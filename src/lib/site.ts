// Canonical origin for sitemap, canonical, and og:url.
// GitHub Pages CNAME stays blog.mymallow.cloud until the domain is moved.
export const SITE_URL = "https://mymallow.cloud";
export const SITE_NAME = "마이멜로";
export const SITE_DESCRIPTION =
  "아이와 부모의 오늘을 가볍고 부드럽게. 생활 정보와 바로 쓰는 도구를 모았습니다.";
export const DEFAULT_OG_IMAGE = "/og-default.png";
export const DEFAULT_OG_WIDTH = 1200;
export const DEFAULT_OG_HEIGHT = 630;
export const LOGO_IMAGE = "/logo.png";
export const LOGO_SIZE = 512;
export const ADSENSE_ACCOUNT = "ca-pub-5854572232694460";

export const defaultOgImage = {
  url: DEFAULT_OG_IMAGE,
  width: DEFAULT_OG_WIDTH,
  height: DEFAULT_OG_HEIGHT,
  alt: SITE_NAME,
};

export function absoluteUrl(pathOrUrl: string) {
  if (/^https?:\/\//i.test(pathOrUrl)) return pathOrUrl;
  const path = pathOrUrl.startsWith("/") ? pathOrUrl : `/${pathOrUrl}`;
  return `${SITE_URL}${path}`;
}

export function serializeJsonLd(data: unknown) {
  return JSON.stringify(data)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");
}

export function publisherOrganization() {
  return {
    "@type": "Organization",
    name: SITE_NAME,
    url: `${SITE_URL}/`,
    logo: {
      "@type": "ImageObject",
      url: absoluteUrl(LOGO_IMAGE),
      width: LOGO_SIZE,
      height: LOGO_SIZE,
    },
  };
}
