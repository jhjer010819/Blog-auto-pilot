import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { pageUrl, postPath } from "@/lib/paths";
import { getPost, getPosts } from "@/lib/posts";

type LegacyPostProps = {
  params: Promise<{ slug: string }>;
};

export const dynamicParams = false;

export function generateStaticParams() {
  return getPosts().map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }: LegacyPostProps): Promise<Metadata> {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) return { title: "없는 글" };
  const canonical = pageUrl(postPath(post.slug));
  return {
    title: post.title,
    description: post.description,
    alternates: { canonical },
    robots: { index: false, follow: true },
    openGraph: { url: canonical, title: post.title, description: post.description },
  };
}

export default async function LegacyPostPage({ params }: LegacyPostProps) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) notFound();
  const href = postPath(post.slug);

  return (
    <main className="flex-1 bg-[#f4f7fb]">
      <meta httpEquiv="refresh" content={`0; url=${href}`} />
      <div className="mx-auto w-full max-w-[640px] px-5 py-16 text-center">
        <p className="text-[15px] leading-7 text-[#3f4754]">이 글은 새 주소로 옮겼습니다.</p>
        <p className="mt-4">
          <Link href={href} className="text-[16px] font-bold text-[#0b8ec8]">
            {post.title}
          </Link>
        </p>
      </div>
    </main>
  );
}
