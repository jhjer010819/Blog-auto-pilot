import json
import os
import time
import urllib.request
import xml.etree.ElementTree as ET

import google.generativeai as genai
from google.api_core.exceptions import (
    DeadlineExceeded,
    GatewayTimeout,
    InternalServerError,
    ResourceExhausted,
    ServiceUnavailable,
)
from requests.exceptions import Timeout as RequestsTimeout

import publish

# 1. 제미니 API 설정 (깃허브 Secrets에서 전달받음)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. Secrets를 확인해주세요.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.8-flash')

# pytrends의 realtime/daily/hottrends 주소는 404다.
# 한국 실시간 검색어는 구글 트렌드 공개 RSS로 가져온다.
TRENDS_RSS_URL = "https://trends.google.com/trending/rss?geo=KR"
# gapic 기본 timeout/retry는 600초다. 한 요청이 그 한도까지 멈추지 않게 90초로 끊는다.
# 라이브러리의 503 재시도(최대 600초)는 끄고, 아래 횟수와 대기만 사용한다.
# 최악: 90초 * 3회 + 대기 20초 + 60초 = 350초.
GEMINI_REQUEST_TIMEOUT_SECONDS = 90
GEMINI_MAX_ATTEMPTS = 3
GEMINI_RETRY_BACKOFF_SECONDS = (20, 60)
_RETRYABLE_GEMINI_ERRORS = (
    DeadlineExceeded,
    GatewayTimeout,
    ServiceUnavailable,
    InternalServerError,
    ResourceExhausted,
    TimeoutError,
    RequestsTimeout,
)

# 수집이 완전히 실패했을 때만 쓰는 고정 샘플. 실시간 트렌드가 아니다.
FALLBACK_SAMPLE_KEYWORDS = [
    "스타틴 복용법", "유방암 초기증상", "커피 혈당 상승",
    "2026 청년 월세 지원금 자격", "연말정산 부모님 인적공제",
    "스마트폰 배터리 절약 팁", "스타벅스 프리퀀시 예약",
    "김부선", "서동주", "프로포폴 사건"
]


def _parse_trends_rss(payload):
    root = ET.fromstring(payload)
    titles = []
    seen = set()
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        if not title or title in seen:
            continue
        seen.add(title)
        titles.append(title)
        if len(titles) >= 20:
            break
    if not titles:
        raise RuntimeError("구글 트렌드 RSS에 검색어 항목이 없습니다.")
    return titles


def _fetch_live_trend_keywords():
    request = urllib.request.Request(
        TRENDS_RSS_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/rss+xml, application/xml, text/xml",
            "Accept-Language": "ko-KR,ko;q=0.9",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = response.read()
    return _parse_trends_rss(payload)


def fetch_multi_category_keywords():
    """
    [1단계: 다중 카테고리 수집]
    한국 구글 트렌드 실시간 검색어를 수집한다.
    네트워크/파싱 실패 시에만 테스트 샘플로 대체한다.
    """
    print("🔍 [1단계] 다중 카테고리 트렌드 키워드 수집 시작...")

    try:
        raw_list = _fetch_live_trend_keywords()
        keywords_by_category = {"realtime_trending": raw_list}
        print(
            f"✅ [실시간 수집] 구글 트렌드 RSS(geo=KR)에서 "
            f"현재 한국 검색어 {len(raw_list)}개를 가져왔습니다."
        )
    except Exception as e:
        print("🚨 [FALLBACK] 실시간 트렌드 수집에 실패해 하드코딩된 테스트 샘플 키워드를 사용합니다.")
        print("🚨 [FALLBACK] 아래 키워드 풀은 현재 검색 트렌드가 아닙니다.")
        print(f"🚨 [FALLBACK] 실패 원인: {e}")
        keywords_by_category = {"fallback_sample": list(FALLBACK_SAMPLE_KEYWORDS)}

    print(f"   └ 수집된 1차 키워드 풀: {keywords_by_category}")
    return keywords_by_category

def filter_garbage(keywords_list):
    """
    [2단계: 1차 파이썬 텍스트 정제]
    인물 가십, 이슈성 단발성 금지어를 파이썬 코드단에서 1차 탈락시킵니다.
    """
    print("🧹 [2단계] 파이썬 블랙리스트 필터링 적용 중...")
    
    blacklist = ["김부선", "서동주", "프로포폴", "사망", "이혼", "열애", "폭행", "고소"]
    clean_pool = []
    
    for item in keywords_list:
        if not any(b in item for b in blacklist):
            clean_pool.append(item)
            
    print(f"   └ 정제 후 키워드 풀: {clean_pool}")
    return clean_pool

def _is_daily_quota(exc):
    """일일 한도는 기다려도 풀리지 않으므로 재시도하지 않는다."""
    if not isinstance(exc, ResourceExhausted):
        return False
    text = str(exc).lower()
    return "per day" in text or "perday" in text


def _is_retryable_gemini_error(exc):
    if _is_daily_quota(exc):
        return False
    if isinstance(exc, _RETRYABLE_GEMINI_ERRORS):
        return True
    return getattr(exc, "code", None) in {429, 500, 503, 504}


def _gemini_error_label(exc):
    code = getattr(exc, "code", None)
    name = type(exc).__name__
    if code:
        return f"{code} {name}"
    return name


def _call_gemini(prompt):
    """JSON 응답을 요청한다. 각 호출은 90초를 넘기지 않고, 일시 오류는 최대 3회까지 다시 호출한다."""
    for attempt in range(1, GEMINI_MAX_ATTEMPTS + 1):
        try:
            return model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json", "temperature": 0.2},
                request_options={"timeout": GEMINI_REQUEST_TIMEOUT_SECONDS, "retry": None},
            )
        except Exception as exc:
            if _is_daily_quota(exc):
                print("🚨 Gemini 할당량 초과입니다. 일일 한도로 보여 재시도하지 않고 종료합니다.")
                raise
            if not _is_retryable_gemini_error(exc) or attempt >= GEMINI_MAX_ATTEMPTS:
                if _is_retryable_gemini_error(exc):
                    print(
                        f"🚨 Gemini 요청이 {GEMINI_MAX_ATTEMPTS}회 모두 실패했습니다. "
                        f"재시도를 중단합니다. 원인: {exc}"
                    )
                raise
            wait = GEMINI_RETRY_BACKOFF_SECONDS[attempt - 1]
            print(
                f"⏳ Gemini 일시 오류({_gemini_error_label(exc)})입니다. "
                f"{wait:.0f}초 대기 후 {attempt + 1}번째 시도를 합니다. "
                f"(최대 {GEMINI_MAX_ATTEMPTS}회) 원인: {exc}"
            )
            time.sleep(wait)
            print(f"🔁 Gemini 요청을 재시도합니다. ({attempt + 1}/{GEMINI_MAX_ATTEMPTS})")


