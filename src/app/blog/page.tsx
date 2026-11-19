import type { Metadata } from "next";
import { PostBrowser } from "@/components/post-browser";
import { getPosts } from "@/lib/posts";
import { serializeJsonLd, SITE_NAME, SITE_URL } from "@/lib/site";
import { postPath } from "@/lib/paths";

const title = "블로그";
const description = "마이멜로의 생활 정보와 정책 글입니다.";
const canonical = `${SITE_URL}/blog/`;

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical },
  openGraph: { title, description, url: canonical },
};

export default function BlogPage() {
  const posts = getPosts();
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Blog",
    name: `${SITE_NAME} 블로그`,
    url: canonical,
    inLanguage: "ko-KR",
    blogPost: posts.map((post) => ({
      "@type": "BlogPosting",
      headline: post.title,
      datePublished: post.date,
      url: `${SITE_URL}${postPath(post.slug)}`,
    })),
  };

  return (
    <main className="flex-1 bg-[#f4f7fb]">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: serializeJsonLd(jsonLd) }} />
      <PostBrowser title="블로그" lede={description} posts={posts} />
    </main>
  );
}
