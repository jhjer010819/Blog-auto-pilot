import { categoryTone } from "@/lib/categories";
import { hasRenderableImage } from "@/lib/home";
import type { Post } from "@/lib/posts";
import { MediaImage } from "./media-image";

export function PostThumb({
  post,
  className,
  eager = false,
  alt,
}: {
  post: Post;
  className?: string;
  eager?: boolean;
  alt?: string;
}) {
  const tone = categoryTone(post.category);
  if (!hasRenderableImage(post) || !post.thumbnail) {
    return (
      <span
        aria-hidden="true"
        className={`grid place-items-center px-2 text-center text-[13px] font-extrabold tracking-[-0.03em] ${className ?? ""}`}
        style={{ background: tone.bg, color: tone.fg }}
      >
        {post.category}
      </span>
    );
  }

  return (
    <MediaImage
      src={post.thumbnail}
      alt={alt ?? post.thumbnailAlt}
      loading={eager ? "eager" : "lazy"}
      className={`object-cover ${className ?? ""}`}
    />
  );
}
