import type { MetadataRoute } from "next";
import { categoriesInUse, categorySlug } from "@/lib/categories";
import { getPosts } from "@/lib/posts";
import { SITE_URL } from "@/lib/site";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const posts = getPosts();
  const newest = posts[0]?.date;

  return [
    { url: `${SITE_URL}/`, lastModified: newest },
    { url: `${SITE_URL}/blog/`, lastModified: newest },
    ...categoriesInUse(posts).map((category) => ({
      url: `${SITE_URL}/blog/category/${categorySlug(category)}/`,
      lastModified: posts.find((post) => post.category === category)?.date,
    })),
    ...posts.map((post) => ({
      url: `${SITE_URL}/blog/${post.slug}/`,
      lastModified: post.date,
    })),
    { url: `${SITE_URL}/tools/`, lastModified: "2026-11-19" },
    { url: `${SITE_URL}/about/`, lastModified: "2026-11-19" },
    { url: `${SITE_URL}/privacy/`, lastModified: "2026-11-19" },
    { url: `${SITE_URL}/terms/`, lastModified: "2026-11-12" },
    { url: `${SITE_URL}/contact/`, lastModified: "2026-11-19" },
  ];
}
