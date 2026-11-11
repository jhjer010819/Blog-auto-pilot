import fs from "fs";
import path from "path";
import { excerptFromHtml, sanitizePostHtml } from "./html";

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const POSTS_DIR = path.join(process.cwd(), "content", "posts");
const ALLOWED_CATEGORIES = [
  "교육",
  "건강",
  "과학",
  "IT",
  "부동산",
  "정부혜택",
  "세금",
  "정책·제도",
  "생활정보",
] as const;
const ALLOWED_CATEGORY_SET = new Set<string>(ALLOWED_CATEGORIES);

export type PostLink = {
  title: string;
  href: string;
  tone: "default" | "tool";
  external: boolean;
};

export type Post = {
  slug: string;
  title: string;
  category: string;
  date: string;
  thumbnail?: string;
  thumbnailAlt: string;
  html: string;
  description: string;
  links: PostLink[];
};

let cached: Post[] | null = null;

export function getPosts() {
  if (process.env.NODE_ENV === "production" && cached) return cached;
  const posts = readPosts();
  if (process.env.NODE_ENV === "production") cached = posts;
  return posts;
}

export function getPost(slug: string) {
  return getPosts().find((post) => post.slug === slug);
}

export function parsePostSource(fileName: string, source: string): Post {
  if (!fileName.endsWith(".html")) {
    throw new Error(`${fileName}: 글 파일은 .html 이어야 합니다.`);
  }
  const slug = fileName.slice(0, -".html".length);
  if (!SLUG.test(slug)) {
    throw new Error(
      `${fileName}: 파일 이름은 영문 소문자, 숫자, 하이픈만 쓸 수 있습니다. 예: 2026-youth-rent-support.html`,
    );
  }

  const extracted = extractMeta(fileName, source.replace(/^\uFEFF/, ""));
  const meta = assertMeta(fileName, extracted.meta);
  const html = sanitizePostHtml(extracted.body);
  if (!textFromRough(html)) {
    throw new Error(`${fileName}: 본문 HTML이 비어 있습니다.`);
  }

  return {
    slug,
    title: meta.title,
    category: meta.category,
    date: meta.date,
    thumbnail: meta.thumbnail,
    thumbnailAlt: meta.thumbnailAlt || meta.title,
    html,
    description: meta.description || excerptFromHtml(html),
    links: meta.links,
  };
}

function readPosts() {
  if (!fs.existsSync(POSTS_DIR)) {
    throw new Error("content/posts 폴더가 없습니다.");
  }

  const fileNames = fs
    .readdirSync(POSTS_DIR)
    .filter((name) => name.endsWith(".html"))
    .sort();

  const posts = fileNames.map((fileName) => {
    const fullPath = path.resolve(POSTS_DIR, fileName);
    if (!fullPath.startsWith(`${path.resolve(POSTS_DIR)}${path.sep}`)) {
      throw new Error(`${fileName}: 잘못된 경로입니다.`);
    }
    return parsePostSource(fileName, fs.readFileSync(fullPath, "utf8"));
  });

  return posts.sort((a, b) => {
    if (a.date !== b.date) return a.date < b.date ? 1 : -1;
    return a.slug < b.slug ? -1 : 1;
  });
}

