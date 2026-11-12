"""마크다운 한 편을 Mallow Info Lab 글 파일로 바꿉니다.

이 저장소의 Next.js 앱이 `content/posts/<slug>.html`만 읽습니다.
파일은 post-meta JSON으로 시작하고 나머지는 본문 HTML입니다.
홈 링크, 제목, 날짜, 「함께 읽으면 유용한 정보」는 사이트가 붙입니다.
공개 주소는 https://blog.mymallow.cloud/posts/<slug>/ 입니다.
cover가 비어 있으면 post-meta cover를 빈 문자열로 둡니다. 사이트 목록은 분류 기본 이미지를 보여 줍니다.
표지는 게시 전에 public/images에 두고 --cover /images/<이름> 으로 넘깁니다. Gemini는 문체 다듬기에만 씁니다.
분류는 교육, 건강, 과학, IT, 부동산, 정부혜택, 세금, 정책·제도, 생활정보 중 하나입니다.
관련 글을 지정하지 않으면 같은 분류의 다른 글을 최신순으로 최대 3개 고릅니다.
같은 분류 글이 없을 때만 다른 분류의 최신 글로 대신합니다.

    <script type="application/json" id="post-meta">
    {
      "title": "...",
      "category": "...",
      "date": "YYYY-MM-DD",
      "cover": "",
      "description": "...",
      "related": [{"title": "...", "href": "/posts/slug/"}]
    }
    </script>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

KST = timezone(timedelta(hours=9))
SITE_ORIGIN = "https://blog.mymallow.cloud"
POSTS_DIR = Path("content") / "posts"
DEFAULT_INPUT = Path("inbox") / "post.md"
META_SCRIPT_ID = "post-meta"
REQUIRED_META_KEYS = ("title", "category", "date", "cover", "related")
OPTIONAL_META_KEYS = frozenset({"description"})
RELATED_LIMIT = 3
# 글의 목적으로 고르는 닫힌 분류. 1단계 트렌드 통 이름(realtime_trending 등)은 분류가 아니다.
ALLOWED_CATEGORIES = (
    "교육",
    "건강",
    "과학",
    "IT",
    "부동산",
    "정부혜택",
    "세금",
    "정책·제도",
    "생활정보",
)
CATEGORY_PURPOSES = {
    "교육": "입학, 학교, 입시, 사관학교",
    "건강": "증상, 예방, 의학 정보",
    "과학": "원리나 현상의 설명. 건강 조언과 구분한다",
    "IT": "앱, 소프트웨어, 디지털 기기",
    "부동산": "매매, 전세, 청약, 시세. 지원금 신청은 여기에 넣지 않는다",
    "정부혜택": "지원금, 바우처, 혜택 신청. 예: 청년 월세 지원금",
    "세금": "연말정산, 공제, 신고",
    "정책·제도": "위에 속하지 않는 공식 규정이나 행정 기준",
    "생활정보": "일상·소비 정보. 예: 스타벅스",
}
MIN_BODY_CHARS = 1800
MAX_BODY_CHARS = 2500
DESCRIPTION_TARGET = 120
DESCRIPTION_CEILING = 180
DESCRIPTION_HARD_MAX = 200
SLUG_MAX = 80
GEMINI_MODEL = "gemini-3.8-flash"
# 문체 다듬기 폴백. main.py의 텍스트 모델 순서와 같다.
POLISH_GEMINI_MODELS = (
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
)
# 원문에 없던 이 말이 다듬은 문장에 생기면 그 문장을 되돌린다.
POLISH_BLOCKLIST = [
    "고시",
    "관보",
    "심의",
    "위원회",
    "누락",
    "공시",
    "의결",
    "시행령",
    "공포",
    "확정",
]
POLISH_CERTAINTY_MARKERS = [
    "확인하지 못",
    "예상",
    "계획",
    "가칭",
]
POLISH_DIRECTION_WORDS = [
    "이후",
    "이전",
    "이북",
    "이남",
    "이동",
    "이서",
    "방면",
    "북쪽",
    "남쪽",
    "동쪽",
    "서쪽",
]
POLISH_LENGTH_MIN = 0.6
POLISH_LENGTH_MAX = 1.5
_PROPER_SUFFIXES = ("공단", "역", "선", "부", "청", "시", "도", "구")
# 긴 조사부터 봐야 '에서'가 '에'로 잘리지 않는다.
_PROPER_PARTICLES = (
    "에서도",
    "에서",
    "까지",
    "부터",
    "에게",
    "으로",
    "이며",
    "이고",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "와",
    "과",
    "만",
    "로",
    "도",
)
POLISH_SYSTEM_PROMPT = """너는 한국어 정보 글의 문장만 다듬는 편집자다. 사실 작성자가 아니다.
입력으로 받은 문장 배열 안에서만 고치고, 배열에 없는 문장을 만들지 마라.

해도 되는 일:
- 앞뒤 문장이 자연스럽게 이어지도록 접속과 호응만 다듬는다.
- 번역투와 인공지능이 쓴 듯한 상투적 표현을 뺀다.
- 같은 맺음말이 반복되면 문장 끝만 조금씩 바꾼다.
- 어미는 합니다/입니다 체를 유지한다. 해요체, 반말, 명령조로 바꾸지 마라.
- 행정·법률 공문서 용어는 요청의 쉬운 말 사전 표현으로 바꾼다. plain_language가 true인 문장을 우선 고친다.
- 명사만 포갠 추상 문장은 누가 무엇을 어느 날부터 어떻게 하는지 보이게 고친다. 기준일이 다릅니다, 출발점이 제각각입니다, 경우에는 방문 신청만 가능합니다는 각각 기한을 며칠부터 세는지, 시작하는 날이 항목마다 다릅니다, 직접 방문해서만 신청할 수 있습니다처럼 쓴다.
- 사전에서 not_followed_by 글자가 용어 바로 뒤에 오거나 not_preceded_by 글자가 바로 앞에 오면 바꾸지 마라. 최고속도, 최고점, 최고한도의 최고는 독촉이 아니다.

절대 하지 마라. 하나라도 어기면 그 문장은 폐기된다:
- 숫자, 날짜, 단위, 백분율을 바꾸거나 빼거나 더하지 마라. 자릿수와 소수점도 그대로 둬라.
- 고유명사, 지명, 역 이름, 노선 이름, 기관·회사 이름, 법령 이름, 사업 이름을 바꾸지 마라.
- 그 문장에 없는 사실, 절차, 기관, 제도, 메뉴 이름, 예시를 더하지 마라.
- 단서, 조건, 범위, 예외를 빼지 마라.
- 확실함의 정도를 올리거나 내리지 마라. 예상, 계획, 가칭, 확인하지 못함은 확정, 없음, 누락이 되면 안 된다.
- 주장의 범위를 좁히거나 넓히지 마라. 구간, 대상, 시기를 더 구체적으로 만들거나 더 두루뭉술하게 만들지 마라.
- 방향과 위치를 가리키는 말을 바꾸지 마라. 이후를 이북으로, 이전을 이남으로 바꾸는 일도 금지다.
- 굵은 표시 ** 를 빼거나 옮기거나 더하지 마라. ** 와 ** 사이의 글자는 쉬운 말 사전의 용어를 그 제안 표현으로 바꾸는 경우만 바꿀 수 있다. 그 안의 숫자는 그대로 둔다. 사전에 없는 글자는 바꾸지 마라. 문장 부호를 ** 안으로 넣거나, 닫는 ** 바로 뒤에 조사나 단어를 붙여 표시가 깨지게 하지 마라.
- 따옴표와 괄호 안의 글자를 바꾸지 마라.
- 문장을 요약해 정보를 줄이거나, 설명을 덧붙여 정보를 늘리지 마라.

