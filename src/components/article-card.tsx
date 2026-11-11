import Link from "next/link";
import { formatPublishedDate } from "@/lib/format";
import type { Post } from "@/lib/posts";

export function ArticleCard({ post, eager = false }: { post: Post; eager?: boolean }) {
  return (
    <li>
      <Link
        href={`/posts/${post.slug}/`}
        className="flex items-center gap-3.5 rounded-[18px] bg-white p-3.5 shadow-[0_8px_28px_rgba(22,34,61,0.05)] transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_14px_34px_rgba(22,34,61,0.08)] sm:gap-4 sm:p-4"
      >
        {post.thumbnail ? (
          <img
            src={post.thumbnail}
            alt={post.thumbnailAlt}
            width={176}
            height={176}
            loading={eager ? "eager" : "lazy"}
            className="h-[76px] w-[76px] shrink-0 rounded-[14px] object-cover sm:h-[88px] sm:w-[88px]"
          />
        ) : (
          <span className="grid h-[76px] w-[76px] shrink-0 place-items-center rounded-[14px] bg-[#e8f1ff] text-[13px] font-bold text-[#3a74f2] sm:h-[88px] sm:w-[88px]">
            {post.category.slice(0, 2)}
          </span>
        )}
        <span className="min-w-0 flex-1 py-0.5">
          <span className="inline-flex rounded-md bg-[#e8f1ff] px-2 py-0.5 text-[12px] font-semibold leading-5 text-[#3a74f2]">
            {post.category}
          </span>
          <h3 className="mt-2 text-[16px] font-bold leading-snug tracking-[-0.02em] text-[#16181d] sm:text-[17px]">
            {post.title}
          </h3>
          <time dateTime={post.date} className="mt-1.5 block text-[13px] text-[#9aa3b5]">
            {formatPublishedDate(post.date)}
          </time>
        </span>
      </Link>
    </li>
  );
}
