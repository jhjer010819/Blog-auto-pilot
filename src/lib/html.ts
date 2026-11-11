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

const LEADING_HEADING = /^<h[1-6]\b[^>]*>[\s\S]*?<\/h[1-6]>/i;
const SENTENCE_END = new Set([".", "!", "?", "…", "。"]);
const DESCRIPTION_CEILING = 180;
const DESCRIPTION_HARD_MAX = 200;
const DESCRIPTION_TARGET = 120;

export function introFromHtml(html: string) {
  let rest = html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, " ")
    .trim();
  for (
    let leading = LEADING_HEADING.exec(rest);
    leading && leading.index === 0;
    leading = LEADING_HEADING.exec(rest)
  ) {
    rest = rest.slice(leading[0].length).trim();
  }
  const nextHeading = rest.search(/<h[1-6]\b/i);
  if (nextHeading >= 0) rest = rest.slice(0, nextHeading);
  return rest;
}

export function splitSentences(text: string) {
  const sentences: string[] = [];
  let start = 0;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index] ?? "";
    if (!SENTENCE_END.has(char)) continue;
    if (
      char === "." &&
      index > 0 &&
      index + 1 < text.length &&
      isDigit(text[index - 1] ?? "") &&
      isDigit(text[index + 1] ?? "")
    ) {
      continue;
    }
    let end = index + 1;
    while (end < text.length && SENTENCE_END.has(text[end] ?? "")) end += 1;
    if (end === text.length || /\s/.test(text[end] ?? "")) {
      const sentence = text.slice(start, end).trim();
      if (sentence) sentences.push(sentence);
      start = end;
      index = end - 1;
    }
  }
  const tail = text.slice(start).trim();
  if (tail) sentences.push(tail);
  return sentences;
}

export function descriptionFromPlain(text: string) {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!normalized) return "";
  const sentences = splitSentences(normalized);
  if (sentences.length === 0) return cutAtBoundary(normalized, DESCRIPTION_TARGET);
  let chosen = sentences[0] ?? "";
  if (sentences.length > 1) {
    const two = `${sentences[0]} ${sentences[1]}`;
    if (two.length <= DESCRIPTION_CEILING) chosen = two;
  }
  if (chosen.length <= DESCRIPTION_HARD_MAX) return chosen;
  return cutAtBoundary(chosen, DESCRIPTION_TARGET);
}

export function excerptFromHtml(html: string) {
  return descriptionFromPlain(textFromHtml(introFromHtml(html)));
}

function cutAtBoundary(text: string, limit: number) {
  if (text.length <= limit) return text;
  const window = text.slice(0, limit);
  let best = -1;
  for (let index = 0; index < window.length; index += 1) {
    if (" ,，、;；:：".includes(window[index] ?? "")) best = index;
  }
  if (best >= 40) return window.slice(0, best).replace(/[\s,，、;；:：]+$/u, "");
  return text;
}

function isDigit(char: string) {
  return char >= "0" && char <= "9";
}