출력:
- JSON 배열만 출력한다. 설명, 코드 펜스, 머리말은 붙이지 마라.
- 입력과 원소 수가 같고, id도 그대로다.
- 각 원소는 {"id": 번호, "text": "다듬은 문장", "merged_with_next": false} 형식이다.
- 이웃한 두 문장을 하나로 잇고 싶을 때만 앞 문장의 merged_with_next를 true로 한다. 잇는 내용은 앞 문장의 text에만 넣고, 뒤 문장의 text는 빈 문자열로 둔다.
- 세 문장 이상을 하나로 합치지 마라. 줄이 다른 문장끼리는 합치지 마라.
"""
GEMINI_RPM_MIN_WAIT_SECONDS = 60

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_CHO = ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]
_JUNG = [
    "a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe",
    "yo", "u", "wo", "we", "wi", "yu", "eu", "ui", "i",
]
_JONG = [
    "", "k", "k", "k", "n", "n", "n", "t", "l", "k", "m", "l", "l", "l", "p", "l",
    "m", "p", "p", "t", "t", "ng", "t", "t", "k", "t", "p", "t",
]
_SENTENCE_END = set(".!?…。")
_FRONT_MATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)
_HEADING_RE = re.compile(r"^#{1,6}\s+\S")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_LIST_MARKER_RE = re.compile(r"^(\s*[-*+]\s+)(\S.*)$", re.DOTALL)
_LABEL_LINE_RE = re.compile(r"^\s*[-*+]\s+\*\*[^*\n]+\*\*\s*[:：]")
_BOLD_SPAN_RE = re.compile(r"\*\*((?:(?!\*\*).)*?)\*\*", re.DOTALL)
_HANGUL_TOKEN_RE = re.compile(r"[0-9]*[가-힣]+")
_LATIN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9-]*")
_POLISH_USER_MARKER = "SENTENCES_JSON:\n"
_CASUAL_ENDING_RE = re.compile(r"(?:해요|이에요|예요|하죠|거든요|잖아요)(?=[.!?…\s]|$)")
_RETRY_AFTER_RE = re.compile(r"retry in\s+([0-9]+(?:\.[0-9]+)?)\s*s", re.IGNORECASE)
_FENCE_RE = re.compile(r"^```(?:markdown|md)?\s*\n(.*)\n```$", re.DOTALL)
_META_FILE_RE = re.compile(
    r'\A<script type="application/json" id="post-meta">\n(.*?)\n</script>\n(.*)\Z',
    re.DOTALL,
)
_GENERIC_SLUGS = {"post", "draft", "input", "inbox", "readme", "index"}
_DISCLAIMERS = (
    "본 글은 정보 제공을 목적으로 작성되었으며, 정확한 진단 및 치료는 반드시 전문의와 상담하시기 바랍니다.",
    "정부 정책 및 지원 기준은 시기별로 개정될 수 있으므로 정확한 내용은 공식 기관 공고를 확인해 주세요.",
)


class PublishError(Exception):
    """사용자가 고칠 수 있는 게시 실패."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="마크다운을 Mallow Info Lab용 content/posts/<slug>.html 로 변환합니다."
    )
    parser.add_argument(
        "markdown",
        nargs="?",
        help=f"마크다운 경로. 생략하면 {{root}}/{DEFAULT_INPUT.as_posix()}",
    )
    parser.add_argument(
        "--category",
        help=(
            "글 분류. 교육, 건강, 과학, IT, 부동산, 정부혜택, 세금, 정책·제도, 생활정보 중 하나. "
            "front matter category 보다 우선합니다."
        ),
    )
    parser.add_argument("--slug", help="content/posts 파일 이름. 확장자는 붙이지 않습니다.")
    parser.add_argument("--date", help="게시 날짜 YYYY-MM-DD. 기본값은 한국 표준시 오늘입니다.")
    parser.add_argument(
        "--cover",
        help=(
            "표지 경로(/images/<이름>). public/images에 파일이 있어야 합니다. "
            "비우면 표지를 만들지 않고 분류 기본 이미지를 씁니다."
        ),
    )
    parser.add_argument(
        "--related",
        action="append",
        default=None,
        metavar="TITLE|HREF",
        help="관련 글. 예: --related '다른 글|/posts/other'. 여러 번 쓸 수 있습니다.",
    )
    parser.add_argument(
        "--no-related",
        action="store_true",
        help="관련 글을 비웁니다. 기존 글에서 자동으로 고르지 않습니다.",
    )
    parser.add_argument(
        "--polish",
        action="store_true",
        help=(
            "Gemini로 문장만 다듬습니다. 제목, 고지, 출처, 표, 코드, 굵은 라벨은 그대로 둡니다. "
            "쉬운 말 검사에 걸린 문장은 그 문장도 함께 보냅니다. "
            "검증에 걸린 문장은 그 문장만 원문으로 되돌립니다. "
            "--dry-run과 함께 쓰면 다듬은 마크다운 전체를 표준 출력에 표시합니다."
        ),
    )
    parser.add_argument(
        "--plain-lang-strict",
        action="store_true",
        help="쉬운 말 검사에 걸리면 파일을 쓰지 않고 실패합니다. 기본값은 경고만 하고 계속합니다.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="파일을 쓰지 않고 결과만 확인합니다.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="글 파일을 현재 브랜치에 커밋하고 푸시합니다. 기본값은 푸시하지 않습니다.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="저장소 루트. 기본값은 publish.py가 있는 디렉터리입니다.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        publish(args)
    except PublishError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def publish(args: argparse.Namespace) -> Path | None:
    if args.dry_run and args.push:
        raise PublishError("--dry-run과 --push는 함께 쓸 수 없습니다.")
    if args.no_related and args.related:
        raise PublishError("--no-related와 --related는 함께 쓸 수 없습니다.")

    root = (args.root or Path(__file__).resolve().parent).resolve()
    source = resolve_input(root, args.markdown)
    raw = read_markdown(source)
    front_matter, document = parse_front_matter(raw)
    title, body = split_h1(document)
    title = choose_title(front_matter, title)
    if not title:
        raise PublishError("제목이 없습니다. 첫 줄에 '# 제목'을 쓰거나 front matter title을 넣으세요.")
    if not body.strip():
        raise PublishError("본문이 비어 있습니다.")

    category = (args.category or front_matter.get("category") or "").strip()
    if not category:
        raise PublishError("분류가 없습니다. --category 또는 front matter의 category를 지정하세요.")
    category = validate_category(category)
    date = validate_date(args.date or str(front_matter.get("date") or "") or today_kst())
    requested_slug = (args.slug or str(front_matter.get("slug") or "")).strip()
    if requested_slug:
        slug = validate_slug(requested_slug)
    else:
        slug = ensure_unique_slug(root, validate_slug(slug_from_source(source, title)), title)
    supplied_cover = args.cover if args.cover is not None else str(front_matter.get("cover") or "")
    cover = resolve_cover(root, supplied_cover)

    plain_flags = plain_language_flags(raw)
    _emit_plain_language(plain_flags)
    if args.plain_lang_strict and plain_flags:
        raise PublishError(
            f"쉬운 말 검사에 {len(plain_flags)}곳이 걸렸습니다. "
            "원고를 고치거나 plain_lang_strict를 끄세요."
        )

    full_markdown = f"# {title}\n\n{body.strip()}\n"
    if args.polish:
        polished = polish_markdown(raw, plain_flags)
        _polished_front, polished_document = parse_front_matter(polished)
        polished_title, body = split_h1(polished_document)
        if polished_title != title:
            raise PublishError("문체 다듬기 과정에서 제목이 바뀌었습니다.")
        if not body.strip():
            raise PublishError("문체 다듬기 뒤 본문이 비었습니다.")
        full_markdown = f"# {title}\n\n{body.strip()}\n"
        if args.dry_run:
            print_polished_markdown(polished)

    related = resolve_related(args, front_matter, root, slug, category)
    body_html = markdown_to_html(body)
    if not body_html.strip():
        raise PublishError("마크다운을 HTML로 바꾸지 못했습니다.")
    supplied_description = str(front_matter.get("description") or "").strip()
    if supplied_description and len(supplied_description) <= DESCRIPTION_HARD_MAX:
        description = supplied_description
    else:
        description = description_from_html(body_html)
    meta = {
        "title": title,
        "category": category,
        "date": date,
        "cover": cover,
        "related": related,
    }
    if description and len(description) <= DESCRIPTION_HARD_MAX:
        meta["description"] = description
    document_html = render_post_file(meta, body_html)
    destination = root / POSTS_DIR / f"{slug}.html"
    length = manuscript_length(full_markdown)
    print_summary(
        root,
        destination,
        slug,
        title,
        category,
        date,
        description,
        length,
        len(related),
        cover,
        args.dry_run,
        args.push,
    )
    if args.dry_run:
        return None

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document_html, encoding="utf-8")
    if args.push:
        git_commit_and_push(root, [destination], title)
    return destination


def resolve_cover(root: Path, supplied: str) -> str:
    """빈 표지는 그대로 두고, /images/ 경로는 public/images 안의 파일인지 확인합니다."""
    cover = supplied.strip()
    if not cover:
        return ""
    if not cover.startswith("/images/"):
        return cover
    name = cover[len("/images/") :]
    if not _is_repo_image_name(name):
        raise PublishError(
            f"표지 경로가 올바르지 않습니다: {cover}. /images/ 안의 파일 이름을 지정하세요."
        )
    images_dir = (root / "public" / "images").resolve()
    path = (images_dir / name).resolve()
    if path != images_dir and images_dir not in path.parents:
        raise PublishError(
            f"표지 경로가 올바르지 않습니다: {cover}. /images/ 안의 파일 이름을 지정하세요."
        )
    if not path.is_file():
        raise PublishError(
            f"표지 파일이 없습니다: public/images/{name}. "
            "public/images에 이미지를 먼저 넣은 뒤 --cover /images/<이름> 으로 지정하세요."
        )
    return cover


def _is_repo_image_name(name: str) -> bool:
    if not name or name.endswith("/") or "\\" in name or "?" in name or "\x00" in name:
        return False
    parts = PurePosixPath(name).parts
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def resolve_input(root: Path, markdown: str | None) -> Path:
    path = Path(markdown) if markdown else root / DEFAULT_INPUT
    if not path.is_file():
        raise PublishError(f"마크다운 파일을 찾을 수 없습니다: {path}")
    return path


def read_markdown(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise PublishError(f"마크다운이 UTF-8이 아닙니다: {path}") from exc
    except OSError as exc:
        raise PublishError(f"마크다운을 읽지 못했습니다: {path}") from exc
    if not text.strip():
        raise PublishError("마크다운이 비어 있습니다.")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_front_matter(text: str) -> tuple[dict[str, str | list], str]:
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, str | list] = {}
    related: list[dict[str, str]] = []
    lines = match.group(1).splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if line.startswith((" ", "\t")):
            raise PublishError("front matter 형식을 읽을 수 없습니다.")
        if ":" not in line:
            raise PublishError(f"front matter 형식을 읽을 수 없습니다: {line}")
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "related" and value == "":
            index += 1
            current: dict[str, str] | None = None
            while index < len(lines) and (
                lines[index].startswith((" ", "\t")) or lines[index].strip().startswith("-")
            ):
                item = lines[index].strip()
                if item.startswith("- "):
                    current = {}
                    related.append(current)
                    remainder = item[2:].strip()
                    if remainder:
                        item_key, item_value = split_meta_pair(remainder)
                        current[item_key] = item_value
                elif current is not None and item:
                    item_key, item_value = split_meta_pair(item)
                    current[item_key] = item_value
                index += 1
            meta["related"] = related
            continue
        meta[key] = strip_quotes(value)
        index += 1
    return meta, text[match.end() :]


def split_meta_pair(text: str) -> tuple[str, str]:
    if ":" not in text:
        raise PublishError(f"front matter 형식을 읽을 수 없습니다: {text}")
    key, value = text.split(":", 1)
    return key.strip().lower(), strip_quotes(value.strip())


def strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def split_h1(markdown: str) -> tuple[str, str]:
    lines = markdown.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            title = line[2:].strip()
            body = "\n".join([*lines[:index], *lines[index + 1 :]]).strip()
            return title, body
    return "", markdown.strip()


def choose_title(front_matter: dict, heading: str) -> str:
    titled = str(front_matter.get("title") or "").strip()
    if titled and heading and titled != heading:
        raise PublishError("front matter title과 H1 제목이 다릅니다.")
    return titled or heading


def today_kst() -> str:
    return datetime.now(KST).date().isoformat()


