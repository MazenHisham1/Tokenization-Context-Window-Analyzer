// Turns the server's tokens (byte spans) into pieces of the ORIGINAL text that the UI
// can colour. Everything here is pure functions, so it is easy to test.
//
// Why this is not trivial:
//  * The server gives UTF-8 BYTE offsets. JavaScript strings are UTF-16, so we count in
//    Unicode code points: [..."😊"] has length 1 (the string's .length would say 2).
//  * One character can be split into several byte tokens (an emoji the tokenizer does not
//    know). Those tokens share one character, so we show them as ONE "shared" chip.
//  * Some tokenizers (WordPiece) drop spaces, so parts of the text can have no token.
//    Those parts become "gap" segments, so the text we show is always the complete text.
import type { Token } from "./types";

export type SegmentKind = "token" | "shared" | "gap";

export interface Segment {
  kind: SegmentKind;
  text: string; // the original characters this segment covers
  charStart: number; // code-point index, inclusive
  charEnd: number; // code-point index, exclusive
  byteStart: number; // smallest byte offset among its tokens (0 for gaps)
  byteEnd: number; // largest byte offset among its tokens (0 for gaps)
  tokenIdx: number[]; // positions in the token list (empty for gaps)
  color: number; // 0, 1, 2... counted per coloured segment; the UI uses color % palette size
}

function utf8Len(codePoint: number): number {
  if (codePoint < 0x80) return 1;
  if (codePoint < 0x800) return 2;
  if (codePoint < 0x10000) return 3;
  return 4;
}

/** offsets[i] = byte offset where character i starts; the last item is the total byte length. */
export function byteOffsets(chars: string[]): number[] {
  const offsets = [0];
  for (const ch of chars) offsets.push(offsets[offsets.length - 1] + utf8Len(ch.codePointAt(0)!));
  return offsets;
}

/** first index whose value is > x */
function upperBound(a: number[], x: number): number {
  let lo = 0, hi = a.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (a[mid] <= x) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** first index whose value is >= x */
function lowerBound(a: number[], x: number): number {
  let lo = 0, hi = a.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (a[mid] < x) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** Byte spans -> [charStart, charEnd) spans. A token holding only part of a character gets
 *  the span of the whole character (same rule as char_spans() in the Python engine). */
export function charSpans(
  chars: string[],
  tokens: Pick<Token, "start" | "end">[],
): [number, number][] {
  const offsets = byteOffsets(chars);
  const n = chars.length;
  return tokens.map((t) => {
    const s = Math.min(Math.max(upperBound(offsets, t.start) - 1, 0), n);
    const e = Math.min(lowerBound(offsets, t.end), n);
    return [s, Math.max(s, e)];
  });
}

export function buildSegments(text: string, tokens: Token[]): Segment[] {
  const chars = [...text];
  const spans = charSpans(chars, tokens);
  const segments: Segment[] = [];
  let cursor = 0; // characters before this index are already placed in a segment
  let color = 0;

  const gap = (from: number, to: number) =>
    segments.push({
      kind: "gap", text: chars.slice(from, to).join(""), charStart: from, charEnd: to,
      byteStart: 0, byteEnd: 0, tokenIdx: [], color: -1,
    });

  let i = 0;
  while (i < tokens.length) {
    let [start, end] = spans[i];
    const members = [i];
    // Tokens that share a character with this one belong to the same segment.
    while (members[members.length - 1] + 1 < tokens.length) {
      const j = members[members.length - 1] + 1;
      const [s2, e2] = spans[j];
      if (s2 >= end) break;
      members.push(j);
      start = Math.min(start, s2);
      end = Math.max(end, e2);
    }
    if (start > cursor) gap(cursor, start);
    segments.push({
      kind: members.length > 1 ? "shared" : "token",
      text: chars.slice(start, end).join(""),
      charStart: start,
      charEnd: end,
      byteStart: Math.min(...members.map((m) => tokens[m].start)),
      byteEnd: Math.max(...members.map((m) => tokens[m].end)),
      tokenIdx: members,
      color: color++,
    });
    cursor = Math.max(cursor, end);
    i = members[members.length - 1] + 1;
  }
  if (cursor < chars.length) gap(cursor, chars.length);
  return segments;
}

export interface WordSplit {
  word: string;
  parts: string[]; // the text of each segment the word touches
}

const WORD_CHAR = /[\p{L}\p{M}\p{N}]/u; // letters, accent marks, digits (any language)

/** Words are runs of letters and digits in any language. Returns [start, end) character spans. */
export function findWords(chars: string[]): [number, number][] {
  const words: [number, number][] = [];
  for (let i = 0; i < chars.length; ) {
    if (!WORD_CHAR.test(chars[i])) { i++; continue; }
    let j = i;
    while (j < chars.length && WORD_CHAR.test(chars[j])) j++;
    words.push([i, j]);
    i = j;
  }
  return words;
}

/** For each word, the text of the segments it touches (empty list = no token covers it).
 *  clip = false keeps a segment whole, so " price" shows that the space belongs to the token.
 *  clip = true cuts every segment to the word, so only the word's own letters remain; use it
 *  to compare tokenizers fairly (one may attach the space to the word, another may not). */
export function partsForWords(
  chars: string[], words: [number, number][], segments: Segment[], clip = false,
): string[][] {
  const coloured = segments.filter((s) => s.kind !== "gap" && s.charEnd > s.charStart);
  const result: string[][] = [];
  let k = 0;
  for (const [ws, we] of words) {
    while (k < coloured.length && coloured[k].charEnd <= ws) k++; // both lists are in order
    const parts: string[] = [];
    for (let m = k; m < coloured.length && coloured[m].charStart < we; m++) {
      const s = coloured[m];
      parts.push(clip ? chars.slice(Math.max(s.charStart, ws), Math.min(s.charEnd, we)).join("") : s.text);
    }
    result.push(parts);
  }
  return result;
}

/** Words made of several tokens. A leading space stays inside the part: " price". */
export function wordSplits(text: string, segments: Segment[]) {
  const chars = [...text];
  const words = findWords(chars);
  const allParts = partsForWords(chars, words, segments);
  const splits: WordSplit[] = [];
  const seen = new Set<string>();
  let splitCount = 0;
  words.forEach(([ws, we], i) => {
    if (allParts[i].length < 2) return;
    splitCount++;
    const word = chars.slice(ws, we).join("");
    if (!seen.has(word)) {
      seen.add(word);
      splits.push({ word, parts: allParts[i] });
    }
  });
  // Show the most-split words first (stable for equal counts).
  splits.sort((a, b) => b.parts.length - a.parts.length);
  return { splits, wordCount: words.length, splitCount };
}
