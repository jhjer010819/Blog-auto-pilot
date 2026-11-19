"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MediaImage } from "./media-image";

const NAV = [
  { href: "/", label: "홈" },
  { href: "/blog/", label: "블로그" },
  { href: "/tools/", label: "툴" },
  { href: "/about/", label: "소개" },
] as const;

function normalize(path: string) {
  if (path.length > 1 && path.endsWith("/")) return path.slice(0, -1);
  return path;
}

function isActive(pathname: string, href: string) {
  const current = normalize(pathname);
  if (href === "/") return current === "/";
  const target = normalize(href);
  return current === target || current.startsWith(`${target}/`);
}

export function SiteHeader() {
  const pathname = usePathname() || "/";

  return (
    <header className="sticky top-0 z-30 border-b border-[#e6ebf2] bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 w-full max-w-[1120px] items-center justify-between gap-3 px-4 sm:px-6">
        <Link href="/" className="flex min-w-0 items-center gap-2.5">
          <MediaImage src="/logo.png" alt="" width={36} height={36} className="h-9 w-9 shrink-0 rounded-[10px]" />
          <span className="truncate text-[17px] font-extrabold tracking-[-0.04em] text-[#121417] sm:text-[18px]">
            My Mallow
          </span>
        </Link>
        <nav aria-label="주요 메뉴" className="flex shrink-0 items-center gap-0.5 sm:gap-1">
          {NAV.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-full px-2.5 py-1.5 text-[13px] tracking-[-0.02em] transition-colors sm:px-3 sm:text-[14px] ${
                  active
                    ? "bg-[#121417] font-bold text-white"
                    : "font-semibold text-[#3f4754] hover:bg-[#f3f6f9]"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
