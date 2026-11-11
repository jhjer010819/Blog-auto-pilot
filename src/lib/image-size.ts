import fs from "fs";
import path from "path";

const SOF_MARKERS = new Set([
  0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf,
]);

export function localImageSize(src: string) {
  if (!src.startsWith("/") || src.includes("..") || src.includes("\\") || src.includes("?")) {
    return undefined;
  }
  const filePath = path.join(process.cwd(), "public", src);
  const publicRoot = path.join(process.cwd(), "public");
  const resolved = path.resolve(filePath);
  if (!resolved.startsWith(`${publicRoot}${path.sep}`)) return undefined;
  let buffer: Buffer;
  try {
    buffer = fs.readFileSync(resolved);
  } catch {
    return undefined;
  }
  return sizeFromBuffer(buffer);
}

function sizeFromBuffer(buffer: Buffer) {
  const png = pngSize(buffer);
  if (png) return png;
  const jpeg = jpegSize(buffer);
  if (jpeg) return jpeg;
  return undefined;
}

function pngSize(buffer: Buffer) {
  if (buffer.length < 24) return undefined;
  const signature = buffer.subarray(0, 8).toString("hex");
  if (signature !== "89504e470d0a1a0a") return undefined;
  const width = buffer.readUInt32BE(16);
  const height = buffer.readUInt32BE(20);
  if (width === 0 || height === 0) return undefined;
  return { width, height };
}

function jpegSize(buffer: Buffer) {
  if (buffer.length < 4 || buffer[0] !== 0xff || buffer[1] !== 0xd8) return undefined;
  let offset = 2;
  while (offset + 8 < buffer.length) {
    if (buffer[offset] !== 0xff) {
      offset += 1;
      continue;
    }
    const marker = buffer[offset + 1];
    if (marker === 0xd8 || marker === 0x01) {
      offset += 2;
      continue;
    }
    if (marker === 0xd9 || marker === 0xda) return undefined;
    const length = buffer.readUInt16BE(offset + 2);
    if (length < 2 || offset + 2 + length > buffer.length) return undefined;
    if (SOF_MARKERS.has(marker)) {
      const height = buffer.readUInt16BE(offset + 5);
      const width = buffer.readUInt16BE(offset + 7);
      if (width > 0 && height > 0) return { width, height };
    }
    offset += 2 + length;
  }
  return undefined;
}
