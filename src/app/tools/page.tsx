import type { Metadata } from "next";
import { ToolBadge, ToolVisual } from "@/components/tool-rank";
import { pageUrl } from "@/lib/paths";
import { TOOLS } from "@/lib/tools";

const title = "툴";
const description = "마이멜로가 만든 도구입니다. 각 도구는 자기 주소에서 열립니다.";
const canonical = pageUrl("/tools/");

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical },
  openGraph: { title, description, url: canonical },
};

export default function ToolsPage() {
  return (
    <main className="flex-1 bg-[#f4f7fb]">
      <div className="mx-auto w-full max-w-[1120px] px-4 py-8 sm:px-6 sm:py-10">
        <h1 className="text-[1.7rem] font-extrabold tracking-[-0.04em] text-[#121417] sm:text-[2rem]">툴</h1>
        <p className="mt-2 max-w-[520px] text-[14px] leading-6 text-[#6b7280]">{description}</p>
        <ul className="mt-6 grid gap-4 sm:grid-cols-2">
          {TOOLS.map((tool) => {
            const card = (
              <>
                <ToolVisual tool={tool} alt={tool.image ? tool.imageAlt : ""} className="aspect-[16/9] w-full" />
                <span className="block p-4">
                  <span className="flex items-start justify-between gap-3">
                    <span className="text-[18px] font-extrabold tracking-[-0.03em] text-[#121417]">
                      {tool.name}
                    </span>
                    <ToolBadge live={tool.live} />
                  </span>
                  <span className="mt-2 block text-[14px] leading-6 text-[#5c6675]">{tool.description}</span>
                  {tool.live && tool.href ? (
                    <span className="mt-3 block text-[13px] font-bold text-[#0b8ec8]">사이트로 이동 →</span>
                  ) : (
                    <span className="mt-3 block text-[13px] font-semibold text-[#8b93a1]">곧 열립니다</span>
                  )}
                </span>
              </>
            );
            const className =
              "block overflow-hidden rounded-[22px] border border-[#e8edf3] bg-white shadow-[0_8px_28px_rgba(18,20,23,0.04)]";
            return (
              <li key={tool.name}>
                {tool.live && tool.href ? (
                  <a href={tool.href} target="_blank" rel="noopener noreferrer" className={`${className} transition duration-200 hover:-translate-y-0.5`}>
                    {card}
                  </a>
                ) : (
                  <div className={className}>{card}</div>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </main>
  );
}
