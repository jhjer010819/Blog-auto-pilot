import Link from "next/link";
import type { PostLink } from "@/lib/posts";

function Chevron() {
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true" className="h-5 w-5 shrink-0 text-[#b0b8c6]">
      <path
        d="M7.5 4.75 13 10.25l-5.5 5.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function RelatedLinks({ links }: { links: PostLink[] }) {
  if (links.length === 0) return null;

  return (
    <aside className="rounded-[22px] bg-[#f4f7fb] p-4 sm:p-6">
      <h2 className="flex items-center gap-2 px-1 text-[16px] font-bold tracking-[-0.02em] text-[#16181d]">
        <span aria-hidden="true">💡</span>
        함께 읽으면 유용한 정보
      </h2>
      <ul className="mt-4 flex flex-col gap-2.5">
        {links.map((link) => {
          const className = `flex items-center justify-between gap-4 rounded-2xl px-4 py-4 text-[15px] font-semibold leading-snug tracking-[-0.02em] text-[#1c2430] transition ${
            link.tone === "tool"
              ? "bg-[#e8f1ff] hover:bg-[#dce8ff]"
              : "bg-white shadow-[0_4px_16px_rgba(22,34,61,0.04)] hover:bg-[#f8fbff]"
          }`;
          const inner = (
            <>
              <span className="min-w-0">{link.title}</span>
              <Chevron />
            </>
          );
          return (
            <li key={`${link.href}-${link.title}`}>
              {link.external ? (
                <a href={link.href} className={className} target="_blank" rel="noopener noreferrer">
                  {inner}
                </a>
              ) : (
                <Link href={link.href} className={className}>
                  {inner}
                </Link>
              )}
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
