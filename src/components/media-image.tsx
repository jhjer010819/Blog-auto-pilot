import type { ImgHTMLAttributes } from "react";

export function MediaImage({
  alt,
  ...props
}: ImgHTMLAttributes<HTMLImageElement> & { alt: string }) {
  return <img alt={alt} {...props} />;
}
