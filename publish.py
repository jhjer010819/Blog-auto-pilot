"""마크다운 한 편을 Mallow Info Lab 글 파일로 바꿉니다.

이 저장소의 Next.js 앱이 `content/posts/<slug>.html`만 읽습니다.
파일은 post-meta JSON으로 시작하고 나머지는 본문 HTML입니다.
홈 링크, 제목, 날짜, 「함께 읽으면 유용한 정보」는 사이트가 붙입니다.
공개 주소는 https://blog.mymallow.cloud/posts/<slug>/ 입니다.
cover가 비어 있으면 게시 때 320×320 JPEG 표지를 만들어 public/images에 저장합니다.
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
import base64
import io
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
GEMINI_RPM_MIN_WAIT_SECONDS = 60
# Imagen is shut down on the Gemini API. Covers use Nano Banana via google-genai.
# 1K is the smallest billed output; the saved file is a compressed 320 JPEG.
COVER_IMAGE_MODEL = "gemini-nano-banana-2.1"
COVER_EDGE = 320
COVER_JPEG_MAX_BYTES = 20 * 1024
COVER_IMAGE_ATTEMPTS = 2
COVER_IMAGE_RETRY_SECONDS = 2.0
COVER_STEM_MAX = 40

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
_CASUAL_ENDING_RE = re.compile(r"(?:해요|이에요|예요|하죠|거든요|잖아요)(?=[.!?…\s]|$)")
_RETRY_AFTER_RE = re.compile(r"retry in\s+([0-9]+(?:\.[0-9]+)?)\s*s", re.IGNORECASE)
_FENCE_RE = re.compile(r"^```(?:markdown|md)?\s*\n(.*)\n```$", re.DOTALL)
_META_FILE_RE = re.compile(
    r'\A<script type="application/json" id="post-meta">\n(.*?)\n</script>\n(.*)\Z',
    re.DOTALL,
)
_GENERIC_SLUGS = {"post", "draft", "input", "inbox", "readme", "index"}
_COVER_STEM_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+){1,3}$")
_COVER_STEM_BANNED = frozenset({"cover", "image", "img", "photo", "thumbnail", "post", "blog"})
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
        help="표지 경로. 비우면 제목과 분류로 320×320 JPEG를 만들어 public/images에 저장합니다.",
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
            "Gemini로 문체만 다듬습니다. 사실, 숫자, 제목, 고지 문장, 표는 유지합니다. "
            "--dry-run과 함께 쓰면 다듬은 마크다운 전체를 표준 출력에 표시합니다."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="파일을 쓰지 않고 결과만 확인합니다.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="글 파일과, 이번 게시에 만든 표지 JPEG를 현재 브랜치에 커밋하고 푸시합니다. 기본값은 푸시하지 않습니다.",
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
    supplied_cover = supplied_cover.strip()

    full_markdown = f"# {title}\n\n{body.strip()}\n"
    if args.polish:
        full_markdown = polish_markdown(full_markdown)
        polished_title, body = split_h1(full_markdown)
        if polished_title != title:
            raise PublishError("문체 다듬기 과정에서 제목이 바뀌었습니다.")
        if not body.strip():
            raise PublishError("문체 다듬기 뒤 본문이 비었습니다.")
        if args.dry_run:
            print_polished_markdown(full_markdown)

    related = resolve_related(args, front_matter, root, slug, category)
    body_html = markdown_to_html(body)
    if not body_html.strip():
        raise PublishError("마크다운을 HTML로 바꾸지 못했습니다.")
    supplied_description = str(front_matter.get("description") or "").strip()
    if supplied_description and len(supplied_description) <= DESCRIPTION_HARD_MAX:
        description = supplied_description
    else:
        description = description_from_html(body_html)
    cover_path: Path | None = None
    cover_bytes: bytes | None = None
    if supplied_cover:
        cover = supplied_cover
        cover_plan = "supplied"
    elif args.dry_run:
        cover = ""
        cover_plan = "generate"
    else:
        cover, cover_path, cover_bytes = build_generated_cover(root, title, category)
        cover_plan = "generated"
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
        cover_plan,
        args.dry_run,
        args.push,
    )
    if args.dry_run:
        return None

    if cover_path is not None and cover_bytes is not None:
        cover_path.parent.mkdir(parents=True, exist_ok=True)
        cover_path.write_bytes(cover_bytes)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document_html, encoding="utf-8")
    if args.push:
        paths = [destination]
        if cover_path is not None:
            paths.append(cover_path)
        git_commit_and_push(root, paths, title)
    return destination


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


def polish_markdown(markdown: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise PublishError("GEMINI_API_KEY가 없습니다. --polish 를 쓰려면 환경 변수로 설정하세요.")
    problems: list[str] = []
    last = markdown
    for attempt in range(2):
        last = call_gemini(api_key, build_polish_prompt(markdown, problems, attempt))
        problems = validate_polish(markdown, last)
        if not problems:
            cleaned = last.strip()
            return cleaned if cleaned.endswith("\n") else cleaned + "\n"
        print(f"문체 다듬기 결과를 확인했습니다. 다시 요청합니다: {'; '.join(problems)}", file=sys.stderr)
    detail = "\n- ".join(problems)
    raise PublishError("문체 다듬기가 조건을 지키지 못했습니다.\n- " + detail)


def build_polish_prompt(markdown: str, problems: list[str], attempt: int) -> str:
    heading_block = "\n".join(headings_of(markdown)) or "(없음)"
    length = manuscript_length(markdown)
    retry = ""
    if problems:
        retry = "이전 시도에서 아래 조건을 어겼다. 같은 실수를 반복하지 마라.\n- " + "\n- ".join(problems) + "\n\n"
    attempt_note = f"이번 요청은 {attempt + 1}번째입니다.\n" if problems else ""
    return f"""너는 한국어 정보 글의 문장만 다듬는 편집자다. 사실 작성자가 아니다.

