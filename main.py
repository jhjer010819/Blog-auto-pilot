import os
import json
import google.generativeai as genai
from pytrends.request import TrendReq

# 1. 제미니 API 설정 (깃허브 Secrets에서 전달받음)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다. Secrets를 확인해주세요.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.8-flash')

def fetch_multi_category_keywords():
    """
    [1단계: 다중 카테고리 수집]
    구글 트렌드 API를 통해 다양한 카테고리의 핫 키워드를 수집합니다.
    (네트워크 에러 방지를 위해 기본 트렌드 수집 실패 시 예비 수집 데이터 fallback 포함)
    """
    print("🔍 [1단계] 다중 카테고리 트렌드 키워드 수집 시작...")
    
    keywords_by_category = {}
    
    try:
        pytrend = TrendReq(hl='ko-KR', tz=540)
        # 한국 실시간 급상승 검색어 가져오기
        df = pytrend.realtime_trending_searches(pn='p23')
        raw_list = df['title'].tolist()[:20] if not df.empty else []
        keywords_by_category["realtime_trending"] = raw_list
    except Exception as e:
        print(f"⚠️ 구글 트렌드 API 수집 중 참고사항 발생 ({e}), 준비된 테스트 샘플 데이터셋으로 대체 수집합니다.")
        # 파이프라인 검증용 다종 카테고리 샘플 데이터 (건강, 정책, IT/생활, 가십 믹스)
        keywords_by_category["multi_pool"] = [
            "스타틴 복용법", "유방암 초기증상", "커피 혈당 상승",
            "2026 청년 월세 지원금 자격", "연말정산 부모님 인적공제",
            "스마트폰 배터리 절약 팁", "스타벅스 프리퀀시 예약",
            "김부선", "서동주", "프로포폴 사건"
        ]

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

def select_best_longtail_with_gemini(keywords_pool):
    """
    [3&4단계: 제미니 1차 판사]
    카테고리를 불문하고 오늘 작성 시 팩트 퀄리티와 SEO 유효기간이 가장 미친 1개 키워드 최종 픽
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
    3. 반드시 아래 JSON 형식으로만 응답할 것.

    JSON 형식:
    {{
        "category": "선택한 카테고리 (예: 건강/정부혜택/IT생활 등)",
        "selected_seed": "선택한 씨앗 키워드",
        "reason": "선택 이유 1줄 요약",
        "longtail_title": "최종 확정된 롱테일 블로그 제목"
    }}
    """
    
    response = model.generate_content(
        prompt,
        generation_config={"response_mime_type": "application/json", "temperature": 0.2}
    )
    
    return json.loads(response.text)

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
