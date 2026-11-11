import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { AdSlot } from "@/components/ad-slot";
import { RelatedLinks } from "@/components/related-links";
import { formatPublishedDate, seoulDateTime } from "@/lib/format";
import { localImageSize } from "@/lib/image-size";
import { getPost, getPosts, type Post } from "@/lib/posts";
import {
  absoluteUrl,
  defaultOgImage,
  publisherOrganization,
  serializeJsonLd,
  SITE_NAME,
  SITE_URL,
} from "@/lib/site";

type PostPageProps = {
  params: Promise<{ slug: string }>;
};

export const dynamicParams = false;

export function generateStaticParams() {
  return getPosts().map((post) => ({ slug: post.slug }));
}

function shareImage(post: Post) {
  if (!post.thumbnail) {
    return defaultOgImage;
  }
  const size = localImageSize(post.thumbnail);
  return {
    url: post.thumbnail,
    alt: post.thumbnailAlt,
    ...(size ? { width: size.width, height: size.height } : {}),
  };
}

export async function generateMetadata({ params }: PostPageProps): Promise<Metadata> {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) return { title: "없는 글" };

  const published = seoulDateTime(post.date);
  const image = shareImage(post);
  const canonical = `/posts/${post.slug}/`;

  return {
    title: post.title,
    description: post.description,
    alternates: { canonical },
    openGraph: {
      type: "article",
      title: post.title,
      description: post.description,
      url: canonical,
      siteName: SITE_NAME,
      locale: "ko_KR",
      publishedTime: published,
      modifiedTime: published,
      section: post.category,
      images: [
        {
          url: image.url,
          alt: image.alt,
          ...(image.width && image.height ? { width: image.width, height: image.height } : {}),
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: post.title,
      description: post.description,
      images: [{ url: image.url, alt: image.alt }],
    },
  };
}

export default async function PostPage({ params }: PostPageProps) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) notFound();

  const pageUrl = `${SITE_URL}/posts/${post.slug}/`;
  const published = seoulDateTime(post.date);
  const image = shareImage(post);
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.title,
    description: post.description,
    image: image.width
      ? {
          "@type": "ImageObject",
          url: absoluteUrl(image.url),
          width: image.width,
          height: image.height,
        }
      : absoluteUrl(image.url),
    datePublished: published,
    dateModified: published,
    author: {
      "@type": "Organization",
      name: SITE_NAME,
      url: `${SITE_URL}/`,
    },
    publisher: publisherOrganization(),
    url: pageUrl,
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": pageUrl,
    },
    articleSection: post.category,
    inLanguage: "ko-KR",
  };

  return (
    <main className="min-h-screen bg-white">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(jsonLd) }}
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
          발행일: <time dateTime={published}>{formatPublishedDate(post.date)}</time>
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
