import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex-1 bg-white">
      <div className="mx-auto flex w-full max-w-[720px] flex-col px-5 pb-16 pt-7 sm:px-6 sm:pt-10">
        <Link
          href="/"
          className="inline-flex text-[14px] font-medium text-[#8b95a7] transition-colors hover:text-[#16181d]"
        >
          ← Mallow Info Lab 홈으로
        </Link>
        <p className="mt-8 text-[14px] font-semibold text-[#3a74f2]">404</p>
        <h1 className="mt-2 text-[1.7rem] font-extrabold tracking-[-0.03em] text-[#141820]">
          없는 글입니다
        </h1>
        <p className="mt-3 text-[15px] leading-7 text-[#667085]">
          주소가 바뀌었거나, 아직 올라오지 않은 낱장입니다.
        </p>
      </div>
    </main>
  );
}
