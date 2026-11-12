import type { MetadataRoute } from "next";
import { getPosts } from "@/lib/posts";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const posts = getPosts();
  return [
    {
      url: "https://blog.mymallow.cloud/",
      lastModified: posts[0]?.date,
    },
    {
      url: "https://blog.mymallow.cloud/about/",
      lastModified: "2026-11-12",
    },
    {
      url: "https://blog.mymallow.cloud/privacy/",
      lastModified: "2026-11-12",
    },
    {
      url: "https://blog.mymallow.cloud/terms/",
      lastModified: "2026-11-12",
    },
    ...posts.map((post) => ({
      url: `https://blog.mymallow.cloud/posts/${post.slug}/`,
      lastModified: post.date,
    })),
  ];
}
