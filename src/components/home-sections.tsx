import Link from "next/link";
import { categoryPath, postPath } from "@/lib/paths";
import { categorySlug } from "@/lib/categories";
import { categoryBoxes, latestPosts, photoPosts, type CategoryBox } from "@/lib/home";
import type { Post } from "@/lib/posts";
import { FEATURED_TOOL, type Tool } from "@/lib/tools";
import { formatPublishedDate } from "@/lib/format";
import { PostThumb } from "./post-thumb";
import { ToolBadge, ToolRank, ToolVisual } from "./tool-rank";

export function HomeSections({ posts }: { posts: Post[] }) {
  const latest = latestPosts(posts);
  const boxes = categoryBoxes(posts);
  const photos = photoPosts(posts);
  const lead = latest[0];
  const rest = latest.slice(1);

  return (
    <div className="mx-auto grid w-full max-w-[1120px] items-start gap-8 px-4 py-6 lg:grid-cols-[minmax(0,1fr)_300px] lg:px-6 lg:py-8">
      <div className="flex min-w-0 flex-col gap-9">
        <FeaturedTool tool={FEATURED_TOOL} />
        <LatestSection lead={lead} rest={rest} />
        <div className="flex flex-col gap-4 lg:hidden">
          <ToolRank headingId="tool-rank-mobile" />
          <IntroCard />
        </div>
        {boxes.length >= 2 ? <CategoryGrid boxes={boxes} /> : null}
        {photos.length >= 3 ? <PhotoGuide posts={photos} /> : null}
      </div>
      <aside className="hidden lg:sticky lg:top-20 lg:block">
        <div className="flex flex-col gap-4">
          <ToolRank headingId="tool-rank-desktop" />
          <IntroCard />
        </div>
      </aside>
    </div>
  );
}

function FeaturedTool({ tool }: { tool: Tool }) {
  const inner = (
    <>
      <div className="flex items-center gap-2 px-5 pt-4">
        <span className="rounded-full bg-[#0b8ec8] px-2 py-0.5 text-[11px] font-extrabold tracking-[0.08em] text-white">
          HOT
        </span>
        <h2 id="featured-tool-heading" className="text-[15px] font-extrabold tracking-[-0.03em] text-[#121417]">
          오늘의 추천 툴
        </h2>
      </div>
      <div className="mt-3 grid md:grid-cols-[1.4fr_0.85fr]">
        <ToolVisual
          tool={tool}
          alt={tool.imageAlt}
          eager
          className="aspect-[16/9] h-full w-full md:aspect-auto md:min-h-[230px]"
        />
        <div className="flex flex-col justify-center px-5 py-5">
          <ToolBadge live={tool.live} />
          <p className="mt-2 text-[1.45rem] font-extrabold leading-snug tracking-[-0.04em] text-[#121417]">
            {tool.name}
          </p>
          <p className="mt-2 text-[14px] leading-6 text-[#5c6675]">{tool.description}</p>
          {tool.live && tool.href ? (
            <span className="mt-4 text-[14px] font-bold text-[#0b8ec8]">바로 가기 →</span>
          ) : null}
        </div>
      </div>
    </>
  );

  return (
    <section aria-labelledby="featured-tool-heading">
      {tool.live && tool.href ? (
        <a
          href={tool.href}
          target="_blank"
          rel="noopener noreferrer"
          className="block overflow-hidden rounded-[22px] border border-[#e8edf3] bg-white shadow-[0_10px_32px_rgba(18,20,23,0.05)] transition duration-200 hover:-translate-y-0.5"
        >
          {inner}
        </a>
      ) : (
        <div className="overflow-hidden rounded-[22px] border border-[#e8edf3] bg-white shadow-[0_10px_32px_rgba(18,20,23,0.05)]">
          {inner}
        </div>
      )}
    </section>
  );
}

function LatestSection({ lead, rest }: { lead?: Post; rest: Post[] }) {
  return (
    <section aria-labelledby="latest-heading">
      <div className="mb-3 flex items-end justify-between gap-3">
        <h2 id="latest-heading" className="text-[20px] font-extrabold tracking-[-0.04em] text-[#121417]">
          최신 글
        </h2>
        <Link href="/blog/" className="text-[13px] font-bold text-[#0b8ec8]">
          전체 보기
        </Link>
      </div>
      {lead ? (
        <div className="flex flex-col gap-3">
          <LeadPost post={lead} />
          {rest.map((post) => (
            <PostRow key={post.slug} post={post} />
          ))}
        </div>
      ) : (
        <div className="rounded-[22px] border border-[#e8edf3] bg-white px-6 py-12 text-center shadow-[0_8px_28px_rgba(18,20,23,0.04)]">
          <p className="text-[18px] font-extrabold tracking-[-0.03em] text-[#121417]">글 준비중</p>
          <p className="mt-2 text-[14px] leading-6 text-[#6b7280]">
            새 글이 올라오면 이곳에 소개합니다.
          </p>
          <Link
            href="/tools/"
            className="mt-4 inline-flex text-[14px] font-bold text-[#0b8ec8]"
          >
            툴 먼저 둘러보기 →
          </Link>
        </div>
      )}
    </section>
  );
}

