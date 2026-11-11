import sanitizeHtml from "sanitize-html";

const ALLOWED_TAGS = [
  "p",
  "br",
  "hr",
  "h2",
  "h3",
  "h4",
  "ul",
  "ol",
  "li",
  "strong",
  "em",
  "b",
  "i",
  "a",
  "blockquote",
  "img",
  "figure",
  "figcaption",
  "table",
  "thead",
  "tbody",
  "tr",
  "th",
  "td",
  "code",
  "pre",
];

function isSafeImageSrc(src: string) {
  if (src.startsWith("/images/") && !src.includes("..") && !src.includes("\\")) {
    return true;
  }
  try {
    const url = new URL(src);
    return url.protocol === "https:" && !url.username && !url.password;
  } catch {
    return false;
  }
}

function isSafeHref(href: string) {
  if (href.startsWith("/") && !href.startsWith("//") && !href.includes("\\") && !href.includes("..")) {
    return true;
  }
  try {
    const url = new URL(href);
    return url.protocol === "https:" && !url.username && !url.password;
  } catch {
    return false;
  }
}

export function sanitizePostHtml(html: string) {
  return sanitizeHtml(html, {
    allowedTags: ALLOWED_TAGS,
    allowedAttributes: {
      a: ["href", "title", "target", "rel"],
      img: ["src", "alt", "title", "width", "height"],
      td: ["colspan", "rowspan"],
      th: ["colspan", "rowspan"],
    },
    allowedSchemes: ["https"],
    allowProtocolRelative: false,
    disallowedTagsMode: "discard",
    exclusiveFilter: (frame) => frame.tag === "img" && !isSafeImageSrc(frame.attribs.src ?? ""),
    transformTags: {
      a: (_tagName, attribs) => {
        const href = attribs.href ?? "";
        if (!isSafeHref(href)) {
          return { tagName: "a", attribs: {} };
        }
        const external = href.startsWith("https://");
        return {
          tagName: "a",
          attribs: {
            href,
            ...(external ? { target: "_blank", rel: "noopener noreferrer" } : {}),
          },
        };
      },
      img: (_tagName, attribs) => ({
        tagName: "img",
        attribs: {
          src: attribs.src ?? "",
          alt: attribs.alt ?? "",
          ...(attribs.width ? { width: attribs.width } : {}),
          ...(attribs.height ? { height: attribs.height } : {}),
        },
      }),
    },
  });
}

export function textFromHtml(html: string) {
  return html
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, " ")
    .trim();
}

export function excerptFromHtml(html: string, max = 140) {
  const text = textFromHtml(html);
  if (text.length <= max) return text;
  return `${text.slice(0, max).trim()}…`;
}
