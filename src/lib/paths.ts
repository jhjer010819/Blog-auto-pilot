import { SITE_URL } from "./site";

export function postPath(slug: string) {
  return `/blog/${slug}/`;
}

export function categoryPath(slug: string) {
  return `/blog/category/${slug}/`;
}

export function pageUrl(path: string) {
  const withSlash = path.endsWith("/") ? path : `${path}/`;
  return `${SITE_URL}${withSlash}`;
}

export function publicHref(href: string) {
  if (href.startsWith("/posts/")) return href.replace(/^\/posts\//, "/blog/");
  return href;
}

export function rewriteLegacyHrefs(html: string) {
  return html
    .replace(/https?:\/\/blog\.mymallow\.cloud\/posts\//g, `${SITE_URL}/blog/`)
    .replace(/(href=["'])\/posts\//g, "$1/blog/");
}
