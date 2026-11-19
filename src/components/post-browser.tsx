import Link from "next/link";
import { categoriesInUse, categorySlug } from "@/lib/categories";
import { formatPublishedDate } from "@/lib/format";
import { categoryPath, postPath } from "@/lib/paths";
import { getPosts, type Post } from "@/lib/posts";
import { PostThumb } from "./post-thumb";

export function PostBrowser({
  title,
  lede,
  posts,
  active,
}: {
  title: string;
  lede: string;
  posts: Post[];
  active?: string;
}) {
  const categories = categoriesInUse(getPosts());

  return (
    <div className="mx-auto w-full max-w-[760px] px-4 py-8 sm:px-6 sm:py-10">
      <h1 className="text-[1.7rem] font-extrabold tracking-[-0.04em] text-[#121417] sm:text-[2rem]">
        {title}
      </h1>
      <p className="mt-2 text-[14px] leading-6 text-[#6b7280]">{lede}</p>
      {categories.length > 0 ? (
        <div className="mt-5 flex flex-wrap gap-2" role="navigation" aria-label="분류">
          <FilterChip href="/blog/" active={!active}>
            전체
          </FilterChip>
          {categories.map((category) => (
            <FilterChip
              key={category}
              href={categoryPath(categorySlug(category))}
              active={active === category}
            >
              {category}
            </FilterChip>
          ))}
        </div>
      ) : null}
      {posts.length === 0 ? (
        <div className="mt-6 rounded-[22px] border border-[#e8edf3] bg-white px-6 py-12 text-center">
          <p className="text-[17px] font-extrabold text-[#121417]">아직 올라온 글이 없습니다</p>
          <p className="mt-2 text-[14px] leading-6 text-[#6b7280]">
            글이 준비되는 동안 마이멜로 툴을 둘러보세요.
          </p>
          <Link href="/tools/" className="mt-4 inline-flex text-[14px] font-bold text-[#0b8ec8]">
            툴 보러 가기 →
          </Link>
        </div>
      ) : (
        <ul className="mt-6 flex flex-col gap-3">
          {posts.map((post, index) => (
            <li key={post.slug}>
              <Link
                href={postPath(post.slug)}
                className="flex items-center gap-3 rounded-[18px] border border-[#e8edf3] bg-white p-2.5 shadow-[0_6px_20px_rgba(18,20,23,0.04)] transition duration-200 hover:-translate-y-0.5 sm:gap-4 sm:p-3"
              >
                <PostThumb
                  post={post}
                  eager={index === 0}
                  className="h-[84px] w-[112px] shrink-0 rounded-xl sm:h-[96px] sm:w-[132px]"
                />
                <span className="min-w-0 flex-1 py-1">
                  <span className="text-[12px] font-bold text-[#0b8ec8]">{post.category}</span>
                  <span className="mt-1 block text-[16px] font-bold leading-snug tracking-[-0.03em] text-[#121417]">
                    {post.title}
                  </span>
                  <time dateTime={post.date} className="mt-1.5 block text-[12px] text-[#8b93a1]">
                    {formatPublishedDate(post.date)}
                  </time>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function FilterChip({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: string;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`rounded-full px-3 py-1.5 text-[13px] font-bold ${
        active ? "bg-[#121417] text-white" : "bg-white text-[#3f4754] ring-1 ring-[#e6ebf2] hover:text-[#0b8ec8]"
      }`}
    >
      {children}
    </Link>
  );
}
