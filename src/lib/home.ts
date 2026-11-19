import { categoriesInUse } from "./categories";
import { localImageSize } from "./image-size";
import type { Post } from "./posts";

export const LATEST_COUNT = 6;
export const PHOTO_MIN = 3;
export const PHOTO_MAX = 4;
const TITLES_PER_BOX = 4;
const OWN_BOX_MIN = 3;

const THEME_GROUPS: string[][] = [
  ["정부혜택", "정책·제도"],
  ["건강", "과학"],
  ["생활정보", "세금", "부동산"],
  ["교육", "IT"],
];

const THEME_ORDER = THEME_GROUPS.flat();

export type CategoryBox = {
  id: string;
  categories: string[];
  posts: Post[];
};

export function latestPosts(posts: Post[]) {
  return posts.slice(0, LATEST_COUNT);
}

export function hasRenderableImage(post: Post) {
  if (!post.thumbnail) return false;
  if (post.thumbnail.startsWith("/")) return Boolean(localImageSize(post.thumbnail));
  return true;
}

export function photoPosts(posts: Post[]) {
  const withImage = posts.filter(hasRenderableImage);
  if (withImage.length < PHOTO_MIN) return [];
  const shown = new Set(latestPosts(posts).map((post) => post.slug));
  const fresh = withImage.filter((post) => !shown.has(post.slug));
  const chosen = fresh.length >= PHOTO_MIN ? fresh : withImage;
  return chosen.slice(0, PHOTO_MAX);
}

export function categoryBoxes(posts: Post[]): CategoryBox[] {
  if (categoriesInUse(posts).length < 2) return [];

  const byCategory = new Map<string, Post[]>();
  for (const post of posts) {
    const list = byCategory.get(post.category) ?? [];
    list.push(post);
    byCategory.set(post.category, list);
  }

  const known = new Set(THEME_ORDER);
  const themes = [
    ...THEME_GROUPS,
    ...[...byCategory.keys()].filter((category) => !known.has(category)).map((category) => [category]),
  ];

  const grouped: string[][] = [];
  for (const theme of themes) {
    const members = theme.filter((category) => byCategory.has(category));
    if (members.length === 0) continue;
    const large = members.filter((category) => (byCategory.get(category)?.length ?? 0) >= OWN_BOX_MIN);
    const tiny = members.filter((category) => (byCategory.get(category)?.length ?? 0) < OWN_BOX_MIN);

    if (large.length === 0) {
      grouped.push(members);
      continue;
    }
    if (tiny.length === 1) {
      const host = large.reduce((best, category) =>
        (byCategory.get(category)?.length ?? 0) > (byCategory.get(best)?.length ?? 0) ? category : best,
      );
      for (const category of large) {
        grouped.push(category === host ? [category, tiny[0]] : [category]);
      }
      continue;
    }
    for (const category of large) grouped.push([category]);
    if (tiny.length >= 2) grouped.push(tiny);
  }

  if (grouped.length < 2) return [];

  return grouped.map((categories) => {
    const ordered = [...categories].sort(
      (a, b) => themeIndex(a) - themeIndex(b),
    );
    return {
      id: ordered.join("-"),
      categories: ordered,
      posts: ordered
        .flatMap((category) => byCategory.get(category) ?? [])
        .sort(byRecency)
        .slice(0, TITLES_PER_BOX),
    };
  });
}

function themeIndex(category: string) {
  const index = THEME_ORDER.indexOf(category);
  return index === -1 ? THEME_ORDER.length : index;
}

function byRecency(a: Post, b: Post) {
  if (a.date !== b.date) return a.date < b.date ? 1 : -1;
  return a.slug < b.slug ? -1 : 1;
}