def validate_date(value: str) -> str:
    value = value.strip()
    if not _DATE_RE.fullmatch(value):
        raise PublishError(f"날짜는 YYYY-MM-DD 형식이어야 합니다: {value}")
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise PublishError(f"올바른 날짜가 아닙니다: {value}") from exc
    return value


def slug_from_source(source: Path, title: str) -> str:
    slug = slugify(title)
    if slug:
        return slug
    stem = re.sub(r"-{2,}", "-", source.stem.strip().lower().replace("_", "-")).strip("-")
    if stem not in _GENERIC_SLUGS and _SLUG_RE.fullmatch(stem):
        return stem
    raise PublishError("슬러그를 만들지 못했습니다. --slug를 지정하세요.")


def romanize_hangul(char: str) -> str:
    code = ord(char) - 0xAC00
    if code < 0 or code > 11171:
        return ""
    cho, jung, jong = code // 588, (code % 588) // 28, code % 28
    return _CHO[cho] + _JUNG[jung] + _JONG[jong]


def slugify(value: str) -> str:
    pieces: list[str] = []
    for char in value.strip().lower():
        if "가" <= char <= "힣":
            pieces.append(romanize_hangul(char))
        elif char.isascii() and char.isalnum():
            pieces.append(char)
        elif char.isspace() or char in "-_":
            pieces.append("-")
    slug = re.sub(r"-{2,}", "-", "".join(pieces)).strip("-")
    if len(slug) <= SLUG_MAX:
        return slug
    trimmed = slug[:SLUG_MAX].rstrip("-")
    if "-" in trimmed:
        trimmed = trimmed.rsplit("-", 1)[0]
    return trimmed.strip("-")


def validate_slug(slug: str) -> str:
    slug = slug.strip().lower()
    if not _SLUG_RE.fullmatch(slug):
        raise PublishError(
            "슬러그는 영문 소문자, 숫자, 하이픈만 사용할 수 있습니다: " + slug
        )
    return slug


def ensure_unique_slug(root: Path, slug: str, title: str) -> str:
    posts_dir = root / POSTS_DIR
    candidate = slug
    number = 2
    while (posts_dir / f"{candidate}.html").exists():
        try:
            meta, _body = read_post_meta((posts_dir / f"{candidate}.html").read_text(encoding="utf-8"))
        except (OSError, PublishError, json.JSONDecodeError, UnicodeError, ValueError):
            meta = {}
        if str(meta.get("title") or "").strip() == title:
            return candidate
        suffix = f"-{number}"
        base = slug[: SLUG_MAX - len(suffix)].rstrip("-")
        candidate = f"{base}{suffix}"
        number += 1
        if number > 100:
            raise PublishError("슬러그를 유일하게 만들지 못했습니다.")
    return candidate


def validate_category(value: str) -> str:
    category = value.strip()
    if category not in ALLOWED_CATEGORIES:
        allowed = ", ".join(ALLOWED_CATEGORIES)
        shown = category or "(빈 값)"
        raise PublishError(f"분류는 허용 목록 중 하나여야 합니다: {shown}. 허용: {allowed}")
    return category


def category_selection_prompt() -> str:
    """1단계 제미니 프롬프트에 넣는 분류 규칙.

    분류는 키워드 수집 통이 아니라, 그 키워드로 쓸 글의 목적에서 고른다.
    """
    lines = [
        "category는 아래 아홉 가지 중 정확히 하나만 쓴다.",
        "기준은 그 키워드로 쓸 글의 목적이다. "
        "구글 트렌드 키워드를 담아 둔 통 이름(realtime_trending, fallback_sample 등)을 category로 쓰지 않는다.",
    ]
    for name in ALLOWED_CATEGORIES:
        lines.append(f"- {name}: {CATEGORY_PURPOSES[name]}")
    return "\n".join(lines)


def resolve_related(
    args: argparse.Namespace,
    front_matter: dict,
    root: Path,
    slug: str,
    category: str,
) -> list[dict[str, str]]:
    if args.no_related:
        return []
    if args.related:
        return normalize_related([parse_related_arg(item) for item in args.related])
    if "related" in front_matter:
        raw_related = front_matter.get("related") or []
        if not isinstance(raw_related, list):
            raise PublishError("front matter related 형식이 잘못되었습니다.")
        return normalize_related(raw_related)
    existing = load_existing_posts(root / POSTS_DIR)
    return auto_related(existing, slug, category)


def parse_related_arg(value: str) -> dict[str, str]:
    if "|" not in value:
        raise PublishError("관련 글은 '제목|/posts/slug' 형식이어야 합니다.")
    title, href = value.split("|", 1)
    return {"title": title.strip(), "href": href.strip()}


def normalize_related(items: list[dict]) -> list[dict[str, str]]:
    related: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            raise PublishError("관련 글 형식이 잘못되었습니다.")
        title = str(item.get("title") or "").strip()
        href = str(item.get("href") or "").strip()
        if not title or not href:
            raise PublishError("관련 글에는 제목과 링크가 모두 필요합니다.")
        if not (href.startswith("/") or href.startswith("http://") or href.startswith("https://")):
            raise PublishError(f"관련 글 링크는 / 또는 http(s)로 시작해야 합니다: {href}")
        related.append({"title": title, "href": normalize_href(href)})
    return related


def normalize_href(href: str) -> str:
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("/") and not href.startswith("//") and "\\" not in href and ".." not in href:
        matched = re.match(r"^([^?#]*)(.*)$", href)
        path = matched.group(1) if matched else href
        suffix = matched.group(2) if matched else ""
        if path != "/" and not path.endswith("/"):
            path = f"{path}/"
        return path + suffix
    return href


def load_existing_posts(posts_dir: Path) -> list[dict[str, str]]:
    if not posts_dir.is_dir():
        return []
    posts: list[dict[str, str]] = []
    for path in sorted(posts_dir.glob("*.html")):
        try:
            meta, _body = read_post_meta(path.read_text(encoding="utf-8"))
        except (OSError, PublishError, json.JSONDecodeError, UnicodeError, ValueError):
            print(f"기존 글 파일을 건너뜁니다: {path.name}", file=sys.stderr)
            continue
        title = str(meta.get("title") or "").strip()
        date = str(meta.get("date") or "").strip()
        if not title or not _DATE_RE.fullmatch(date):
            print(f"기존 글 메타가 불완전합니다: {path.name}", file=sys.stderr)
            continue
        posts.append(
            {
                "slug": path.stem,
                "title": title,
                "date": date,
                "category": str(meta.get("category") or "").strip(),
            }
        )
    return posts


def auto_related(posts: list[dict[str, str]], slug: str, category: str) -> list[dict[str, str]]:
    """같은 분류의 다른 글을 최신순으로 최대 RELATED_LIMIT개 고른다.

    같은 분류 글이 하나라도 있으면 그 글만 반환하고 다른 분류로 채우지 않는다.
    같은 분류 글이 전혀 없을 때만 다른 분류의 최신 글로 대신한다.
    추천 툴·외부 CTA는 넣지 않고, 글 자체만 가리킨다.
    """
    others = [post for post in posts if post["slug"] != slug]
    same = [post for post in others if post.get("category") == category]
    chosen = same if same else others
    chosen.sort(key=lambda post: post["slug"])
    chosen.sort(key=lambda post: post["date"], reverse=True)
    return [
        {"title": post["title"], "href": f"/posts/{post['slug']}/"}
        for post in chosen[:RELATED_LIMIT]
    ]


def markdown_to_html(body: str) -> str:
    try:
        import markdown
    except ImportError as exc:
        raise PublishError(
            "markdown 라이브러리가 없습니다. pip install -r requirements.txt 를 실행하세요."
        ) from exc
    html = markdown.markdown(
        body.strip(),
        extensions=["tables", "fenced_code", "sane_lists"],
        output_format="html",
    )
    return mark_disclaimer_paragraphs(html.strip())


_DISCLAIMER_CLASS = "post-disclaimer"
_PARAGRAPH_RE = re.compile(r"<p\b([^>]*)>(.*?)</p>", re.IGNORECASE | re.DOTALL)


def mark_disclaimer_paragraphs(html: str) -> str:
    def replace(match: re.Match[str]) -> str:
        attrs = match.group(1) or ""
        inner = match.group(2)
        found, rest = _leftover_after_disclaimers(plain_from_html(inner))
        if not found:
            return f"<p{attrs}>{inner}</p>"
        if not rest:
            return f"<p{_with_disclaimer_class(attrs)}>{inner}</p>"
        if "<" in inner:
            return f"<p{attrs}>{inner}</p>"
        return _split_plain_disclaimer_paragraph(attrs, inner)

    return _PARAGRAPH_RE.sub(replace, html)


def _leftover_after_disclaimers(text: str) -> tuple[bool, str]:
    rest = re.sub(r"\s+", " ", text).strip()
    found = False
    changed = True
    while changed:
        changed = False
        for sentence in _DISCLAIMERS:
            if sentence not in rest:
                continue
            rest = re.sub(r"\s+", " ", rest.replace(sentence, " ", 1)).strip()
            found = True
            changed = True
    return found, rest


def _split_plain_disclaimer_paragraph(attrs: str, inner: str) -> str:
    pieces: list[tuple[str, str]] = []
    rest = inner
    while rest:
        earliest = -1
        sentence = ""
        for candidate in _DISCLAIMERS:
            index = rest.find(candidate)
            if index != -1 and (earliest == -1 or index < earliest):
                earliest = index
                sentence = candidate
        if earliest == -1:
            pieces.append(("body", rest))
            break
        if earliest > 0:
            pieces.append(("body", rest[:earliest]))
        pieces.append(("disclaimer", sentence))
        rest = rest[earliest + len(sentence) :]

    groups: list[tuple[str, str]] = []
    pending = ""
    for kind, text in pieces:
        if not plain_from_html(text):
            if groups:
                groups[-1] = (groups[-1][0], groups[-1][1] + text)
            else:
                pending += text
            continue
        text = pending + text
        pending = ""
        if groups and groups[-1][0] == kind:
            groups[-1] = (kind, groups[-1][1] + text)
        else:
            groups.append((kind, text))
    if pending and groups:
        groups[-1] = (groups[-1][0], groups[-1][1] + pending)

    body_attrs = _without_disclaimer_class(attrs)
    rendered: list[str] = []
    for kind, text in groups:
        content = text.strip()
        if not content:
            continue
        tag_attrs = f' class="{_DISCLAIMER_CLASS}"' if kind == "disclaimer" else body_attrs
        rendered.append(f"<p{tag_attrs}>{content}</p>")
    return "\n".join(rendered)


