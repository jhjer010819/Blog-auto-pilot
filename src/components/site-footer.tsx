import Link from "next/link";

const LINKS = [
  { href: "/about/", label: "어바웃" },
  { href: "/privacy/", label: "개인정보 처리방침" },
  { href: "/terms/", label: "이용약관" },
] as const;

export function SiteFooter() {
  return (
    <footer className="bg-[#f4f6fb]">
      <div className="mx-auto w-full max-w-[720px] px-4 pb-8 sm:px-6 sm:pb-12">
        <div className="rounded-[18px] bg-white px-5 py-4 text-center shadow-[0_8px_28px_rgba(22,34,61,0.05)]">
          <nav aria-label="사이트 정보" className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2">
            {LINKS.map((link, index) => (
              <span key={link.href} className="inline-flex items-center gap-x-3">
                {index > 0 ? (
                  <span aria-hidden="true" className="text-[13px] text-[#d5dbe6]">
                    ·
                  </span>
                ) : null}
                <Link
                  href={link.href}
                  className="text-[13px] font-semibold text-[#667085] transition-colors hover:text-[#2f6bff]"
                >
                  {link.label}
                </Link>
              </span>
            ))}
          </nav>
          <p className="mt-2 text-[12px] leading-5 text-[#98a2b3]">
            <a
              href="https://mymallow.cloud/"
              className="transition-colors hover:text-[#667085]"
              target="_blank"
              rel="noopener noreferrer"
            >
              마이멜로 (MyMallow)
            </a>
            {" · Mallow Info Lab"}
          </p>
        </div>
      </div>
    </footer>
  );
}
