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

봇이 넣는 것은 본문뿐입니다. 홈으로 돌아가기, 제목, 발행일, “함께 읽으면 유용한 정보”는 글 템플릿이 붙입니다. 소개, 개인정보 처리방침, 이용약관으로 가는 하단 링크는 루트 레이아웃이 목록, 글, 없는 페이지, 앞으로 올라오는 글에 공통으로 붙입니다. 주소는 `/about/`, `/privacy/`, `/terms/`입니다.

- `date`는 `YYYY-MM-DD`
- `category`는 아래 「분류」의 아홉 가지 중 하나여야 합니다. 다른 값이면 빌드가 실패합니다.
- `thumbnail`은 `public/images`에 둔 파일의 경로(`/images/...`)이거나 `https` 주소
- `links[].tone`에 `"tool"`을 주면 파란 추천 툴 줄로 표시됩니다
- 본문의 스크립트, 이벤트 속성, `javascript:` 주소는 빌드할 때 제거됩니다
- 같은 파일에서 `thumbnail` 대신 `cover`, `links` 대신 `related`를 써도 읽습니다. `cover`가 비어 있으면 목록 카드는 분류 이름 앞 두 글자를 기본 이미지로 보여 줍니다.

### 정적 HTML로 올리기

```bash
npm run export
```

`STATIC_EXPORT=1 next build`와 같습니다. `out/index.html`이 목록이고, `out/posts/<slug>/index.html`이 글 한 장입니다.

GitHub Pages 배포는 `.github/workflows/deploy-pages.yml`입니다.

- `main`에 사이트 소스 또는 이 워크플로가 푸시되면 실행됩니다. `GITHUB_TOKEN`으로 푸시하면 이 `push` 트리거는 켜지지 않습니다. 글 게시 워크플로가 `main`에 푸시하면 `workflow_dispatch`로 이 배포를 직접 호출합니다. Actions 화면에서 수동 실행도 됩니다.
- 워크플로가 `npm run export`로 `out/`을 만들고, `actions/deploy-pages`로 게시합니다. 게시 루트에 `CNAME`(`blog.mymallow.cloud`)과 `.nojekyll`이 포함됩니다.
- 배포 방식은 GitHub Actions입니다. `gh-pages` 브랜치를 만들지 않습니다.
- 저장소 Pages 소스는 **GitHub Actions**여야 합니다. 한 번만 설정하면 이후 `main` 병합이 사이트를 갱신합니다.
- DNS는 별도입니다. `blog.mymallow.cloud` CNAME을 `jhjer010819.github.io`로 두고, Cloudflare 프록시는 끕니다.

`public/ads.txt`는 정적 내보내기 루트의 `ads.txt`가 되어 `https://blog.mymallow.cloud/ads.txt`로 게시됩니다. 애드센스 스크립트는 이 파일만으로 붙지 않습니다.