def select_best_longtail_with_gemini(keywords_pool):
    """
    [3&4단계: 제미니 1차 판사]
    카테고리를 불문하고 오늘 작성 시 팩트 퀄리티와 SEO 유효기간이 가장 미친 1개 키워드 최종 픽.
    category는 키워드 수집 통이 아니라, 그 키워드로 쓸 글의 목적에 따라 허용된 아홉 가지 중 하나다.
    504, 503, 500, 429, 시간 초과는 _call_gemini가 최대 3회(대기 20초, 60초) 다시 호출한다.
    일일 한도는 재시도하지 않는다.
    """
    print("🤖 [3~4단계] 제미니 API가 전체 카테고리 중 최적의 1개 롱테일 최종 낙점 중...")
    
    prompt = f"""
    너는 블로그 SEO 및 콘텐츠 큐레이션 전문가다.
    아래 다양한 카테고리의 키워드 정제 리스트 중, 오늘 3호 블로그에 작성했을 때 
    1) 의학/정부정책/생활 팩트 정보를 체계적으로 작성하기 가장 좋고,
    2) 구글 검색 유저의 유입 유효기간(에버그린)이 가장 긴 '단 1개의 키워드'를 선택해라.

    키워드 리스트: {keywords_pool}

    [조건]
    1. 인물/가십/단발성 이슈는 절대 선택 금지.
    2. 최종 롱테일 제목은 구체적인 신체 증상, 정책 자격, 해결책 형태의 3~4단어 조합으로 다듬을 것.
    3. category는 키워드가 들어 있던 수집 통이 아니라, 그 키워드로 쓸 글의 목적에서 고른다.
    4. 반드시 아래 JSON 형식으로만 응답할 것.

    [분류]
    {publish.category_selection_prompt()}

    JSON 형식:
    {{
        "category": "교육, 건강, 과학, IT, 부동산, 정부혜택, 세금, 정책·제도, 생활정보 중 정확히 하나",
        "selected_seed": "선택한 씨앗 키워드",
        "reason": "선택 이유 1줄 요약",
        "longtail_title": "최종 확정된 롱테일 블로그 제목"
    }}
    """

    response = _call_gemini(prompt)

    result = json.loads(response.text)
    if not isinstance(result, dict):
        raise ValueError("Gemini 응답이 JSON 객체가 아닙니다.")
    try:
        result["category"] = publish.validate_category(str(result.get("category") or ""))
    except publish.PublishError as exc:
        raise ValueError(str(exc)) from exc
    return result

if __name__ == "__main__":
    # 1. 수집
    raw_data = fetch_multi_category_keywords()
    pool = list(raw_data.values())[0]
    
    # 2. 정제
    clean_pool = filter_garbage(pool)
    
    # 3. 제미니 판정 & 롱테일 확정
    result = select_best_longtail_with_gemini(clean_pool)
    
    print("\n==========================================")
    print("🎉 [깃허브 액션 1단계 키워드 선별 결과]")
    print(f"📂 선택 카테고리: {result.get('category')}")
    print(f"📌 선택 씨앗 단어: {result.get('selected_seed')}")
    print(f"💡 선택 이유: {result.get('reason')}")
    print(f"🚀 확정 롱테일 제목: {result.get('longtail_title')}")
    print("==========================================")
