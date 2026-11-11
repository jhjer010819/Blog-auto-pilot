# Blog-auto-pilot

3호 블로그 자동화 저장소입니다. 글 목록과 글 화면은 따로 만든 Mallow Info Lab(Next.js 정적 내보내기)이 담당합니다. 그 사이트 소스는 이 저장소에 없습니다. 2단계는 `content/posts/<slug>.html` 파일만 만듭니다.

## 1단계: 키워드 선별

```bash
python main.py
```

`.github/workflows/keyword_selector.yml`이 매일 아침과 수동 실행으로 `main.py`를 돌립니다. `GEMINI_API_KEY` 시크릿이 필요합니다.

## 2단계: 글 파일 만들기

`publish.py`는 마크다운을 Mallow Info Lab이 읽는 글 파일로 바꿉니다. 파일은 `post-meta` JSON으로 시작하고, 나머지는 본문 HTML입니다.

```html
<script type="application/json" id="post-meta">
{
  "title": "글 제목",
  "category": "건강",
  "date": "2026-11-10",
  "cover": "",
  "related": [{ "title": "다른 글", "href": "/posts/other-slug" }]
}
</script>
<p>본문</p>
```

사이트는 홈 링크, 제목, 날짜, 광고 영역, 「함께 읽으면 유용한 정보」를 직접 붙입니다. 이 스크립트는 그 화면을 만들지 않습니다. 같은 슬러그 파일을 다시 쓰면 그 파일만 갱신합니다.

날짜는 `YYYY-MM-DD`입니다. 관련 글을 지정하지 않으면 `content/posts`에 이미 있는 글 중 최신 3개의 링크를 넣습니다. 링크는 `/posts/<slug>`입니다.

### 로컬 실행

```bash
pip install -r requirements.txt
python publish.py path/to/post.md --category 건강
python publish.py path/to/post.md --category 건강 --dry-run
python publish.py path/to/post.md --category 건강 --polish
python publish.py path/to/post.md --category 건강 --push
```

경로를 생략하면 `inbox/post.md`를 읽습니다.

| 옵션 | 동작 |
| --- | --- |
| `--category` | 분류. front matter `category`가 있으면 생략할 수 있습니다. |
| `--slug` | 파일 이름. 없으면 파일명이나 제목에서 만듭니다. |
| `--date` | `YYYY-MM-DD`. 없으면 한국 표준시 오늘입니다. |
| `--cover` | 표지 경로. 없으면 빈 문자열입니다. |
| `--related "제목\|/posts/slug"` | 관련 글. 여러 번 지정할 수 있습니다. |
| `--no-related` | 관련 글을 비웁니다. |
| `--polish` | Gemini(`gemini-3.8-flash`)로 문체만 다듬습니다. `GEMINI_API_KEY`가 필요합니다. |
| `--dry-run` | 파일을 쓰지 않습니다. |
| `--push` | 이 글 파일만 현재 브랜치에 커밋하고 푸시합니다. |

`--push`를 주지 않으면 커밋과 푸시를 하지 않습니다. `--push`는 현재 브랜치에 일반 푸시만 하며, 강제 푸시는 하지 않습니다. `--dry-run`과 `--push`는 함께 쓸 수 없습니다.

`--polish`는 번역투와 반복되는 맺음말만 고칩니다. 숫자, H1/H2/H3, 표의 행, 의학·정책 고지 문장은 유지합니다. 본문이 이미 공백 포함 1800~2500자면 그 범위를 벗어나지 않아야 합니다. 맞추지 못하면 파일을 쓰지 않고 종료합니다.

앞부분에 간단한 front matter를 둘 수 있습니다.

```markdown
---
title: 글 제목
category: 건강
date: 2026-11-10
slug: post-slug
cover: ""
related:
  - title: 다른 글
    href: /posts/other-slug
---
```

### 깃허브 액션

`.github/workflows/publish_post.yml`은 **수동 실행만** 가능합니다. 일정 실행은 없습니다. 기본값은 파일을 쓰지 않고 푸시하지도 않습니다. 실제로 올리려면 `dry_run`을 끄고 `push`를 켜면 됩니다. `GEMINI_API_KEY`는 1단계와 같은 저장소 시크릿입니다.

## 배포

블로그 화면은 Mallow Info Lab 쪽에서 정적 파일로 내보내는 구조입니다. 이 저장소에 Vercel 프로젝트를 만들거나 DNS를 바꾸지는 않습니다.
