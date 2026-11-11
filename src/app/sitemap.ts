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
    ...posts.map((post) => ({
      url: `https://blog.mymallow.cloud/posts/${post.slug}/`,
      lastModified: post.date,
    })),
  ];
}