다듬을 것:
- AI가 쓴 듯한 상투적 표현
- 번역투
- 반복되는 맺음말

지키지 않으면 실패다:
- 새 사실, 기관, 수치, 사례, 예외를 만들지 마라. 있는 사실을 빼지 마라.
- 숫자와 단위를 바꾸거나 추가하거나 삭제하지 마라.
- 의학·정책 고지 문장은 글자 그대로 남겨라.
- 아래 제목은 기호(#)와 문구, 순서를 한 글자도 바꾸지 마라. 제목을 늘리거나 줄이지 마라.
- 표의 행을 늘리거나 줄이지 마라.
- 본문(첫 H1 제목 줄과 줄바꿈 제외, 공백 포함)은 {MIN_BODY_CHARS}~{MAX_BODY_CHARS}자를 유지하라. 현재 {length}자다.
- 분량을 맞추려고 사실을 지어내지 마라. 이미 있는 문장을 다듬어 맞춰라.
- 어미는 합니다/입니다 체를 유지하라. 해요체로 바꾸지 마라.
- 출력은 다듬은 마크다운만 써라. 설명, 코드 펜스, 사과는 붙이지 마라.

{attempt_note}{retry}고정 제목:
{heading_block}

원문:
{markdown}
"""


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


def build_generated_cover(root: Path, title: str, category: str) -> tuple[str, Path, bytes]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise PublishError(
            "GEMINI_API_KEY가 없습니다. 표지를 만들려면 환경 변수로 설정하거나 --cover 로 경로를 지정하세요."
        )
    stem = request_cover_stem(api_key, title, category)
    path = allocate_cover_path(root / "public" / "images", stem)
    raw = fetch_cover_image_bytes(api_key, build_cover_prompt(title, category))
    return f"/images/{path.name}", path, normalize_cover_jpeg(raw)


def build_cover_prompt(title: str, category: str) -> str:
    return (
        "Create a square cinematic editorial photograph for a Korean information blog. "
        "Use the title and category only as the subject of the scene. "
        f"Category: {category}. Title: {title}. "
        "Photorealistic, quiet, natural light, shallow depth of field, like a stock photograph. "
        "No readable text, letters, numbers, logos, watermarks, or brand names. "
        "No real-school insignia, military insignia, uniforms with badges, or weapons. "
        "Not an infographic, poster, diagram, collage, or clickbait thumbnail."
    )


def request_cover_stem(api_key: str, title: str, category: str) -> str:
    problems: list[str] = []
    for _attempt in range(2):
        raw = call_gemini(
            api_key,
            build_cover_stem_prompt(title, category, problems),
            max_output_tokens=64,
        )
        try:
            return validate_cover_stem(normalize_cover_stem(raw))
        except PublishError as exc:
            problems = [str(exc)]
            print(f"표지 파일 이름을 다시 요청합니다: {exc}", file=sys.stderr)
    raise PublishError("표지 파일 이름을 만들지 못했습니다. 짧은 영문 이름을 받지 못했습니다.")


def build_cover_stem_prompt(title: str, category: str, problems: list[str]) -> str:
    retry = ""
    if problems:
        retry = "이전 답은 거절되었다: " + " ".join(problems) + "\n다시 짧은 영문 케밥만 답하라.\n"
    return (
        "블로그 표지 파일 이름의 영문 슬러그만 한 줄로 답하라.\n"
        "조건:\n"
        "- 영어 단어 2~4개를 하이픈으로 잇는다. 예: youth-rent, year-end-tax\n"
        "- 소문자, 숫자, 하이픈만 사용한다. 확장자는 붙이지 않는다.\n"
        "- 한국어를 쓰지 않는다.\n"
        "- cover, image, photo, thumbnail, post, blog 는 쓰지 않는다.\n"
        "- 설명은 붙이지 않는다.\n\n"
        f"{retry}분류: {category}\n제목: {title}\n"
    )


def normalize_cover_stem(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    line = text.splitlines()[0].strip().strip("`\"'").lower()
    line = re.sub(r"\.jpe?g$", "", line).replace("_", "-").replace(" ", "-")
    match = re.search(r"[a-z0-9]+(?:-[a-z0-9]+){1,3}", line)
    stem = match.group(0) if match else re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9-]+", "-", line)).strip("-")
    if len(stem) > COVER_STEM_MAX:
        stem = stem[:COVER_STEM_MAX].rstrip("-")
        if "-" in stem:
            stem = stem.rsplit("-", 1)[0]
    return stem.strip("-")


def validate_cover_stem(stem: str) -> str:
    parts = stem.split("-") if stem else []
    if not _COVER_STEM_RE.fullmatch(stem) or any(part in _COVER_STEM_BANNED for part in parts):
        raise PublishError(f"표지 파일 이름이 짧고 영문 케밥 형식이 아닙니다: {stem or '(빈 값)'}")
    return stem


def allocate_cover_path(images_dir: Path, stem: str) -> Path:
    path = images_dir / f"{stem}.jpg"
    if not path.exists():
        return path
    for number in range(2, 51):
        suffix = f"-{number}"
        base = stem[: COVER_STEM_MAX - len(suffix)].rstrip("-")
        path = images_dir / f"{base}{suffix}.jpg"
        if not path.exists():
            return path
    raise PublishError("표지 파일 이름을 유일하게 만들지 못했습니다.")


def load_genai():
    try:
        from google import genai
    except ImportError as exc:
        raise PublishError(
            "google-genai 라이브러리가 없습니다. pip install -r requirements.txt 를 실행하세요."
        ) from exc
    return genai


def fetch_cover_image_bytes(api_key: str, prompt: str) -> bytes:
    client = load_genai().Client(api_key=api_key)
    last: Exception | None = None
    for attempt in range(COVER_IMAGE_ATTEMPTS):
        try:
            interaction = client.interactions.create(
                model=COVER_IMAGE_MODEL,
                input=prompt,
                response_format={
                    "type": "image",
                    "mime_type": "image/jpeg",
                    "aspect_ratio": "1:1",
                    "image_size": "1K",
                    "delivery": "inline",
                },
            )
            return cover_image_bytes(getattr(interaction, "output_image", None))
        except Exception as exc:  # noqa: BLE001 - 이미지 API 오류는 한 번 더 시도한다.
            last = exc
            if attempt + 1 >= COVER_IMAGE_ATTEMPTS:
                break
            wait = _cover_retry_wait(exc)
            print(f"표지 이미지 생성을 다시 시도합니다: {exc}", file=sys.stderr)
            time.sleep(wait)
    raise PublishError(f"표지 이미지를 만들지 못했습니다: {last}") from last


def cover_image_bytes(image: object) -> bytes:
    data = image.get("data") if isinstance(image, dict) else getattr(image, "data", None)
    if isinstance(data, str):
        payload = data.strip()
        if payload.startswith("data:") and "," in payload:
            payload = payload.split(",", 1)[1]
        if not payload:
            raise PublishError("표지 이미지 응답이 비어 있습니다.")
        try:
            decoded = base64.b64decode(payload, validate=False)
        except Exception as exc:
            raise PublishError("표지 이미지 데이터를 읽지 못했습니다.") from exc
        if not decoded:
            raise PublishError("표지 이미지 응답이 비어 있습니다.")
        return decoded
    if isinstance(data, (bytes, bytearray)):
        if not data:
            raise PublishError("표지 이미지 응답이 비어 있습니다.")
        return bytes(data)
    raise PublishError("표지 이미지 응답이 비어 있습니다.")


def _cover_retry_wait(exc: Exception) -> float:
    if _is_transient_rpm_limit(exc):
        return _rpm_wait_seconds(exc)
    return COVER_IMAGE_RETRY_SECONDS


def normalize_cover_jpeg(raw: bytes) -> bytes:
    try:
        from PIL import Image
    except ImportError as exc:
        raise PublishError(
            "Pillow 라이브러리가 없습니다. pip install -r requirements.txt 를 실행하세요."
        ) from exc
    try:
        with Image.open(io.BytesIO(raw)) as image:
            rgb = image.convert("RGB")
            if rgb.size != (COVER_EDGE, COVER_EDGE):
                rgb = rgb.resize((COVER_EDGE, COVER_EDGE), Image.Resampling.LANCZOS)
            best: bytes | None = None
            for quality in range(78, 19, -3):
                buffer = io.BytesIO()
                rgb.save(buffer, format="JPEG", quality=quality, optimize=True)
                data = buffer.getvalue()
                best = data
                if len(data) <= COVER_JPEG_MAX_BYTES:
                    return data
            if best is None:
                raise PublishError("표지 이미지를 JPEG로 바꾸지 못했습니다.")
            return best
    except PublishError:
        raise
    except Exception as exc:
        raise PublishError(f"표지 이미지를 JPEG로 바꾸지 못했습니다: {exc}") from exc


def cover_summary_line(cover: str, plan: str) -> str:
    if plan == "generate":
        return (
            "표지: 비어 있어 게시 시 320×320 JPEG를 생성합니다. "
            "검증 실행에서는 이미지 API를 호출하지 않고 파일도 쓰지 않습니다."
        )
    if cover:
        suffix = " (이번 게시에 생성함)" if plan == "generated" else ""
        return f"표지: {cover}{suffix}"
    return "표지: 없음"


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
    cover_plan: str,
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
    print(cover_summary_line(cover, cover_plan))
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
