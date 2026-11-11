# Blog-auto-pilot

생활정보 노트(https://blog.mymallow.cloud/) 정적 사이트와, 글감 키워드를 고르는 파이프라인이 같은 저장소에 있습니다. 둘은 따로 동작합니다.

## 정적 사이트

소스 위치는 `site/`입니다. 공개 글이 생기기 전에는 글 목록을 비워 둡니다. 나중에 글은 `site/posts/`에 HTML 파일로 추가하고, `site/posts/index.html`과 홈의 최근 글 영역에 링크를 넣습니다.

GitHub Pages 배포는 `.github/workflows/deploy-pages.yml`입니다.

- `main`에 `site/` 또는 이 워크플로가 푸시되면 실행됩니다. Actions 화면에서 수동 실행도 됩니다.
- 워크플로가 `site/`를 아티팩트로 올리고 `actions/deploy-pages`로 게시합니다. 게시 루트에 `CNAME`(`blog.mymallow.cloud`)과 `.nojekyll`이 포함됩니다.
- 배포 방식은 GitHub Actions입니다. `gh-pages` 브랜치를 만들지 않습니다.
- 저장소 Pages 소스는 **GitHub Actions**여야 합니다. 한 번만 설정하면 이후 `main` 병합이 사이트를 갱신합니다.
- DNS는 별도입니다. `blog.mymallow.cloud` CNAME을 `jhjer010819.github.io`로 두고, Cloudflare 프록시는 끕니다.

키워드 워크플로(`.github/workflows/keyword_selector.yml`)는 이 배포를 호출하지 않고, 사이트 빌드도 Python 의존성을 설치하지 않습니다.

## 키워드 선별

`.github/workflows/keyword_selector.yml`이 매일 한국시간 06:00에 `main.py`를 실행합니다. Actions에서 수동 실행도 됩니다. `GEMINI_API_KEY` 시크릿이 필요합니다.

로컬 실행:

```bash
pip install -r requirements.txt
GEMINI_API_KEY=... python main.py
```