def _with_disclaimer_class(attrs: str) -> str:
    match = re.search(r'\bclass\s*=\s*"([^"]*)"', attrs, flags=re.IGNORECASE)
    if match:
        classes = [part for part in match.group(1).split() if part]
        if _DISCLAIMER_CLASS not in classes:
            classes.append(_DISCLAIMER_CLASS)
        replaced = f'class="{" ".join(classes)}"'
        return attrs[: match.start()] + replaced + attrs[match.end() :]
    if not attrs:
        return f' class="{_DISCLAIMER_CLASS}"'
    prefix = "" if attrs.startswith(" ") else " "
    return f'{prefix}{attrs} class="{_DISCLAIMER_CLASS}"'


def _without_disclaimer_class(attrs: str) -> str:
    match = re.search(r'\bclass\s*=\s*"([^"]*)"', attrs, flags=re.IGNORECASE)
    if not match:
        return attrs
    classes = [part for part in match.group(1).split() if part and part != _DISCLAIMER_CLASS]
    replaced = f'class="{" ".join(classes)}"' if classes else ""
    nxt = attrs[: match.start()] + replaced + attrs[match.end() :]
    nxt = re.sub(r"[ \t]{2,}", " ", nxt)
    if nxt.strip() == "":
        return ""
    if not nxt.startswith(" "):
        nxt = f" {nxt}"
    return nxt


def render_post_file(meta: dict, body_html: str) -> str:
    ordered: dict = {key: meta[key] for key in ("title", "category", "date", "cover")}
    description = str(meta.get("description") or "").strip()
    if description:
        ordered["description"] = description
    ordered["related"] = meta["related"]
    payload = json.dumps(ordered, ensure_ascii=False, indent=2).replace("<", "\\u003c")
    body = body_html.strip() + "\n"
    return (
        '<script type="application/json" id="'
        + META_SCRIPT_ID
        + '">\n'
        + payload
        + "\n</script>\n"
        + body
    )


def read_post_meta(text: str) -> tuple[dict, str]:
    match = _META_FILE_RE.match(text)
    if not match:
        raise PublishError("글 파일은 post-meta 스크립트로 시작해야 합니다.")
    try:
        meta = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise PublishError("post-meta JSON을 읽을 수 없습니다.") from exc
    if not isinstance(meta, dict):
        raise PublishError("post-meta는 JSON 객체여야 합니다.")
    return meta, match.group(2)


def parse_post_file(text: str) -> tuple[dict, str]:
    meta, body = read_post_meta(text)
    missing = [key for key in REQUIRED_META_KEYS if key not in meta]
    extra = [key for key in meta if key not in REQUIRED_META_KEYS and key not in OPTIONAL_META_KEYS]
    if missing or extra:
        raise PublishError("post-meta 필드가 예상과 다릅니다.")
    return meta, body


def description_from_html(html: str) -> str:
    return description_from_plain(plain_from_html(intro_from_html(html)))


def intro_from_html(html: str) -> str:
    rest = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    rest = re.sub(r"<style\b[^>]*>.*?</style>", " ", rest, flags=re.I | re.S).strip()
    leading = re.compile(r"^<h[1-6]\b[^>]*>.*?</h[1-6]>", re.I | re.S)
    while True:
        match = leading.match(rest)
        if not match:
            break
        rest = rest[match.end() :].strip()
    next_heading = re.search(r"<h[1-6]\b", rest, flags=re.I)
    if next_heading:
        rest = rest[: next_heading.start()]
    return rest