function LeadPost({ post }: { post: Post }) {
  return (
    <Link
      href={postPath(post.slug)}
      className="block overflow-hidden rounded-[22px] border border-[#e8edf3] bg-white shadow-[0_10px_32px_rgba(18,20,23,0.05)] transition duration-200 hover:-translate-y-0.5"
    >
      <PostThumb post={post} eager alt={post.thumbnailAlt} className="aspect-[16/9] w-full" />
      <span className="block px-5 py-4">
        <span className="text-[13px] font-bold text-[#0b8ec8]">{post.category}</span>
        <span className="mt-1 block text-[1.35rem] font-extrabold leading-snug tracking-[-0.04em] text-[#121417]">
          {post.title}
        </span>
        <time dateTime={post.date} className="mt-2 block text-[13px] text-[#8b93a1]">
          {formatPublishedDate(post.date)}
        </time>
      </span>
    </Link>
  );
}

function PostRow({ post }: { post: Post }) {
  return (
    <Link
      href={postPath(post.slug)}
      className="flex items-center gap-3 rounded-[18px] border border-[#e8edf3] bg-white p-2.5 shadow-[0_6px_20px_rgba(18,20,23,0.04)] transition duration-200 hover:-translate-y-0.5 sm:gap-4 sm:p-3"
    >
      <PostThumb post={post} className="h-[76px] w-[104px] shrink-0 rounded-xl sm:h-[84px] sm:w-[120px]" />
      <span className="min-w-0 flex-1 py-1">
        <span className="block text-[15px] font-bold leading-snug tracking-[-0.03em] text-[#121417] sm:text-[16px]">
          {post.title}
        </span>
        <span className="mt-1.5 block text-[12px] text-[#8b93a1]">
          {post.category}
          <span aria-hidden="true"> · </span>
          <time dateTime={post.date}>{formatPublishedDate(post.date)}</time>
        </span>
      </span>
    </Link>
  );
}

function CategoryGrid({ boxes }: { boxes: CategoryBox[] }) {
  return (
    <section aria-labelledby="category-heading">
      <h2 id="category-heading" className="mb-3 text-[20px] font-extrabold tracking-[-0.04em] text-[#121417]">
        분류별 글
      </h2>
      <div className="grid grid-cols-2 gap-3">
        {boxes.map((box) => (
          <article
            key={box.id}
            className="min-w-0 rounded-[18px] border border-[#e8edf3] bg-white p-3.5 shadow-[0_6px_20px_rgba(18,20,23,0.04)] sm:p-4"
          >
            <h3 className="border-b border-[#eef2f6] pb-2 text-[14px] font-extrabold leading-snug tracking-[-0.03em] text-[#121417] sm:text-[15px]">
              {box.categories.map((category, index) => (
                <span key={category}>
                  {index > 0 ? <span aria-hidden="true">·</span> : null}
                  <Link href={categoryPath(categorySlug(category))} className="hover:text-[#0b8ec8]">
                    {category}
                  </Link>
                </span>
              ))}
            </h3>
            <ul className="mt-2.5 flex flex-col gap-2">
              {box.posts.map((post) => (
                <li key={post.slug}>
                  <Link
                    href={postPath(post.slug)}
                    className="line-clamp-2 text-[13px] font-semibold leading-5 tracking-[-0.02em] text-[#1f2937] hover:text-[#0b8ec8]"
                  >
                    {post.title}
                  </Link>
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </section>
  );
}

function PhotoGuide({ posts }: { posts: Post[] }) {
  return (
    <section aria-labelledby="photo-heading">
      <h2 id="photo-heading" className="mb-3 text-[20px] font-extrabold tracking-[-0.04em] text-[#121417]">
        사진으로 보는 가이드
      </h2>
      <div className="grid grid-cols-2 gap-3">
        {posts.map((post) => (
          <Link
            key={post.slug}
            href={postPath(post.slug)}
            className="group relative block aspect-[4/3] overflow-hidden rounded-[18px] bg-[#e7f6fd]"
          >
            <PostThumb
              post={post}
              eager
              alt={post.thumbnailAlt}
              className="absolute inset-0 h-full w-full transition duration-300 group-hover:scale-[1.03]"
            />
            <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 via-black/35 to-transparent px-3 pb-3 pt-10">
              <span className="line-clamp-2 text-[13px] font-bold leading-snug tracking-[-0.02em] text-white sm:text-[14px]">
                {post.title}
              </span>
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

function IntroCard() {
  return (
    <Link
      href="/about/"
      className="block rounded-[22px] bg-[#111111] px-5 py-5 text-white shadow-[0_10px_28px_rgba(0,0,0,0.12)] transition duration-200 hover:-translate-y-0.5"
    >
      <p className="text-[12px] font-bold tracking-[0.08em] text-[#7dd3fc]">마이멜로</p>
      <p className="mt-2 text-[15px] font-bold leading-6 tracking-[-0.03em]">
        아이와 부모의 오늘을 가볍고 부드럽게 만들어 주는 소중한 조력자입니다.
      </p>
      <span className="mt-4 inline-flex text-[13px] font-bold text-[#7dd3fc]">소개 보기 →</span>
    </Link>
  );
}
