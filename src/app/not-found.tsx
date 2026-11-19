import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex-1 bg-[#f4f7fb]">
      <div className="mx-auto flex w-full max-w-[720px] flex-col px-5 pb-16 pt-12 sm:px-6">
        <p className="text-[14px] font-bold text-[#0b8ec8]">404</p>
        <h1 className="mt-2 text-[1.7rem] font-extrabold tracking-[-0.03em] text-[#121417]">
          없는 페이지입니다
        </h1>
        <p className="mt-3 text-[15px] leading-7 text-[#5c6675]">
          주소가 바뀌었거나, 아직 올라오지 않은 페이지입니다.
        </p>
        <p className="mt-6 flex gap-4 text-[14px] font-bold">
          <Link href="/" className="text-[#0b8ec8]">
            홈
          </Link>
          <Link href="/blog/" className="text-[#0b8ec8]">
            블로그
          </Link>
        </p>
      </div>
    </main>
  );
}
