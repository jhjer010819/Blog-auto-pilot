import type { Metadata } from "next";
import type { ReactNode } from "react";
import { pageUrl } from "@/lib/paths";

export function infoMetadata(title: string, description: string, path: string): Metadata {
  const canonical = pageUrl(path);
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
    <main className="flex-1 bg-[#f4f7fb]">
      <div className="mx-auto w-full max-w-[720px] px-4 py-6 sm:px-6 sm:py-12">
        <header className="overflow-hidden rounded-[22px] border border-[#e8edf3] bg-white shadow-[0_10px_32px_rgba(18,20,23,0.05)]">
          <div className="h-[5px] bg-[#38bdf8]" />
          <div className="px-6 py-8 sm:px-8 sm:py-10">
            <p className="text-[14px] font-bold text-[#0b8ec8]">{kicker}</p>
            <h1 className="mt-2 text-[1.7rem] font-extrabold leading-[1.35] tracking-[-0.03em] text-[#121417] sm:text-[2rem]">
              {title}
            </h1>
            {lede ? <p className="mt-3 text-[15px] leading-7 text-[#5c6675]">{lede}</p> : null}
          </div>
        </header>
        <article className="post-body mt-4 rounded-[22px] border border-[#e8edf3] bg-white px-6 py-8 shadow-[0_8px_28px_rgba(18,20,23,0.04)] sm:px-8">
          {children}
        </article>
      </div>
    </main>
  );
}
