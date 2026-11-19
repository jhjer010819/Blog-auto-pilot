import { TOOLS, type Tool } from "@/lib/tools";
import { MediaImage } from "./media-image";

export function ToolBadge({ live }: { live: boolean }) {
  return (
    <span
      className={`inline-flex shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold ${
        live ? "bg-[#e7f6fd] text-[#0369a1]" : "bg-[#f3f4f6] text-[#6b7280]"
      }`}
    >
      {live ? "Live" : "준비중"}
    </span>
  );
}

export function ToolVisual({
  tool,
  className,
  alt = "",
  eager = false,
}: {
  tool: Tool;
  className?: string;
  alt?: string;
  eager?: boolean;
}) {
  if (tool.image) {
    return (
      <MediaImage
        src={tool.image}
        alt={alt}
        loading={eager ? "eager" : "lazy"}
        className={`object-cover ${className ?? ""}`}
      />
    );
  }

  return (
    <span
      aria-hidden="true"
      className={`grid place-items-center bg-gradient-to-br from-[#e7f6fd] via-white to-[#dff3fb] text-[#0b4a66] ${className ?? ""}`}
    >
      <svg viewBox="0 0 48 48" className="h-[58%] w-auto" fill="none">
        <rect x="8" y="10" width="32" height="28" rx="4" stroke="currentColor" strokeWidth="2.4" />
        <path d="M8 18h32M18 10v8M30 10v8" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
      </svg>
    </span>
  );
}

export function ToolRank({ headingId = "tool-rank-heading" }: { headingId?: string }) {
  return <ToolRankList tools={TOOLS} headingId={headingId} />;
}

function ToolRankList({ tools, headingId }: { tools: Tool[]; headingId: string }) {
  return (
    <section aria-labelledby={headingId} className="rounded-[22px] border border-[#e8edf3] bg-white p-4 shadow-[0_8px_28px_rgba(18,20,23,0.04)]">
      <h2 id={headingId} className="px-1 text-[16px] font-extrabold tracking-[-0.03em] text-[#121417]">
        툴 순위
      </h2>
      <ol className="mt-3 flex flex-col gap-2">
        {tools.map((tool, index) => {
          const body = (
            <>
              <span className="w-5 shrink-0 text-[16px] font-black tabular-nums text-[#121417]">
                {index + 1}
              </span>
              <ToolVisual tool={tool} className="h-12 w-12 shrink-0 rounded-xl" />
              <span className="min-w-0 flex-1">
                <span className="flex items-start justify-between gap-2">
                  <span className="text-[14px] font-bold leading-5 tracking-[-0.02em] text-[#121417]">
                    {tool.name}
                  </span>
                  <ToolBadge live={tool.live} />
                </span>
                <span className="mt-0.5 block truncate text-[12px] leading-5 text-[#6b7280]">
                  {tool.description}
                </span>
              </span>
            </>
          );
          const className = "flex items-center gap-2.5 rounded-2xl px-1 py-1.5";
          return (
            <li key={tool.name}>
              {tool.live && tool.href ? (
                <a
                  href={tool.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`${className} transition-colors hover:bg-[#f5fbfe]`}
                >
                  {body}
                </a>
              ) : (
                <div className={className}>{body}</div>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
