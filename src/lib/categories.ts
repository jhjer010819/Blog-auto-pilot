import { ALLOWED_CATEGORIES, type Post } from "./posts";

const CATEGORY_SLUG: Record<string, string> = {
  교육: "education",
  건강: "health",
  과학: "science",
  IT: "it",
  부동산: "real-estate",
  정부혜택: "benefits",
  세금: "tax",
  "정책·제도": "policy",
  생활정보: "living",
};

const TONE: Record<string, { bg: string; fg: string }> = {
  교육: { bg: "#e7f6fd", fg: "#075985" },
  건강: { bg: "#e8f8ef", fg: "#047857" },
  과학: { bg: "#eef2ff", fg: "#4338ca" },
  IT: { bg: "#eef2ff", fg: "#3730a3" },
  부동산: { bg: "#f3f4f6", fg: "#374151" },
  정부혜택: { bg: "#e7f6fd", fg: "#0369a1" },
  세금: { bg: "#f5f3ff", fg: "#6d28d9" },
  "정책·제도": { bg: "#f4f4f5", fg: "#27272a" },
  생활정보: { bg: "#fff7ed", fg: "#c2410c" },
};

export function categorySlug(category: string) {
  return CATEGORY_SLUG[category] ?? encodeURIComponent(category);
}

export function categoryFromSlug(slug: string) {
  const found = Object.entries(CATEGORY_SLUG).find(([, value]) => value === slug);
  return found?.[0];
}

export function categoriesInUse(posts: Post[]) {
  const present = new Set(posts.map((post) => post.category));
  const ordered: string[] = ALLOWED_CATEGORIES.filter((category) => present.has(category));
  for (const category of present) {
    if (!ordered.includes(category)) ordered.push(category);
  }
  return ordered;
}

export function categoryTone(category: string) {
  return TONE[category] ?? { bg: "#e7f6fd", fg: "#0369a1" };
}
