import type { SimulateResponse } from "./types";

export type SegmentKind = "message" | "free" | "reserve";

export interface Segment {
  kind: SegmentKind;
  tokens: number;
  pct: number; // share of the bar, 0-100
  index?: number; // message number, for kind "message"
  role?: string;
  partial?: boolean;
}

export interface Bar {
  segments: Segment[];
  limitPct: number | null; // where the window ends, when the content runs past it; else null
}

/** The bar shows, left to right: the kept messages, the free space, the room reserved for the answer.
 *  If the content is bigger than the window the bar grows and a marker shows where the window ends. */
export function buildBar(r: SimulateResponse): Bar {
  const parts: Omit<Segment, "pct">[] = [];
  for (const m of r.messages) {
    if (m.status === "dropped") continue;
    parts.push({ kind: "message", tokens: m.kept_tokens + r.per_message_overhead, index: m.index, role: m.role, partial: m.status === "partial" });
  }
  const free = Math.max(0, r.budget - r.used_tokens);
  if (free > 0) parts.push({ kind: "free", tokens: free });
  if (r.reserve_output > 0) parts.push({ kind: "reserve", tokens: r.reserve_output });

  const total = parts.reduce((a, p) => a + p.tokens, 0) || 1;
  const segments = parts.map((p) => ({ ...p, pct: (p.tokens / total) * 100 }));
  const limitPct = total > r.context_window ? (r.context_window / total) * 100 : null;
  return { segments, limitPct };
}

export type Tone = "ok" | "warn" | "bad";

const n = (x: number) => x.toLocaleString("en-US");
const plural = (count: number, word: string) => `${count} ${word}${count === 1 ? "" : "s"}`;

/** One sentence that says what happened, and how serious it is. */
export function summarize(r: SimulateResponse): { tone: Tone; text: string } {
  const dropped = r.messages.filter((m) => m.status === "dropped").length;
  const cut = r.messages.filter((m) => m.status === "partial").length;

  if (r.cannot_fit) {
    return { tone: "bad", text: `The system messages alone (${n(r.used_tokens)} tokens) are bigger than the ${n(r.budget)} tokens available. Nothing else can be kept.` };
  }
  if (r.strategy === "error" && !r.fits) {
    return { tone: "bad", text: `${n(r.overflow_tokens)} tokens over the limit. Most APIs reject a request like this with an error instead of cutting anything.` };
  }
  if (dropped === 0 && cut === 0) {
    return { tone: "ok", text: `Everything fits: ${n(r.used_tokens)} of ${n(r.budget)} available tokens used.` };
  }
  const what = [dropped > 0 && `${plural(dropped, "message")} dropped`, cut > 0 && `${plural(cut, "message")} cut`].filter(Boolean).join(" and ");
  const lead = `The conversation is ${n(r.overflow_tokens)} tokens over the limit, so ${what}.`;
  if (r.nothing_fits) return { tone: "bad", text: `${lead} Not even the newest message fits.` };
  return { tone: "warn", text: `${lead} ${n(r.used_tokens)} of ${n(r.budget)} available tokens are used.` };
}

/** Split a message's text into the part that survives and the parts that were cut off. */
export function splitKept(text: string, keptChars: [number, number] | null): { before: string; kept: string; after: string } {
  if (!keptChars) return { before: "", kept: text, after: "" };
  const chars = [...text]; // code points, the same unit the server uses
  const [a, b] = keptChars;
  return { before: chars.slice(0, a).join(""), kept: chars.slice(a, b).join(""), after: chars.slice(b).join("") };
}
