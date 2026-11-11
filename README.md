# Blog-auto-pilot

Mallow Info Lab(https://blog.mymallow.cloud/)과, 글감 키워드를 고르는 파이프라인이 같은 저장소에 있습니다. 둘은 따로 동작합니다. 사이트 이름은 Mallow Info Lab입니다.

## Mallow Info Lab

목록 페이지 하나와, 글 하나당 HTML 한 장으로 이루어져 있습니다. 글쓰기 화면은 없습니다. 봇이 `content/posts`에 HTML 파일을 올리면 목록과 낱장 페이지가 같이 만들어집니다.

### 로컬에서 보기

```bash
npm install
npm run dev
```

개발 서버는 `3847` 포트(또는 `PORT`)에서 열립니다. HTML 파일을 저장한 뒤 새로고침하면 반영됩니다.

### 봇이 글을 올리는 방법

`content/posts/<slug>.html` 파일을 추가합니다. slug는 영문 소문자, 숫자, 하이픈만 씁니다.

```html
<script type="application/json" id="post-meta">
{
  "title": "글 제목",
  "category": "정부혜택",
  "date": "2026-11-10",
  "thumbnail": "/images/cover.jpg",
  "thumbnailAlt": "표지 설명",
  "links": [
    { "title": "다른 글 제목", "href": "/posts/other-slug/" },
    { "title": "[추천 툴] 도구 이름", "href": "https://example.com", "tone": "tool" }
  ]
}
</script>
<p>본문 HTML입니다. h2, 목록, 인용만 적어도 페이지 껍데기는 사이트가 붙입니다.</p>
```

봇이 넣는 것은 본문뿐입니다. 홈으로 돌아가기, 제목, 발행일, 광고 자리, “함께 읽으면 유용한 정보”는 템플릿이 붙입니다.

- `date`는 `YYYY-MM-DD`
- `thumbnail`은 `public/images`에 둔 파일의 경로(`/images/...`)이거나 `https` 주소
- `links[].tone`에 `"tool"`을 주면 파란 추천 툴 줄로 표시됩니다
- 본문의 스크립트, 이벤트 속성, `javascript:` 주소는 빌드할 때 제거됩니다
- 같은 파일에서 `thumbnail` 대신 `cover`, `links` 대신 `related`를 써도 읽습니다. `cover`가 비어 있으면 표지를 그리지 않습니다.

### 정적 HTML로 올리기

```bash
npm run export
```

`STATIC_EXPORT=1 next build`와 같습니다. `out/index.html`이 목록이고, `out/posts/<slug>/index.html`이 글 한 장입니다.

GitHub Pages 배포는 `.github/workflows/deploy-pages.yml`입니다.

- `main`에 사이트 소스 또는 이 워크플로가 푸시되면 실행됩니다. Actions 화면에서 수동 실행도 됩니다.
- 워크플로가 `npm run export`로 `out/`을 만들고, `actions/deploy-pages`로 게시합니다. 게시 루트에 `CNAME`(`blog.mymallow.cloud`)과 `.nojekyll`이 포함됩니다.
- 배포 방식은 GitHub Actions입니다. `gh-pages` 브랜치를 만들지 않습니다.
- 저장소 Pages 소스는 **GitHub Actions**여야 합니다. 한 번만 설정하면 이후 `main` 병합이 사이트를 갱신합니다.
- DNS는 별도입니다. `blog.mymallow.cloud` CNAME을 `jhjer010819.github.io`로 두고, Cloudflare 프록시는 끕니다.

광고 자리는 `NEXT_PUBLIC_ADSENSE_CLIENT`(`ca-pub-`로 시작), `NEXT_PUBLIC_ADSENSE_SLOT_TOP`, `NEXT_PUBLIC_ADSENSE_SLOT_BOTTOM`이 있을 때만 애드센스로 바뀝니다. 없으면 시안의 자리 표시가 남습니다. `ads.txt`는 두지 않습니다.

표지용 글꼴은 [Pretendard](https://github.com/orioncactus/pretendard) (SIL Open Font License)입니다. 라이선스 원문은 `public/fonts/LICENSE`에 있습니다.

키워드 워크플로(`.github/workflows/keyword_selector.yml`)는 이 배포를 호출하지 않고, 사이트 빌드도 Python 의존성을 설치하지 않습니다.

## 키워드 선별

`.github/workflows/keyword_selector.yml`이 매일 한국시간 06:00에 `main.py`를 실행합니다. Actions에서 수동 실행도 됩니다. `GEMINI_API_KEY` 시크릿이 필요합니다.

로컬 실행:

```bash
pip install -r requirements.txt
GEMINI_API_KEY=... python main.py
```