표지용 글꼴은 [Pretendard](https://github.com/orioncactus/pretendard) (SIL Open Font License)입니다. 라이선스 원문은 `public/fonts/LICENSE`에 있습니다.

키워드 워크플로(`.github/workflows/keyword_selector.yml`)는 이 배포를 호출하지 않고, 사이트 빌드도 Python 의존성을 설치하지 않습니다.

## 글 파일 만들기

`publish.py`는 마크다운을 `content/posts/<slug>.html`로 바꿉니다. 목록 화면이나 글 화면 HTML은 만들지 않습니다. 슬러그는 제목을 로마자로 옮긴 값이고, 주소는 `https://blog.mymallow.cloud/posts/<slug>/`입니다.

```bash
pip install -r requirements.txt
python publish.py path/to/post.md --category 정부혜택
python publish.py path/to/post.md --category 정부혜택 --dry-run
python publish.py path/to/post.md --category 정부혜택 --polish
python publish.py path/to/post.md --category 정부혜택 --push
```

경로를 생략하면 `inbox/post.md`를 읽습니다. `--polish`는 `GEMINI_API_KEY`가 있을 때 `gemini-3.8-flash`로 문체만 다듬습니다. 숫자, 제목, 표의 행, 의학·정책 고지, 공백 포함 1800~2500자 범위가 깨지면 파일을 쓰지 않습니다. `--push`를 주지 않으면 커밋과 푸시를 하지 않고, 강제 푸시도 하지 않습니다.

### 분류

분류는 글의 목적에 따라 아래 아홉 가지 중 하나만 고릅니다. 1단계가 키워드를 담아 둔 통 이름(`realtime_trending`, `fallback_sample`)은 분류가 아닙니다.

| 분류 | 어떤 글인가 |
| --- | --- |
| 교육 | 입학, 학교, 입시, 사관학교 |
| 건강 | 증상, 예방, 의학 정보 |
| 과학 | 원리나 현상의 설명. 건강 조언과 구분합니다 |
| IT | 앱, 소프트웨어, 디지털 기기 |
| 부동산 | 매매, 전세, 청약, 시세. 지원금 신청은 정부혜택입니다 |
| 정부혜택 | 지원금, 바우처, 혜택 신청. 예: 청년 월세 지원금 |
| 세금 | 연말정산, 공제, 신고 |
| 정책·제도 | 위에 속하지 않는 공식 규정이나 행정 기준 |
| 생활정보 | 일상·소비 정보. 예: 스타벅스 |

`publish.py`의 `--category`와 front matter `category`가 이 목록 밖이면 글을 만들지 않습니다. 사이트 post-meta의 `category`도 같은 목록만 받습니다.

설명문은 본문 첫 소제목 앞의 두 문장입니다. 관련 글을 `--related`나 front matter `related`로 적으면 그 목록을 그대로 씁니다. 적지 않으면 같은 분류의 다른 글 중 최신 3개의 `/posts/<slug>/` 링크를 넣습니다. 같은 분류 글이 하나라도 있으면 그 글만 넣고, 다른 분류로 채우지 않습니다. 같은 분류 글이 하나도 없을 때만 다른 분류의 최신 글 최대 3개로 대신합니다. 지금 올리는 글은 빼며, 추천 툴 링크는 자동으로 넣지 않습니다.

표지는 `--cover /images/name.jpg` 또는 front matter `cover`로 지정합니다. 그 이미지는 게시 전에 `public/images/name.jpg`로 저장소에 있어야 하고, 파일이 없으면 글을 만들지 않습니다. 표지를 비우면 API를 호출하지 않고 post-meta `cover`를 빈 문자열로 둡니다. 목록은 분류 이름 앞 두 글자를 기본 이미지로 보여 줍니다. `GEMINI_API_KEY`는 `--polish` 문체 다듬기에만 씁니다. `--push`는 글 HTML만 커밋합니다.

`.github/workflows/publish_post.yml`은 수동 실행만 됩니다. 기본값은 `dry_run: true`, `push: false`입니다. `push: true`로 `main`에 푸시하면, 이어서 `deploy-pages.yml`을 `main`에서 실행합니다. 다른 브랜치에 푸시하면 페이지 배포는 호출하지 않습니다.

## 키워드 선별

`.github/workflows/keyword_selector.yml`이 매일 한국시간 06:00에 `main.py`를 실행합니다. Actions에서 수동 실행도 됩니다. `GEMINI_API_KEY` 시크릿이 필요합니다. 고른 키워드의 category는 위 아홉 가지 중 하나입니다. 기준은 그 키워드로 쓸 글의 목적이고, 트렌드 수집 통 이름이 아닙니다. 허용 목록 밖이면 1단계가 실패합니다.

텍스트 모델 순서는 `GEMINI_MODELS`(쉼표로 구분)로 바꿉니다. 비어 있으면 `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite` 순입니다. 503, 504, 500, 시간 초과, 분당 429는 그 모델의 재시도를 다 쓴 뒤에 다음 모델로 넘어갑니다. 첫 모델은 90초·3회(대기 20초, 60초), 두 번째는 45초·2회(대기 15초), 그 이후는 30초·2회(대기 10초)입니다. 기본 세 모델이 매번 시간 제한까지 가면 약 8분 45초(525초)입니다. 모델을 찾을 수 없거나 신규 키에 열리지 않으면(404, not found, not available) 그 모델은 다시 부르지 않고 바로 다음으로 넘어갑니다. 일일 한도(`per day`)는 다음 모델로 넘어가지 않고 바로 멈춥니다. 로그에 요청한 모델, 넘어간 시점, 최종 사용 모델이 출력됩니다.

로컬 실행:

```bash
pip install -r requirements.txt
GEMINI_API_KEY=... python main.py
```
