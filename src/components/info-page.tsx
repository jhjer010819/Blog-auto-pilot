import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { SITE_URL } from "@/lib/site";

export function infoMetadata(title: string, description: string, path: string): Metadata {
  const canonical = `${SITE_URL}${path}`;
  return {
    title,
    description,
    alternates: { canonical },
    openGraph: {
      title,
      description,
      url: canonical,
    },
    twitter: {
      title,
      description,
    },
  };
}

export function InfoPage({
  kicker,
  title,
  lede,
  children,
}: {
  kicker: string;
  title: string;
  lede?: string;
  children: ReactNode;
}) {
  return (
    <main className="flex-1 bg-[#f4f6fb]">
      <div className="mx-auto w-full max-w-[720px] px-4 py-6 sm:px-6 sm:py-12">
        <header className="overflow-hidden rounded-[22px] bg-white shadow-[0_10px_40px_rgba(22,34,61,0.06)]">
          <div className="h-[5px] bg-[#2f6bff]" />
          <div className="px-6 py-8 sm:px-8 sm:py-10">
            <Link
              href="/"
              className="inline-flex text-[14px] font-medium text-[#8b95a7] transition-colors hover:text-[#16181d]"
            >
              ← Mallow Info Lab 홈으로
            </Link>
            <p className="mt-6 text-[14px] font-semibold text-[#3a74f2]">{kicker}</p>
            <h1 className="mt-2 text-[1.7rem] font-extrabold leading-[1.35] tracking-[-0.03em] text-[#141820] sm:text-[2rem]">
              {title}
            </h1>
            {lede ? <p className="mt-3 text-[14px] text-[#9aa3b5]">{lede}</p> : null}
          </div>
        </header>
        <article className="post-body mt-4 rounded-[22px] bg-white px-6 py-8 shadow-[0_8px_28px_rgba(22,34,61,0.05)] sm:px-8">
          {children}
        </article>
      </div>
    </main>
  );
}
