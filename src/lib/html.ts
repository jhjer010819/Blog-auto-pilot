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

const DISCLAIMER_CLASS = "post-disclaimer";

const DISCLAIMER_SENTENCES = [
  "본 글은 정보 제공을 목적으로 작성되었으며, 정확한 진단 및 치료는 반드시 전문의와 상담하시기 바랍니다.",
  "정부 정책 및 지원 기준은 시기별로 개정될 수 있으므로 정확한 내용은 공식 기관 공고를 확인해 주세요.",
];

export function sanitizePostHtml(html: string) {
  return markDisclaimerParagraphs(sanitizeHtml(html, {
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
  }));
}

export function markDisclaimerParagraphs(html: string) {
  return html.replace(/<p\b([^>]*)>([\s\S]*?)<\/p>/gi, (_full, rawAttrs: string, inner: string) => {
    const attrs = rawAttrs ?? "";
    const text = textFromHtml(inner);
    const { found, rest } = leftoverAfterDisclaimers(text);
    if (!found) return `<p${attrs}>${inner}</p>`;
    if (!rest) return `<p${withDisclaimerClass(attrs)}>${inner}</p>`;
    if (inner.includes("<")) return `<p${attrs}>${inner}</p>`;
    return splitPlainDisclaimerParagraph(attrs, inner);
  });
}

function leftoverAfterDisclaimers(text: string) {
  let rest = text.replace(/\s+/g, " ").trim();
  let found = false;
  let changed = true;
  while (changed) {
    changed = false;
    for (const sentence of DISCLAIMER_SENTENCES) {
      if (!rest.includes(sentence)) continue;
      rest = rest.replace(sentence, " ").replace(/\s+/g, " ").trim();
      found = true;
      changed = true;
    }
  }
  return { found, rest };
}

function splitPlainDisclaimerParagraph(attrs: string, inner: string) {
  const pieces: { kind: "body" | "disclaimer"; text: string }[] = [];
  let rest = inner;
  while (rest.length > 0) {
    let earliest = -1;
    let sentence = "";
    for (const candidate of DISCLAIMER_SENTENCES) {
      const index = rest.indexOf(candidate);
      if (index !== -1 && (earliest === -1 || index < earliest)) {
        earliest = index;
        sentence = candidate;
      }
    }
    if (earliest === -1) {
      pieces.push({ kind: "body", text: rest });
      break;
    }
    if (earliest > 0) pieces.push({ kind: "body", text: rest.slice(0, earliest) });
    pieces.push({ kind: "disclaimer", text: sentence });
    rest = rest.slice(earliest + sentence.length);
  }

  const groups: { kind: "body" | "disclaimer"; text: string }[] = [];
  let pending = "";
  for (const piece of pieces) {
    if (!textFromHtml(piece.text)) {
      if (groups.length > 0) groups[groups.length - 1].text += piece.text;
      else pending += piece.text;
      continue;
    }
    const text = pending + piece.text;
    pending = "";
    const last = groups[groups.length - 1];
    if (last && last.kind === piece.kind) last.text += text;
    else groups.push({ kind: piece.kind, text });
  }
  if (pending && groups.length > 0) groups[groups.length - 1].text += pending;

  const bodyAttrs = withoutDisclaimerClass(attrs);
  return groups
    .map((group) => {
      const content = group.text.replace(/^\s+|\s+$/g, "");
      if (!content) return "";
      const tagAttrs = group.kind === "disclaimer" ? ` class="${DISCLAIMER_CLASS}"` : bodyAttrs;
      return `<p${tagAttrs}>${content}</p>`;
    })
    .filter(Boolean)
    .join("\n");
}

function withDisclaimerClass(attrs: string) {
  const match = /\bclass\s*=\s*"([^"]*)"/i.exec(attrs);
  if (match) {
    const classes = match[1].split(/\s+/).filter(Boolean);
    if (!classes.includes(DISCLAIMER_CLASS)) classes.push(DISCLAIMER_CLASS);
    const replaced = `class="${classes.join(" ")}"`;
    return `${attrs.slice(0, match.index)}${replaced}${attrs.slice(match.index + match[0].length)}`;
  }
  if (!attrs) return ` class="${DISCLAIMER_CLASS}"`;
  return `${attrs.startsWith(" ") ? "" : " "}${attrs} class="${DISCLAIMER_CLASS}"`;
}

function withoutDisclaimerClass(attrs: string) {
  const match = /\bclass\s*=\s*"([^"]*)"/i.exec(attrs);
  if (!match) return attrs;
  const classes = match[1].split(/\s+/).filter((name) => name && name !== DISCLAIMER_CLASS);
  const replaced = classes.length > 0 ? `class="${classes.join(" ")}"` : "";
  let next = `${attrs.slice(0, match.index)}${replaced}${attrs.slice(match.index + match[0].length)}`;
  next = next.replace(/[ \t]{2,}/g, " ").replace(/^[ \t]+$/, "");
  if (next && !next.startsWith(" ")) next = ` ${next}`;
  return next;
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