function extractMeta(fileName: string, source: string) {
  const match = source.match(/<script\b([^>]*)>([\s\S]*?)<\/script>/i);
  if (!match) {
    throw new Error(`${fileName}: <script id="post-meta"> 블록이 없습니다.`);
  }
  const attrs = match[1] ?? "";
  if (!/\bid=["']post-meta["']/i.test(attrs) || !/\btype=["']application\/json["']/i.test(attrs)) {
    throw new Error(
      `${fileName}: 파일 맨 위에 <script type="application/json" id="post-meta"> JSON이 있어야 합니다.`,
    );
  }

  let meta: unknown;
  try {
    meta = JSON.parse(match[2] ?? "");
  } catch {
    throw new Error(`${fileName}: post-meta JSON을 읽을 수 없습니다.`);
  }

  const body = `${source.slice(0, match.index ?? 0)}${source.slice((match.index ?? 0) + match[0].length)}`.trim();
  return { meta, body };
}

type CleanMeta = {
  title: string;
  category: string;
  date: string;
  thumbnail?: string;
  thumbnailAlt: string;
  description?: string;
  links: PostLink[];
};

function assertMeta(fileName: string, value: unknown): CleanMeta {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${fileName}: post-meta는 JSON 객체여야 합니다.`);
  }
  const meta = value as Record<string, unknown>;
  const title = requiredString(fileName, meta.title, "title", 160);
  const category = requiredCategory(fileName, meta.category);
  const date = requiredString(fileName, meta.date, "date", 10);
  if (!isRealDate(date)) {
    throw new Error(`${fileName}: date는 YYYY-MM-DD 형식의 실제 날짜여야 합니다.`);
  }

  const thumbnail = readThumbnail(fileName, meta);

  const thumbnailAlt =
    meta.thumbnailAlt === undefined
      ? ""
      : requiredString(fileName, meta.thumbnailAlt, "thumbnailAlt", 160);
  const description =
    meta.description === undefined
      ? undefined
      : requiredString(fileName, meta.description, "description", 200);

  return {
    title,
    category,
    date,
    thumbnail,
    thumbnailAlt,
    description,
    links: readLinks(
      fileName,
      meta.links !== undefined ? meta.links : meta.related,
      meta.links !== undefined ? "links" : "related",
    ),
  };
}

function readThumbnail(fileName: string, meta: Record<string, unknown>) {
  if (meta.thumbnail !== undefined) {
    const thumbnail = requiredString(fileName, meta.thumbnail, "thumbnail", 500);
    if (!isSafeThumbnail(thumbnail)) {
      throw new Error(
        `${fileName}: thumbnail은 /images/ 안의 경로이거나 https 주소여야 합니다.`,
      );
    }
    return thumbnail;
  }

  if (typeof meta.cover !== "string") return undefined;
  const cover = meta.cover.trim();
  if (!cover) return undefined;
  if (cover.length > 500) {
    throw new Error(`${fileName}: cover는 500자 이하로 적어 주세요.`);
  }
  if (!isSafeThumbnail(cover)) {
    throw new Error(`${fileName}: cover는 /images/ 안의 경로이거나 https 주소여야 합니다.`);
  }
  return cover;
}

function readLinks(fileName: string, value: unknown, field = "links"): PostLink[] {
  if (value === undefined) return [];
  if (!Array.isArray(value)) {
    throw new Error(`${fileName}: ${field}는 배열이어야 합니다.`);
  }
  if (value.length > 6) {
    throw new Error(`${fileName}: ${field}는 6개까지입니다.`);
  }

  return value.map((item, index) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error(`${fileName}: ${field}[${index}]는 객체여야 합니다.`);
    }
    const link = item as Record<string, unknown>;
    const title = requiredString(fileName, link.title, `${field}[${index}].title`, 120);
    const href = normalizeHref(
      fileName,
      requiredString(fileName, link.href, `${field}[${index}].href`, 500),
    );
    const tone = link.tone === undefined ? "default" : link.tone;
    if (tone !== "default" && tone !== "tool") {
      throw new Error(`${fileName}: ${field}[${index}].tone은 "tool"만 쓸 수 있습니다.`);
    }
    return { title, href: href.href, external: href.external, tone };
  });
}

function normalizeHref(fileName: string, href: string) {
  if (href.startsWith("/") && !href.startsWith("//") && !href.includes("\\") && !href.includes("..")) {
    const matched = href.match(/^([^?#]*)(\?[^#]*)?(#.*)?$/);
    let pathname = matched?.[1] || "/";
    if (!pathname.endsWith("/")) pathname = `${pathname}/`;
    return {
      href: `${pathname}${matched?.[2] ?? ""}${matched?.[3] ?? ""}`,
      external: false,
    };
  }

  let url: URL;
  try {
    url = new URL(href);
  } catch {
    throw new Error(`${fileName}: 링크 주소가 올바르지 않습니다. (${href})`);
  }
  if (url.protocol !== "https:" || url.username || url.password) {
    throw new Error(`${fileName}: 바깥 링크는 https 주소만 쓸 수 있습니다. (${href})`);
  }
  return { href: url.toString(), external: true };
}

function isSafeThumbnail(src: string) {
  if (src.startsWith("/images/") && !src.includes("..") && !src.includes("\\") && !src.includes("?")) {
    return true;
  }
  try {
    const url = new URL(src);
    return url.protocol === "https:" && !url.username && !url.password;
  } catch {
    return false;
  }
}

function requiredCategory(fileName: string, value: unknown) {
  const category = requiredString(fileName, value, "category", 24);
  if (!ALLOWED_CATEGORY_SET.has(category)) {
    throw new Error(
      `${fileName}: category는 다음 중 하나여야 합니다. ${ALLOWED_CATEGORIES.join(", ")}`,
    );
  }
  return category;
}

function requiredString(fileName: string, value: unknown, field: string, max: number) {
  if (typeof value !== "string") {
    throw new Error(`${fileName}: ${field}는 문자열이어야 합니다.`);
  }
  const trimmed = value.trim();
  if (!trimmed) {
    throw new Error(`${fileName}: ${field}가 비어 있습니다.`);
  }
  if (trimmed.length > max) {
    throw new Error(`${fileName}: ${field}는 ${max}자 이하로 적어 주세요.`);
  }
  return trimmed;
}

function isRealDate(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return (
    date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day
  );
}

function textFromRough(html: string) {
  return html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
}
