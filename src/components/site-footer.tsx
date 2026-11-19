import Link from "next/link";

const LINKS = [
  { href: "/about/", label: "소개" },
  { href: "/privacy/", label: "개인정보처리방침" },
  { href: "/terms/", label: "이용약관" },
  { href: "/contact/", label: "문의" },
] as const;

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-[#e6ebf2] bg-white">
      <div className="mx-auto w-full max-w-[1120px] px-4 py-8 text-center sm:px-6">
        <nav aria-label="사이트 정보" className="flex flex-wrap items-center justify-center gap-x-4 gap-y-2">
          {LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-[13px] font-semibold text-[#3f4754] transition-colors hover:text-[#0b8ec8]"
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <p className="mt-4 text-[13px] font-semibold text-[#121417]">마이멜로 · MyMallow</p>
        <p className="mt-1 text-[12px] text-[#8b93a1]">© 2026 My Mallow</p>
        <p className="mt-1 text-[12px]">
          <a
            href="mailto:contact@mymallow.cloud"
            className="text-[#5c6675] underline-offset-2 hover:text-[#0b8ec8] hover:underline"
          >
            contact@mymallow.cloud
          </a>
        </p>
      </div>
    </footer>
  );
}
