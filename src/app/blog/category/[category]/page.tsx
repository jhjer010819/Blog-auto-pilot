import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PostBrowser } from "@/components/post-browser";
import { categoriesInUse, categoryFromSlug, categorySlug } from "@/lib/categories";
import { pageUrl, categoryPath } from "@/lib/paths";
import { getPosts } from "@/lib/posts";

type CategoryPageProps = {
  params: Promise<{ category: string }>;
};

export const dynamicParams = false;

export function generateStaticParams() {
  return categoriesInUse(getPosts()).map((category) => ({ category: categorySlug(category) }));
}

export async function generateMetadata({ params }: CategoryPageProps): Promise<Metadata> {
  const { category: slug } = await params;
  const name = categoryFromSlug(slug);
  if (!name) return { title: "없는 분류" };
  const description = `${name} 글을 모았습니다.`;
  const canonical = pageUrl(categoryPath(slug));
  return {
    title: name,
    description,
    alternates: { canonical },
    openGraph: { title: name, description, url: canonical },
  };
}

export default async function CategoryPage({ params }: CategoryPageProps) {
  const { category: slug } = await params;
  const name = categoryFromSlug(slug);
  if (!name) notFound();
  const posts = getPosts().filter((post) => post.category === name);

  return (
    <main className="flex-1 bg-[#f4f7fb]">
      <PostBrowser title={name} lede={`${name} 글`} posts={posts} active={name} />
    </main>
  );
}