def plain_from_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    for source, target in (
        ("&nbsp;", " "),
        ("&amp;", "&"),
        ("&lt;", "<"),
        ("&gt;", ">"),
        ("&quot;", '"'),
        ("&#39;", "'"),
    ):
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char not in _SENTENCE_END:
            index += 1
            continue
        if (
            char == "."
            and index > 0
            and index + 1 < length
            and text[index - 1].isdigit()
            and text[index + 1].isdigit()
        ):
            index += 1
            continue
        end = index + 1
        while end < length and text[end] in _SENTENCE_END:
            end += 1
        if end == length or text[end].isspace():
            sentence = text[start:end].strip()
            if sentence:
                sentences.append(sentence)
            start = end
            index = end
            continue
        index += 1
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def description_from_plain(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return ""
    sentences = split_sentences(normalized)
    if not sentences:
        return cut_at_boundary(normalized, DESCRIPTION_TARGET)
    chosen = sentences[0]
    if len(sentences) > 1:
        two = f"{sentences[0]} {sentences[1]}"
        if len(two) <= DESCRIPTION_CEILING:
            chosen = two
    if len(chosen) <= DESCRIPTION_HARD_MAX:
        return chosen
    return cut_at_boundary(chosen, DESCRIPTION_TARGET)


def cut_at_boundary(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    window = text[:limit]
    best = -1
    for index, char in enumerate(window):
        if char in " ,，、;；:：":
            best = index
    if best >= 40:
        return window[:best].rstrip(" ,，、;；:：")
    return text


def manuscript_length(markdown: str) -> int:
    _title, body = split_h1(markdown)
    return len(body.replace("\n", "").replace("\r", ""))


def headings_of(markdown: str) -> list[str]:
    return [line.strip() for line in markdown.splitlines() if _HEADING_RE.match(line)]


def table_row_count(markdown: str) -> int:
    return sum(1 for line in markdown.splitlines() if line.strip().startswith("|"))


def validate_polish(original: str, polished: str) -> list[str]:
    problems: list[str] = []
    polished = polished.strip()
    if not polished:
        return ["다듬은 글이 비어 있습니다."]
    if headings_of(original) != headings_of(polished):
        problems.append("제목의 문구와 순서가 바뀌었습니다.")
    if Counter(_NUMBER_RE.findall(original)) != Counter(_NUMBER_RE.findall(polished)):
        problems.append("숫자가 추가되거나 빠졌습니다.")
    if table_row_count(original) != table_row_count(polished):
        problems.append("표의 행 수가 바뀌었습니다.")
    for disclaimer in _DISCLAIMERS:
        if disclaimer in original and disclaimer not in polished:
            problems.append("의학·정책 고지 문장이 빠졌거나 바뀌었습니다.")
    original_casual = len(_CASUAL_ENDING_RE.findall(original))
    polished_casual = len(_CASUAL_ENDING_RE.findall(polished))
    if polished_casual > original_casual:
        problems.append("합니다/입니다 체를 해요체로 바꾸었습니다.")
    original_length = manuscript_length(original)
    polished_length = manuscript_length(polished)
    if MIN_BODY_CHARS <= original_length <= MAX_BODY_CHARS:
        if not (MIN_BODY_CHARS <= polished_length <= MAX_BODY_CHARS):
            problems.append(
                f"본문 분량이 {polished_length}자입니다. {MIN_BODY_CHARS}~{MAX_BODY_CHARS}자를 유지해야 합니다."
            )
    else:
        before = distance_to_range(original_length)
        after = distance_to_range(polished_length)
        if after > before:
            problems.append(
                f"본문 분량이 목표에서 더 멀어졌습니다. {original_length}자에서 {polished_length}자가 되었습니다."
            )
    return problems


def distance_to_range(length: int) -> int:
    if length < MIN_BODY_CHARS:
        return MIN_BODY_CHARS - length
    if length > MAX_BODY_CHARS:
        return length - MAX_BODY_CHARS
    return 0


@dataclass(frozen=True)
class PolishSentence:
    """Gemini에 보내는 본문 문장 하나. start/end는 원문 전체에서의 위치다."""

    id: int
    start: int
    end: int
    text: str
    line: int = 0
    flagged: bool = False


class PolishModelError(Exception):
    """문체 다듬기 호출이 모델 폴백 끝까지 실패했을 때."""

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(detail or reason)


class _PolishResponseError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def polish_markdown(markdown: str, plain_flags: list[dict] | None = None) -> str:
    """문장만 골라 한 번의 Gemini 요청으로 다듬는다.

    제목, 고지, 출처, 표, 코드, 굵은 라벨은 보내지 않는다.
    쉬운 말 검사에 걸린 문장은 그 보호 규칙보다 우선해서 포함한다.
    검증에 걸린 문장만 원문으로 되돌리고, 응답 자체가 잘못되면 글 전체를 원문으로 둔다.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise PublishError("GEMINI_API_KEY가 없습니다. --polish 를 쓰려면 환경 변수로 설정하세요.")

    flags = plain_language_flags(markdown) if plain_flags is None else plain_flags
    sentences, protected_units = collect_polish_sentences(markdown, flags)
    if not sentences:
        _emit_polish_status(
            {
                "status": "ok",
                "model": "none",
                "applied": 0,
                "reverted": 0,
                "kept": protected_units,
                "reverts": [],
            }
        )
        return markdown

    try:
        model_name, response_text = call_polish_models(
            api_key,
            POLISH_SYSTEM_PROMPT,
            build_polish_user_prompt(sentences, flags),
        )
    except PublishError as exc:
        if "라이브러리" in str(exc):
            raise
        _emit_polish_error("api", str(exc))
        return markdown
    except PolishModelError as exc:
        _emit_polish_error(exc.reason or "api", exc.detail or str(exc))
        return markdown
    except Exception as exc:  # noqa: BLE001 - 호출 실패는 원문 유지로 넘긴다.
        _emit_polish_error("api", str(exc))
        return markdown

    try:
        rows = parse_polish_response(response_text, len(sentences))
    except _PolishResponseError as exc:
        _emit_polish_error(exc.reason, "Gemini 응답 형식이 맞지 않아 원문을 유지합니다.")
        return markdown

    result, summary = apply_polish_rows(markdown, sentences, rows, protected_units, model_name)
    _emit_polish_status(summary)
    return result


def build_polish_user_prompt(
    sentences: list[PolishSentence],
    plain_flags: list[dict] | None = None,
) -> str:
    flags = plain_flags or []
    payload = [
        {
            "id": sentence.id,
            "text": sentence.text,
            "merged_with_next": False,
            "plain_language": sentence.flagged,
        }
        for sentence in sentences
    ]
    noted: list[dict] = []
    for sentence in sentences:
        if not sentence.flagged:
            continue
        related = [
            {"term": flag["term"], "suggestion": flag["suggestion"]}
            for flag in flags
            if flag.get("line") == sentence.line and flag.get("term") and str(flag["term"]) in sentence.text
        ]
        noted.append({"id": sentence.id, "hits": related})
    dictionary = json.dumps(_dictionary_for_prompt(), ensure_ascii=False)
    flagged = json.dumps(noted, ensure_ascii=False)
    body = json.dumps(payload, ensure_ascii=False)
    return (
        "행정·법률 용어는 아래 쉬운 말 사전으로 바꿔라. "
        "not_followed_by 글자가 용어 바로 뒤에 오거나 not_preceded_by 글자가 바로 앞에 오면 바꾸지 마라. "
        "최고속도, 최고점, 최고한도처럼 가장 높다는 뜻의 최고는 독촉으로 바꾸지 마라.\n"
        f"PLAIN_DICTIONARY:\n{dictionary}\n"
        "plain_language가 true인 문장을 우선 고쳐라. "
        "걸린 용어는 제안된 말로 바꾸고, 명사만 있는 추상 문장은 누가 무엇을 어느 날부터 어떻게 하는지 구체적인 문장으로 풀어라. "
        "예: 기준일이 다릅니다 → 기한을 며칠부터 세는지 적는다. "
        "출발점이 제각각입니다 → 시작하는 날이 항목마다 다릅니다. "
        "경우에는 방문 신청만 가능합니다 → 직접 방문해서만 신청할 수 있습니다.\n"
        f"PLAIN_LANG_HITS:\n{flagged}\n"
        "아래 JSON 배열의 문장만 다듬어, 같은 길이의 JSON 배열로 답하라. "
        "id는 유지하고, 각 원소에 text와 merged_with_next를 넣어라. "
        "plain_language 필드는 출력에 넣지 마라.\n"
        f"{_POLISH_USER_MARKER}{body}"
    )


def collect_polish_sentences(
    markdown: str,
    plain_flags: list[dict] | None = None,
) -> tuple[list[PolishSentence], int]:
    """보호 구간을 뺀 문장과, 보내지 않은 구간의 개수를 돌려준다.

    쉬운 말 검사에 걸린 문장은 제목·굵은 라벨이어도 포함한다.
    표, 코드, 고지, 출처, 프론트매터는 검사가 건너뛰므로 여기에도 넣지 않는다.
    """
    flags = plain_flags or []
    protected_units = 0
    found: list[tuple[int, int, str, int, bool]] = []
    front = _FRONT_MATTER_RE.match(markdown)
    body_start = front.end() if front else 0
    if front:
        protected_units += 1
    sources_at = _sources_start(markdown, body_start)
    body_end = sources_at if sources_at is not None else len(markdown)
    if sources_at is not None:
        protected_units += 1

    lines = _line_spans(markdown)
    index = 0
    while index < len(lines):
        start, _end, raw_line = lines[index]
        if start < body_start or start >= body_end:
            index += 1
            continue
        newline_len = len(raw_line) - len(raw_line.rstrip("\r\n"))
        content = raw_line[: len(raw_line) - newline_len] if newline_len else raw_line
        stripped = content.strip()
        if stripped.startswith("```"):
            index += 1
            while index < len(lines) and lines[index][0] < body_end:
                fence_line = lines[index][2].strip()
                index += 1
                if fence_line.startswith("```"):
                    break
            protected_units += 1
            continue
        if stripped.startswith("|"):
            index += 1
            while index < len(lines) and lines[index][0] < body_end and lines[index][2].strip().startswith("|"):
                index += 1
            protected_units += 1
            continue
        if not stripped:
            index += 1
            continue
        line_no = markdown.count("\n", 0, start) + 1
        protected_line = _protected_polish_line(content)
        if protected_line and not _line_has_plain_flag(content, line_no, flags):
            protected_units += 1
            index += 1
            continue
        payload_start = start
        payload = content
        heading = re.match(r"^(#{1,6}\s+)(\S.*)$", content)
        if heading:
            payload_start = start + len(heading.group(1))
            payload = heading.group(2)
        else:
            marker = _LIST_MARKER_RE.match(content)
            if marker:
                payload_start = start + len(marker.group(1))
                payload = marker.group(2)
        extracted: list[tuple[int, int, str]] = []
        for rel_start, rel_end in _balanced_sentence_spans(payload):
            absolute_start = payload_start + rel_start
            absolute_end = payload_start + rel_end
            sentence = markdown[absolute_start:absolute_end]
            if _is_disclaimer_text(sentence):
                protected_units += 1
                continue
            extracted.append((absolute_start, absolute_end, sentence))
        if protected_line:
            for span_start, span_end, sentence in extracted:
                if _sentence_has_plain_flag(sentence, line_no, flags):
                    found.append((span_start, span_end, sentence, line_no, True))
                else:
                    protected_units += 1
        else:
            for span_start, span_end, sentence in extracted:
                flagged = _sentence_has_plain_flag(sentence, line_no, flags)
                found.append((span_start, span_end, sentence, line_no, flagged))
        index += 1

    sentences = [
        PolishSentence(
            id=number,
            start=span_start,
            end=span_end,
            text=text,
            line=line_no,
            flagged=flagged,
        )
        for number, (span_start, span_end, text, line_no, flagged) in enumerate(found, start=1)
    ]
    return sentences, protected_units


def _line_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        spans.append((offset, offset + len(line), line))
        offset += len(line)
    if offset < len(text):
        spans.append((offset, len(text), text[offset:]))
    return spans


def _sources_start(markdown: str, body_start: int) -> int | None:
    """본문 뒤에서 마지막 `---` 줄이 시작되는 위치. 그 줄부터 출처로 본다."""
    last: int | None = None
    for start, _end, raw_line in _line_spans(markdown):
        if start < body_start:
            continue
        if raw_line.strip() == "---":
            last = start
    return last


def _protected_polish_line(content: str) -> bool:
    stripped = content.strip()
    if _HEADING_RE.match(stripped):
        return True
    if _is_entirely_bold(stripped):
        return True
    if _LABEL_LINE_RE.match(content):
        return True
    if _is_mostly_bold_list_item(content):
        return True
    if _is_disclaimer_text(stripped):
        return True
    return False


def _is_entirely_bold(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 4 or not stripped.startswith("**") or not stripped.endswith("**"):
        return False
    inner = stripped[2:-2]
    return bool(inner.strip()) and "**" not in inner


def _is_mostly_bold_list_item(text: str) -> bool:
    """목록 항목에서 공백을 뺀 글자의 대부분이 굵은 글씨면 보내지 않는다."""
    stripped = text.strip()
    marker = _LIST_MARKER_RE.match(stripped)
    if not marker:
        return False
    content = marker.group(2).strip()
    spans = _BOLD_SPAN_RE.findall(content)
    if not spans:
        return False
    bold_chars = sum(len(re.sub(r"\s+", "", span)) for span in spans)
    plain = re.sub(r"\s+", "", content.replace("**", ""))
    if not plain:
        return True
    return bold_chars / len(plain) >= 0.75


def _is_disclaimer_text(text: str) -> bool:
    found, rest = _leftover_after_disclaimers(text)
    return found and not rest


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char not in _SENTENCE_END:
            index += 1
            continue
        if (
            char == "."
            and index > 0
            and index + 1 < length
            and text[index - 1].isdigit()
            and text[index + 1].isdigit()
        ):
            index += 1
            continue
        end = index + 1
        while end < length and text[end] in _SENTENCE_END:
            end += 1
        if end == length or text[end].isspace():
            left = start
            right = end
            while left < right and text[left].isspace():
                left += 1
            while right > left and text[right - 1].isspace():
                right -= 1
            if left < right:
                spans.append((left, right))
            start = end
            index = end
            continue
        index += 1
    left = start
    right = length
    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    if left < right:
        spans.append((left, right))
    return spans


def _balanced_sentence_spans(text: str) -> list[tuple[int, int]]:
    raw = _sentence_spans(text)
    balanced: list[tuple[int, int]] = []
    index = 0
    while index < len(raw):
        start, end = raw[index]
        while text[start:end].count("**") % 2 == 1 and index + 1 < len(raw):
            index += 1
            end = raw[index][1]
        balanced.append((start, end))
        index += 1
    return balanced


def parse_polish_response(raw: str, expected: int) -> list[dict]:
    text = strip_model_fence(raw).strip()
    if not text:
        raise _PolishResponseError("json")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise _PolishResponseError("json") from exc
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            raise _PolishResponseError("json") from exc
    if not isinstance(data, list):
        raise _PolishResponseError("json")
    if len(data) != expected:
        raise _PolishResponseError("count")
    rows: list[dict] = []
    seen: set[int] = set()
    for item in data:
        if not isinstance(item, dict) or "id" not in item or "text" not in item:
            raise _PolishResponseError("json")
        try:
            sentence_id = int(item["id"])
        except (TypeError, ValueError) as exc:
            raise _PolishResponseError("json") from exc
        if sentence_id in seen or not 1 <= sentence_id <= expected:
            raise _PolishResponseError("count")
        if not isinstance(item["text"], str):
            raise _PolishResponseError("json")
        merged = item.get("merged_with_next", False)
        if not isinstance(merged, bool):
            raise _PolishResponseError("json")
        seen.add(sentence_id)
        rows.append({"id": sentence_id, "text": item["text"], "merged_with_next": merged})
    if seen != set(range(1, expected + 1)):
        raise _PolishResponseError("count")
    rows.sort(key=lambda row: row["id"])
    return rows


_PLAIN_LANGUAGE: dict | None = None


def _string_list(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        raise PublishError("쉬운 말 사전의 예외 목록 형식이 잘못되었습니다.")
    return sorted(set(items), key=len, reverse=True)


def _load_plain_language() -> dict:
    global _PLAIN_LANGUAGE
    if _PLAIN_LANGUAGE is not None:
        return _PLAIN_LANGUAGE
    path = Path(__file__).resolve().parent / "config" / "plain_language.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublishError(f"쉬운 말 사전을 읽지 못했습니다: {path}") from exc
    if not isinstance(raw, dict):
        raise PublishError("쉬운 말 사전은 JSON 객체여야 합니다.")
    replacements_raw = raw.get("replacements")
    patterns_raw = raw.get("patterns")
    if not isinstance(replacements_raw, list) or not isinstance(patterns_raw, list):
        raise PublishError("쉬운 말 사전에는 replacements와 patterns가 있어야 합니다.")
    replacements: list[dict] = []
    for item in replacements_raw:
        if not isinstance(item, dict):
            raise PublishError("쉬운 말 사전 항목 형식이 잘못되었습니다.")
        term = str(item.get("term") or "").strip()
        suggestion = str(item.get("suggestion") or "").strip()
        if not term or not suggestion:
            raise PublishError("쉬운 말 사전 항목에는 term과 suggestion이 필요합니다.")
        replacements.append(
            {
                "term": term,
                "suggestion": suggestion,
                "not_followed_by": _string_list(item.get("not_followed_by")),
                "not_preceded_by": _string_list(item.get("not_preceded_by")),
            }
        )
    replacements.sort(key=lambda entry: len(entry["term"]), reverse=True)
    patterns: list[dict] = []
    for item in patterns_raw:
        if not isinstance(item, dict):
            raise PublishError("쉬운 말 패턴 형식이 잘못되었습니다.")
        pattern = str(item.get("pattern") or "").strip()
        suggestion = str(item.get("suggestion") or "").strip()
        if not pattern or not suggestion:
            raise PublishError("쉬운 말 패턴에는 pattern과 suggestion이 필요합니다.")
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            raise PublishError(f"쉬운 말 패턴을 해석하지 못했습니다: {pattern}") from exc
        patterns.append({"pattern": pattern, "suggestion": suggestion, "compiled": compiled})
    _PLAIN_LANGUAGE = {"replacements": replacements, "patterns": patterns}
    return _PLAIN_LANGUAGE


def _dictionary_for_prompt() -> list[dict]:
    rows: list[dict] = []
    for entry in _load_plain_language()["replacements"]:
        row: dict = {"term": entry["term"], "suggestion": entry["suggestion"]}
        if entry["not_followed_by"]:
            row["not_followed_by"] = entry["not_followed_by"]
        if entry["not_preceded_by"]:
            row["not_preceded_by"] = entry["not_preceded_by"]
        rows.append(row)
    return rows


def _longest_affix(text: str, index: int, affixes: list[str], *, at_end: bool) -> str:
    """at_end이면 index 앞에서 끝나는 접사, 아니면 index에서 시작하는 접사를 고른다."""
    best = ""
    for affix in affixes:
        matched = text[:index].endswith(affix) if at_end else text.startswith(affix, index)
        if matched and len(affix) > len(best):
            best = affix
    return best


def _forbidden_context(text: str, start: int, end: int, entry: dict) -> bool:
    if _longest_affix(text, end, entry.get("not_followed_by") or [], at_end=False):
        return True
    if _longest_affix(text, start, entry.get("not_preceded_by") or [], at_end=True):
        return True
    return False


def _apply_dictionary(text: str) -> str:
    """금지 문맥이 아닌 사전 용어를 제안 표현으로 바꾼 문자열.

    고유명사 검사는 이 결과를 비교해, 사전 치환으로 생기는 시·청 같은 끝글자를
    기관 이름으로 오인하지 않는다. 치환 밖에 있는 이름은 그대로 비교한다.
    """
    entries = _load_plain_language()["replacements"]
    occupied = [False] * len(text)
    spans: list[tuple[int, int, str]] = []
    for entry in entries:
        term = entry["term"]
        start = 0
        while True:
            index = text.find(term, start)
            if index < 0:
                break
            end = index + len(term)
            if any(occupied[index:end]) or _forbidden_context(text, index, end, entry):
                start = index + 1
                continue
            for pos in range(index, end):
                occupied[pos] = True
            spans.append((index, end, entry["suggestion"]))
            start = end
    parts: list[str] = []
    cursor = 0
    for start, end, suggestion in sorted(spans):
        parts.append(text[cursor:start])
        parts.append(suggestion)
        cursor = end
    parts.append(text[cursor:])
    return "".join(parts)


def _guarded_collocations(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for entry in _load_plain_language()["replacements"]:
        followed = entry["not_followed_by"]
        preceded = entry["not_preceded_by"]
        if not followed and not preceded:
            continue
        term = entry["term"]
        start = 0
        while True:
            index = text.find(term, start)
            if index < 0:
                break
            end = index + len(term)
            follower = _longest_affix(text, end, followed, at_end=False)
            leader = _longest_affix(text, index, preceded, at_end=True)
            if follower or leader:
                counts[f"{leader}{term}{follower}"] += 1
            start = index + 1
    return counts


def _is_dictionary_substitution(original: str, polished: str) -> bool:
    """polished가 original의 사전 치환만으로 만들어지면 True."""
    entries = _load_plain_language()["replacements"]
    index = 0
    other = 0
    changed = False
    while index < len(original) and other < len(polished):
        substituted = False
        for entry in entries:
            term = entry["term"]
            suggestion = entry["suggestion"]
            if term == suggestion:
                continue
            if not original.startswith(term, index) or not polished.startswith(suggestion, other):
                continue
            if _forbidden_context(original, index, index + len(term), entry):
                continue
            index += len(term)
            other += len(suggestion)
            changed = True
            substituted = True
            break
        if substituted:
            continue
        if original[index] != polished[other]:
            return False
        index += 1
        other += 1
    return changed and index == len(original) and other == len(polished)


def _bold_change_is_dictionary_substitution(original: str, polished: str) -> bool:
    if original.count("**") != polished.count("**"):
        return False
    orig_spans = _BOLD_SPAN_RE.findall(original)
    pol_spans = _BOLD_SPAN_RE.findall(polished)
    if len(orig_spans) != len(pol_spans):
        return False
    changed = False
    for orig, pol in zip(orig_spans, pol_spans):
        if orig == pol:
            continue
        if Counter(_NUMBER_RE.findall(orig)) != Counter(_NUMBER_RE.findall(pol)):
            return False
        if not _is_dictionary_substitution(orig, pol):
            return False
        changed = True
    return changed


def plain_language_flags(markdown: str) -> list[dict]:
    """본문에서 공문서 용어와 추상 문장을 찾는다.

    프론트매터, 출처, 표, 코드, 고지 문장은 건너뛴다. 제목은 포함한다.
    """
    loaded = _load_plain_language()
    entries = loaded["replacements"]
    patterns = loaded["patterns"]
    front = _FRONT_MATTER_RE.match(markdown)
    body_start = front.end() if front else 0
    sources_at = _sources_start(markdown, body_start)
    body_end = sources_at if sources_at is not None else len(markdown)
    flags: list[dict] = []
    lines = _line_spans(markdown)
    index = 0
    while index < len(lines):
        start, _end, raw_line = lines[index]
        if start < body_start or start >= body_end:
            index += 1
            continue
        newline_len = len(raw_line) - len(raw_line.rstrip("\r\n"))
        content = raw_line[: len(raw_line) - newline_len] if newline_len else raw_line
        stripped = content.strip()
        if stripped.startswith("```"):
            index += 1
            while index < len(lines) and lines[index][0] < body_end:
                fence_line = lines[index][2].strip()
                index += 1
                if fence_line.startswith("```"):
                    break
            continue
        if stripped.startswith("|"):
            index += 1
            while index < len(lines) and lines[index][0] < body_end and lines[index][2].strip().startswith("|"):
                index += 1
            continue
        if not stripped:
            index += 1
            continue
        line_no = markdown.count("\n", 0, start) + 1
        payload = content
        heading = re.match(r"^(#{1,6}\s+)(\S.*)$", content)
        if heading:
            payload = heading.group(2)
        else:
            marker = _LIST_MARKER_RE.match(content)
            if marker:
                payload = marker.group(2)
        for rel_start, rel_end in _balanced_sentence_spans(payload):
            sentence = payload[rel_start:rel_end]
            if _is_disclaimer_text(sentence):
                continue
            flags.extend(_flags_in_sentence(sentence, line_no, entries, patterns))
        index += 1
    return flags


def _flags_in_sentence(
    sentence: str,
    line_no: int,
    entries: list[dict],
    patterns: list[dict],
) -> list[dict]:
    occupied = [False] * len(sentence)
    matches: list[tuple[int, int, str, str]] = []
    for entry in entries:
        term = entry["term"]
        start = 0
        while True:
            index = sentence.find(term, start)
            if index < 0:
                break
            end = index + len(term)
            if any(occupied[index:end]) or _forbidden_context(sentence, index, end, entry):
                start = index + 1
                continue
            for pos in range(index, end):
                occupied[pos] = True
            matches.append((index, end, term, entry["suggestion"]))
            start = end
    for pattern in patterns:
        for match in pattern["compiled"].finditer(sentence):
            start, end = match.span()
            if start == end or any(occupied[start:end]):
                continue
            for pos in range(start, end):
                occupied[pos] = True
            matches.append((start, end, match.group(0), pattern["suggestion"]))
    matches.sort(key=lambda item: item[0])
    return [
        {
            "term": term,
            "suggestion": suggestion,
            "excerpt": _plain_excerpt(sentence, start, end),
            "line": line_no,
        }
        for start, end, term, suggestion in matches
    ]


def _plain_excerpt(sentence: str, start: int, end: int, limit: int = 140) -> str:
    text = re.sub(r"\s+", " ", sentence).strip()
    if len(text) <= limit:
        return text
    term = sentence[start:end]
    normalized = text.find(term)
    if normalized < 0:
        return text[: limit - 1] + "…"
    left = max(0, normalized - 40)
    right = min(len(text), normalized + len(term) + 40)
    excerpt = text[left:right].strip()
    if left > 0:
        excerpt = "…" + excerpt
    if right < len(text):
        excerpt = excerpt + "…"
    return excerpt


def _line_has_plain_flag(content: str, line_no: int, flags: list[dict]) -> bool:
    for flag in flags:
        term = str(flag.get("term") or "")
        if flag.get("line") == line_no and term and term in content:
            return True
    return False


def _sentence_has_plain_flag(sentence: str, line_no: int, flags: list[dict]) -> bool:
    for flag in flags:
        term = str(flag.get("term") or "")
        if flag.get("line") == line_no and term and term in sentence:
            return True
    return False


def _emit_plain_language(flags: list[dict]) -> None:
    print(
        "PLAIN_LANG_FLAGS: " + json.dumps(flags, ensure_ascii=False, separators=(",", ":")),
        flush=True,
    )
    if flags:
        print(f"PLAIN_LANG_STATUS: flags={len(flags)}", flush=True)
    else:
        print("PLAIN_LANG_STATUS: ok", flush=True)


def sentence_reject_reason(original: str, polished: str) -> str | None:
    """다듬은 문장을 버릴 이유. 통과하면 None."""
    if original == polished:
        return None
    if not polished.strip():
        return "문장 길이가 허용 범위를 벗어났습니다."
    if Counter(_NUMBER_RE.findall(original)) != Counter(_NUMBER_RE.findall(polished)):
        return "숫자가 바뀌었습니다."
    bold_changed = (
        original.count("**") != polished.count("**")
        or Counter(_BOLD_SPAN_RE.findall(original)) != Counter(_BOLD_SPAN_RE.findall(polished))
    )
    if bold_changed and not _bold_change_is_dictionary_substitution(original, polished):
        return "굵은 글씨가 바뀌었습니다."
    if _bold_closer_breaks_commonmark(polished):
        return "굵은 표시가 문장 부호에 붙어 있습니다."
    for term in POLISH_BLOCKLIST:
        if term in polished and term not in original:
            return "원문에 없는 행정 용어가 있습니다."
    if Counter(_proper_stems(_apply_dictionary(original))) != Counter(_proper_stems(_apply_dictionary(polished))):
        return "고유명사가 바뀌었습니다."
    if len(original) == 0 or not (
        POLISH_LENGTH_MIN <= len(polished) / len(original) <= POLISH_LENGTH_MAX
    ):
        return "문장 길이가 허용 범위를 벗어났습니다."
    for marker in POLISH_CERTAINTY_MARKERS:
        if marker in original and marker not in polished:
            return "확실함의 정도가 바뀌었습니다."
    if Counter(_direction_stems(original)) != Counter(_direction_stems(polished)):
        return "방향·위치 표현이 바뀌었습니다."
    if _guarded_collocations(original) != _guarded_collocations(polished):
        return "사전에서 예외로 둔 단어를 바꿨습니다."
    return None


def _bold_closer_breaks_commonmark(text: str) -> bool:
    """닫는 ** 앞에 문장 부호가 있고 뒤에 글자가 오면 CommonMark에서 굵은 글씨가 깨진다."""
    positions = [match.start() for match in re.finditer(r"\*\*", text)]
    for index, start in enumerate(positions):
        if index % 2 == 0:
            continue
        prev = text[start - 1] if start else ""
        nxt = text[start + 2] if start + 2 < len(text) else ""
        if prev and unicodedata.category(prev).startswith("P") and nxt.isalpha():
            return True
    return False


def _strip_particle(token: str) -> str:
    for particle in _PROPER_PARTICLES:
        if token.endswith(particle) and len(token) > len(particle):
            return token[: -len(particle)]
    return token


def _proper_stems(text: str) -> list[str]:
    plain = text.replace("**", "")
    stems: list[str] = []
    for match in _HANGUL_TOKEN_RE.finditer(plain):
        token = match.group(0)
        digits_len = len(token) - len(token.lstrip("0123456789"))
        digits = token[:digits_len]
        hangul = token[digits_len:]
        stem = _strip_particle(hangul)
        if any(stem.endswith(suffix) for suffix in _PROPER_SUFFIXES):
            stems.append(digits + stem)
            continue
        if any(hangul.endswith(suffix) for suffix in _PROPER_SUFFIXES):
            stems.append(token)
    for match in _LATIN_TOKEN_RE.finditer(plain):
        stems.append(match.group(0))
    return stems


def _direction_stems(text: str) -> list[str]:
    plain = text.replace("**", "")
    found: list[str] = []
    for token in _HANGUL_TOKEN_RE.findall(plain):
        hangul = token.lstrip("0123456789")
        if hangul in POLISH_DIRECTION_WORDS:
            found.append(hangul)
            continue
        stem = _strip_particle(hangul)
        if stem in POLISH_DIRECTION_WORDS:
            found.append(stem)
    return found


def _sentence_has_literal_bold(text: str) -> bool:
    try:
        html = markdown_to_html(text)
    except PublishError:
        return True
    return "**" in html


def _literal_bold_count(text: str) -> int:
    try:
        html = markdown_to_html(text)
    except PublishError:
        return text.count("**")
    return html.count("**")


def _can_merge_sentences(markdown: str, left: PolishSentence, right: PolishSentence) -> bool:
    if right.start < left.end:
        return False
    between = markdown[left.end : right.start]
    return "\n" not in between and between.strip() == ""


def _apply_span_replacements(original: str, replacements: list[tuple[int, int, str]]) -> str:
    parts: list[str] = []
    cursor = 0
    for start, end, text in sorted(replacements):
        if start < cursor or end < start:
            continue
        parts.append(original[cursor:start])
        parts.append(text)
        cursor = end
    parts.append(original[cursor:])
    return "".join(parts)


def apply_polish_rows(
    markdown: str,
    sentences: list[PolishSentence],
    rows: list[dict],
    protected_units: int,
    model_name: str,
) -> tuple[str, dict]:
    by_id = {row["id"]: row for row in rows}
    replacements: list[tuple[int, int, str]] = []
    applied = 0
    reverted = 0
    unchanged = 0
    reverts: list[dict] = []
    index = 0
    while index < len(sentences):
        current = sentences[index]
        row = by_id[current.id]
        nxt = sentences[index + 1] if index + 1 < len(sentences) else None
        next_row = by_id[nxt.id] if nxt else None
        merge = bool(
            row["merged_with_next"]
            and nxt is not None
            and next_row is not None
            and not next_row["merged_with_next"]
            and _can_merge_sentences(markdown, current, nxt)
        )
        if merge and nxt is not None:
            original = markdown[current.start : nxt.end]
            candidate = row["text"].strip()
            reason = None if candidate == original else sentence_reject_reason(original, candidate)
            if candidate == original:
                unchanged += 2
            elif reason or _sentence_has_literal_bold(candidate):
                reverted += 2
                reverts.append({"id": current.id, "reason": reason or "굵은 표시가 렌더링되지 않았습니다."})
                reverts.append({"id": nxt.id, "reason": "앞 문장과 합치기가 거절되었습니다."})
            else:
                applied += 2
                replacements.append((current.start, nxt.end, candidate))
            index += 2
            continue
        candidate = row["text"].strip()
        if candidate == current.text:
            unchanged += 1
        else:
            reason = sentence_reject_reason(current.text, candidate)
            if reason or _sentence_has_literal_bold(candidate):
                reverted += 1
                reverts.append({"id": current.id, "reason": reason or "굵은 표시가 렌더링되지 않았습니다."})
            else:
                applied += 1
                replacements.append((current.start, current.end, candidate))
        index += 1

    assembled = _apply_span_replacements(markdown, replacements)
    if _literal_bold_count(assembled) > _literal_bold_count(markdown):
        print(
            "다듬은 글을 렌더링했더니 굵은 표시가 그대로 남아 적용한 문장을 되돌립니다.",
            file=sys.stderr,
        )
        for start, end, _text in replacements:
            for sentence in sentences:
                if start <= sentence.start and sentence.end <= end:
                    reverts.append({"id": sentence.id, "reason": "굵은 표시가 렌더링되지 않았습니다."})
        reverted += applied
        applied = 0
        assembled = markdown
        replacements = []

    summary = {
        "status": "ok",
        "model": model_name,
        "applied": applied,
        "reverted": reverted,
        "kept": protected_units + unchanged,
        "reverts": reverts,
    }
    if applied:
        print(
            f"문체 다듬기: 적용 {applied}문장, 되돌림 {reverted}문장, 유지 {summary['kept']}구간, 모델 {model_name}",
            file=sys.stderr,
        )
    elif reverted:
        print(
            f"문체 다듬기: 되돌림 {reverted}문장, 유지 {summary['kept']}구간, 모델 {model_name}",
            file=sys.stderr,
        )
    return assembled, summary


def _emit_polish_error(reason: str, detail: str) -> None:
    print(f"문체 다듬기를 적용하지 못했습니다. 원문을 유지합니다. 이유: {detail}", file=sys.stderr)
    _emit_polish_status({"status": "error", "reason": reason, "detail": detail})


def _emit_polish_status(payload: dict) -> None:
    if payload.get("status") == "ok":
        line = (
            f"POLISH_STATUS: ok model={payload['model']} "
            f"applied={payload['applied']} reverted={payload['reverted']} kept={payload['kept']}"
        )
    else:
        line = f"POLISH_STATUS: error reason={payload.get('reason', 'api')}"
    print(line, flush=True)
    print("POLISH_SUMMARY: " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)


def _polish_model_names() -> tuple[str, ...]:
    """문체 다듬기 모델. GEMINI_POLISH_MODELS가 있으면 그것을, 없으면 GEMINI_MODELS를 쓴다."""
    raw = os.environ.get("GEMINI_POLISH_MODELS", "")
    if not raw.strip():
        raw = os.environ.get("GEMINI_MODELS", "")
    names = tuple(part.strip() for part in raw.split(",") if part.strip())
    return names or POLISH_GEMINI_MODELS


def call_polish_models(api_key: str, system_prompt: str, user_prompt: str) -> tuple[str, str]:
    """목록의 첫 모델로 한 번 요청한다.

    429, RESOURCE_EXHAUSTED, 일일 할당량이면 같은 요청을 다음 모델로 한 번만 다시 보낸다.
    그 폴백도 할당량으로 실패하면 더 시도하지 않는다.
    모델을 찾을 수 없는 경우에는 지금까지처럼 목록의 다음 모델로 넘어간다.
    """
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise PublishError(
            "google-generativeai 라이브러리가 없습니다. pip install -r requirements.txt 를 실행하세요."
        ) from exc

    genai.configure(api_key=api_key)
    names = _polish_model_names()
    errors: list[str] = []
    quota_fallback_used = False
    for index, name in enumerate(names):
        print(
            f"Gemini 모델 {name}로 문체 다듬기를 요청합니다. ({index + 1}/{len(names)})",
            file=sys.stderr,
        )
        try:
            text = _generate_polish(genai, name, system_prompt, user_prompt)
        except Exception as exc:  # noqa: BLE001 - 모델별 실패는 다음 모델로 넘긴다.
            errors.append(f"{name}: {exc}")
            if _is_quota_or_rate_limit(exc):
                if quota_fallback_used or index + 1 >= len(names):
                    print(
                        "Gemini 할당량 또는 속도 제한입니다. 폴백 모델을 더 시도하지 않습니다.",
                        file=sys.stderr,
                    )
                    raise PolishModelError(
                        "api",
                        "Gemini 할당량 또는 속도 제한으로 문체 다듬기를 중단합니다.",
                    ) from exc
                quota_fallback_used = True
                print(
                    f"Gemini 모델 {name}가 할당량 또는 속도 제한(429)입니다. "
                    f"같은 요청을 폴백 모델 {names[index + 1]}로 한 번만 다시 보냅니다. 원인: {exc}",
                    file=sys.stderr,
                )
                continue
            if index + 1 >= len(names):
                break
            if _is_model_unavailable_message(exc):
                print(
                    f"Gemini 모델 {name}를 사용할 수 없습니다. "
                    f"다시 호출하지 않고 다음 모델 {names[index + 1]}로 넘어갑니다. 원인: {exc}",
                    file=sys.stderr,
                )
            else:
                print(
                    f"Gemini 모델 {name} 요청이 실패했습니다. "
                    f"다음 모델 {names[index + 1]}로 넘어갑니다. 원인: {exc}",
                    file=sys.stderr,
                )
            continue
        print(f"문체 다듬기 최종 사용 모델: {name}", file=sys.stderr)
        return name, text
    detail = errors[-1] if errors else "응답이 없습니다."
    raise PolishModelError("api", f"Gemini 문체 다듬기 호출에 실패했습니다: {detail}")


def _generate_polish(genai: object, name: str, system_prompt: str, user_prompt: str) -> str:
    model = genai.GenerativeModel(name, system_instruction=system_prompt)  # type: ignore[attr-defined]
    response = model.generate_content(
        user_prompt,
        generation_config={
            "temperature": 0.2,
            "max_output_tokens": 16384,
            "response_mime_type": "application/json",
        },
    )
    try:
        text = response.text
    except ValueError as exc:
        raise PublishError(f"Gemini 응답을 읽지 못했습니다: {exc}") from exc
    if not text or not str(text).strip():
        raise PublishError("Gemini가 빈 응답을 반환했습니다.")
    return str(text)


def _is_quota_or_rate_limit(exc: Exception) -> bool:
    """429, RESOURCE_EXHAUSTED, 일일·분당 할당량."""
    if type(exc).__name__ in {"ResourceExhausted", "TooManyRequests"}:
        return True
    if getattr(exc, "code", None) == 429 or getattr(exc, "status_code", None) == 429:
        return True
    text = str(exc).lower().replace("_", " ").replace("-", " ")
    if "resource exhausted" in text:
        return True
    if "per day" in text or "perday" in text or "per minute" in text or "perminute" in text:
        return True
    if "rate limit" in text or "too many requests" in text or "quota" in text:
        return True
    return re.search(r"\b429\b", text) is not None


def _is_daily_quota_message(exc: Exception) -> bool:
    text = str(exc).lower()
    return "per day" in text or "perday" in text


def _is_model_unavailable_message(exc: Exception) -> bool:
    if type(exc).__name__ == "NotFound" or getattr(exc, "code", None) == 404:
        return True
    text = str(exc).lower().replace("_", " ")
    return "not found" in text or "not available" in text


def call_gemini(api_key: str, prompt: str, *, max_output_tokens: int = 8192) -> str:
    try:
        import google.generativeai as genai
        from google.api_core.exceptions import ResourceExhausted
    except ImportError as exc:
        raise PublishError(
            "google-generativeai 라이브러리가 없습니다. pip install -r requirements.txt 를 실행하세요."
        ) from exc

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    def generate() -> str:
        try:
            response = model.generate_content(
                prompt,
                generation_config={"temperature": 0.2, "max_output_tokens": max_output_tokens},
            )
        except ResourceExhausted:
            raise
        except Exception as exc:  # noqa: BLE001 - API 오류를 게시 실패로 알린다.
            raise PublishError(f"Gemini 호출에 실패했습니다: {exc}") from exc
        try:
            text = response.text
        except ValueError as exc:
            raise PublishError(f"Gemini 응답을 읽지 못했습니다: {exc}") from exc
        if not text or not text.strip():
            raise PublishError("Gemini가 빈 응답을 반환했습니다.")
        return strip_model_fence(text)

    try:
        return generate()
    except ResourceExhausted as exc:
        if not _is_transient_rpm_limit(exc):
            raise PublishError("Gemini 할당량을 초과했습니다. 재시도하지 않고 중단합니다.") from exc
        wait = _rpm_wait_seconds(exc)
        print(f"Gemini 분당 한도입니다. {wait:.0f}초 후 한 번만 다시 요청합니다.", file=sys.stderr)
        time.sleep(wait)
        try:
            return generate()
        except ResourceExhausted as retry_exc:
            raise PublishError("Gemini 분당 한도가 한 번 더 발생해 중단합니다.") from retry_exc


def strip_model_fence(text: str) -> str:
    stripped = text.strip()
    match = _FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def _retry_after_seconds(exc: Exception) -> float | None:
    match = _RETRY_AFTER_RE.search(str(exc))
    if not match:
        return None
    return float(match.group(1))


def _is_transient_rpm_limit(exc: Exception) -> bool:
    text = str(exc).lower()
    if "per day" in text or "perday" in text:
        return False
    if "per minute" in text or "perminute" in text:
        return True
    hint = _retry_after_seconds(exc)
    return hint is not None and hint <= 120


def _rpm_wait_seconds(exc: Exception) -> float:
    hint = _retry_after_seconds(exc)
    if hint is None:
        return float(GEMINI_RPM_MIN_WAIT_SECONDS)
    return float(max(GEMINI_RPM_MIN_WAIT_SECONDS, int(hint + 0.999)))


def cover_summary_line(cover: str) -> str:
    if cover:
        return f"표지: {cover}"
    return "표지: 없음 (분류 기본 이미지 사용)"


def print_polished_markdown(markdown: str) -> None:
    """검증 실행의 잡 로그에서 다듬은 글 전체를 복사할 수 있게 표시합니다."""
    print("=== POLISHED START ===", flush=True)
    print(markdown.rstrip("\n"), flush=True)
    print("=== POLISHED END ===", flush=True)


def print_summary(
    root: Path,
    destination: Path,
    slug: str,
    title: str,
    category: str,
    date: str,
    description: str,
    length: int,
    related_count: int,
    cover: str,
    dry_run: bool,
    push: bool,
) -> None:
    try:
        shown = destination.relative_to(root).as_posix()
    except ValueError:
        shown = destination.as_posix()
    if dry_run:
        print("검증만 했습니다. 파일은 쓰지 않았습니다.")
    print(f"글 파일: {shown}")
    print(f"주소: {SITE_ORIGIN}/posts/{slug}/")
    print(f"제목: {title}")
    print(f"분류: {category}")
    print(f"날짜: {date}")
    print(cover_summary_line(cover))
    print(f"설명: {description}")
    print(f"본문 글자 수: {length}")
    print(f"관련 글: {related_count}")
    if dry_run:
        print("푸시: 하지 않음")
    else:
        print("푸시: 요청함" if push else "푸시: 하지 않음")


def git_commit_and_push(root: Path, paths: list[Path], title: str) -> None:
    git_root = find_git_root(root)
    relatives = [path.resolve().relative_to(git_root).as_posix() for path in paths]
    branch = git_output(git_root, ["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
    if branch in {"", "HEAD"}:
        raise PublishError("분리된 HEAD에서는 푸시하지 않습니다.")
    status = git_output(git_root, ["git", "status", "--porcelain", "--", *relatives])
    if not status.strip():
        print("변경이 없어 커밋하지 않습니다.")
        return
    ensure_git_identity(git_root)
    run_git(git_root, ["git", "add", "--", *relatives])
    message = "글 게시: " + " ".join(title.split())
    run_git(git_root, ["git", "commit", "-m", message, "--", *relatives])
    print(f"푸시 대상 브랜치: {branch}")
    run_git(git_root, push_command(branch))


def push_command(branch: str) -> list[str]:
    if not branch or branch == "HEAD" or branch.startswith("-"):
        raise PublishError(f"푸시할 브랜치 이름이 올바르지 않습니다: {branch}")
    return ["git", "push", "origin", f"HEAD:refs/heads/{branch}"]


def find_git_root(start: Path) -> Path:
    for candidate in [start.resolve(), *start.resolve().parents]:
        if (candidate / ".git").exists():
            return candidate
    raise PublishError("git 저장소가 아니어서 푸시할 수 없습니다.")


def ensure_git_identity(git_root: Path) -> None:
    defaults = {
        "user.email": "blog-auto-pilot@users.noreply.github.com",
        "user.name": "Blog Auto Pilot",
    }
    for key, value in defaults.items():
        probe = subprocess.run(
            ["git", "config", "--get", key],
            cwd=git_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode != 0 or not probe.stdout.strip():
            run_git(git_root, ["git", "config", key, value])


def git_output(git_root: Path, command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=git_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise PublishError(detail or f"git 명령이 실패했습니다: {' '.join(command)}")
    return result.stdout


def run_git(git_root: Path, command: list[str]) -> None:
    result = subprocess.run(
        command,
        cwd=git_root,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise PublishError(detail or f"git 명령이 실패했습니다: {' '.join(command)}")


if __name__ == "__main__":
    sys.exit(main())
