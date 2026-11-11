import { ArticleCard } from "@/components/article-card";
import { getPosts } from "@/lib/posts";

export default function HomePage() {
  const posts = getPosts();

  return (
    <main className="min-h-screen bg-[#f4f6fb]">
      <div className="mx-auto w-full max-w-[720px] px-4 py-6 sm:px-6 sm:py-12">
        <header className="overflow-hidden rounded-[22px] bg-white shadow-[0_10px_40px_rgba(22,34,61,0.06)]">
          <div className="h-[5px] bg-[#2f6bff]" />
          <div className="px-6 py-10 text-center sm:py-12">
            <h1 className="text-[1.85rem] font-extrabold tracking-[-0.04em] text-[#141820] sm:text-[2.15rem]">
              Mallow Info Lab <span aria-hidden="true">💡</span>
            </h1>
            <p className="mt-3 text-[15px] font-medium leading-6 text-[#8b95a7]">
              매일 업데이트되는 핵심 정책 & 생활 꿀팁 족보
            </p>
          </div>
        </header>

        <section className="mt-9 sm:mt-11" aria-labelledby="latest-heading">
          <h2
            id="latest-heading"
            className="text-[12px] font-semibold tracking-[0.16em] text-[#98a2b3]"
          >
            LATEST ARTICLES
          </h2>
          {posts.length === 0 ? (
            <div className="mt-4 rounded-[18px] bg-white px-5 py-10 text-center shadow-[0_8px_28px_rgba(22,34,61,0.05)]">
              <p className="text-[16px] font-bold text-[#16181d]">아직 발행된 글이 없습니다</p>
              <p className="mt-2 text-[14px] leading-6 text-[#8b95a7]">
                새 HTML이 올라오면 이 목록에 나타납니다.
              </p>
            </div>
          ) : (
            <ul className="mt-4 flex flex-col gap-3.5">
              {posts.map((post, index) => (
                <ArticleCard key={post.slug} post={post} eager={index === 0} />
              ))}
            </ul>
          )}
        </section>
      </div>
    </main>
  );
}
