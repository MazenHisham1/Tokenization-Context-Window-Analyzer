import type { Segment } from "./segments";
import type { Token } from "./types";

/** Index (into `segments`) of the chip to focus after `key`, or undefined if the key is not a navigation key.
 *  Gaps (the text between coloured blocks) are skipped. */
export function nextChip(segments: Segment[], current: number | null, key: string): number | undefined {
  const nav = segments.flatMap((s, i) => (s.kind === "gap" ? [] : [i]));
  if (nav.length === 0) return undefined;
  const pos = current === null ? -1 : nav.indexOf(current);
  switch (key) {
    case "ArrowRight":
    case "ArrowDown":
      return nav[Math.min(pos + 1, nav.length - 1)];
    case "ArrowLeft":
    case "ArrowUp":
      return nav[pos === -1 ? nav.length - 1 : Math.max(pos - 1, 0)];
    case "Home":
      return nav[0];
    case "End":
      return nav[nav.length - 1];
    default:
      return undefined;
  }
}

/** Make whitespace audible: a screen reader says nothing for " " or "\n". */
export function speak(s: string): string {
  if (s === "") return "empty";
  const spoken = s.replace(/\r?\n|\t| +/g, (run, index: number) => {
    if (run === "\t") return " tab ";
    if (run[0] !== " ") return " new line ";
    if (run.length > 1) return ` ${run.length} spaces `;
    return index === 0 || index + 1 === s.length ? " space " : " "; // a single space between words needs no announcement
  });
  return spoken.replace(/\s+/g, " ").trim();
}

/** The sentence a screen reader announces for the focused chip. */
export function describeSegment(seg: Segment, tokens: Token[]): string {
  const first = tokens[seg.tokenIdx[0]];
  if (seg.kind === "shared") {
    const ids = seg.tokenIdx.slice(0, 6).map((n) => tokens[n].id).join(", ");
    const more = seg.tokenIdx.length > 6 ? ` and ${seg.tokenIdx.length - 6} more` : "";
    return `${seg.tokenIdx.length} tokens share the text ${speak(seg.text)}. The tokenizer has no single token for it, so it falls back to raw bytes. IDs ${ids}${more}. Bytes ${seg.byteStart} to ${seg.byteEnd}.`;
  }
  const text = seg.charEnd === seg.charStart ? "no visible text" : speak(seg.text);
  return `Token ${seg.tokenIdx[0] + 1}: ${text}. ID ${first.id}. Bytes ${first.start} to ${first.end}.`;
}
