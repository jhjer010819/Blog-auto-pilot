import type { Metadata } from "next";
import { HomeSections } from "@/components/home-sections";
import { getPosts } from "@/lib/posts";
import { publisherOrganization, serializeJsonLd, SITE_DESCRIPTION, SITE_NAME, SITE_URL } from "@/lib/site";

export const metadata: Metadata = {
  alternates: { canonical: `${SITE_URL}/` },
  openGraph: { url: `${SITE_URL}/` },
};

const websiteJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: SITE_NAME,
  url: `${SITE_URL}/`,
  description: SITE_DESCRIPTION,
  inLanguage: "ko-KR",
  publisher: publisherOrganization(),
};

export default function HomePage() {
  const posts = getPosts();

  return (
    <main className="flex-1 bg-[#f4f7fb]">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: serializeJsonLd(websiteJsonLd) }}
      />
      <HomeSections posts={posts} />
    </main>
  );
}
