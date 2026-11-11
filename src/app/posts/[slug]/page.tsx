import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { AdSlot } from "@/components/ad-slot";
import { RelatedLinks } from "@/components/related-links";
import { formatPublishedDate } from "@/lib/format";
import { getPost, getPosts } from "@/lib/posts";

type PostPageProps = {
  params: Promise<{ slug: string }>;
};

export const dynamicParams = false;

export function generateStaticParams() {
  return getPosts().map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }: PostPageProps): Promise<Metadata> {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) return { title: "없는 글" };

  return {
    title: post.title,
    description: post.description,
    alternates: { canonical: `/posts/${post.slug}/` },
    openGraph: {
      type: "article",
      title: post.title,
      description: post.description,
      url: `/posts/${post.slug}/`,
      publishedTime: post.date,
      images: post.thumbnail ? [{ url: post.thumbnail, alt: post.thumbnailAlt }] : undefined,
    },
  };
}

export default async function PostPage({ params }: PostPageProps) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) notFound();

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    datePublished: post.date,
    description: post.description,
    articleSection: post.category,
    inLanguage: "ko",
    mainEntityOfPage: `https://blog.mymallow.cloud/posts/${post.slug}/`,
    publisher: {
      "@type": "Organization",
      name: "Mallow Info Lab",
      url: "https://blog.mymallow.cloud",
    },
  };

  return (
    <main className="min-h-screen bg-white">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd).replace(/</g, "\\u003c") }}
      />
      <article className="mx-auto w-full max-w-[720px] px-5 pb-16 pt-7 sm:px-6 sm:pt-10">
        <Link
          href="/"
          className="inline-flex text-[14px] font-medium text-[#8b95a7] transition-colors hover:text-[#16181d]"
        >
          ← Mallow Info Lab 홈으로
        </Link>
        <p className="mt-8 text-[14px] font-semibold text-[#3a74f2]">{post.category}</p>
        <h1 className="mt-2 text-[1.7rem] font-extrabold leading-[1.35] tracking-[-0.03em] text-[#141820] sm:text-[2rem]">
          {post.title}
        </h1>
        <p className="mt-3 text-[14px] text-[#9aa3b5]">
          발행일: <time dateTime={post.date}>{formatPublishedDate(post.date)}</time>
        </p>
        <div className="mt-8">
          <AdSlot position="top" />
        </div>
        <div className="post-body mt-8" dangerouslySetInnerHTML={{ __html: post.html }} />
        <div className="mt-10">
          <AdSlot position="bottom" />
        </div>
        {post.links.length > 0 ? (
          <div className="mt-8">
            <RelatedLinks links={post.links} />
          </div>
        ) : null}
      </article>
    </main>
  );
}
