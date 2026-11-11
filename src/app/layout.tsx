import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

const description = "매일 업데이트되는 핵심 정책 & 생활 꿀팁 족보";

export const metadata: Metadata = {
  metadataBase: new URL("https://blog.mymallow.cloud"),
  title: {
    default: "Mallow Info Lab",
    template: "%s · Mallow Info Lab",
  },
  description,
  openGraph: {
    type: "website",
    locale: "ko_KR",
    siteName: "Mallow Info Lab",
    title: "Mallow Info Lab",
    description,
    url: "/",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body className="min-h-full antialiased">{children}</body>
    </html>
  );
}
