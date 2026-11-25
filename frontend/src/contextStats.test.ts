import { describe, expect, it } from "vitest";
import { buildBar, splitKept, summarize } from "./contextStats";
import type { SimMessageResult, SimulateResponse } from "./types";

function msg(i: number, status: SimMessageResult["status"], tokens: number, kept = status === "kept" ? tokens : 0): SimMessageResult {
  return { index: i, role: i === 0 ? "system" : "user", chars: tokens * 4, tokens, status, kept_tokens: kept, kept_chars: null };
}
function resp(over: Partial<SimulateResponse> = {}): SimulateResponse {
  const messages = [msg(0, "kept", 10), msg(1, "dropped", 50), msg(2, "kept", 20)];
  return { model: "m", tokenizer: "t", exact: true, strategy: "drop_oldest", context_window: 100, reserve_output: 20, budget: 80,
    per_message_overhead: 2, total_tokens: 86, used_tokens: 34, overflow_tokens: 6, fits: true, cannot_fit: false, nothing_fits: false, messages, ...over };
}

describe("buildBar", () => {
  it("shows kept messages, then free space, then the reserve, and leaves out dropped messages", () => {
    const { segments, limitPct } = buildBar(resp());
    expect(segments.map((s) => s.kind)).toEqual(["message", "message", "free", "reserve"]);
    expect(segments.map((s) => s.tokens)).toEqual([12, 22, 46, 20]); // overhead included, 80 - 34 = 46 free
    expect(segments.reduce((a, s) => a + s.pct, 0)).toBeCloseTo(100);
    expect(limitPct).toBeNull();
  });

  it("marks where the window ends when the content is bigger than the window", () => {
    const r = resp({ strategy: "error", used_tokens: 120, budget: 80, total_tokens: 120, overflow_tokens: 40, fits: false,
      messages: [msg(0, "kept", 108), msg(1, "kept", 8)] });
    const { segments, limitPct } = buildBar(r);
    expect(segments.some((s) => s.kind === "free")).toBe(false); // no free space when over budget
    expect(limitPct).toBeCloseTo((100 / 140) * 100); // 120 used + 20 reserved = 140 tokens against a window of 100
    expect(segments.at(-1)?.kind).toBe("reserve");
  });

  it("flags a cut message and omits the reserve when it is 0", () => {
    const r = resp({ reserve_output: 0, messages: [msg(0, "kept", 10), { ...msg(1, "partial", 50, 20), kept_chars: [0, 80] }] });
    const { segments } = buildBar(r);
    expect(segments.find((s) => s.partial)?.tokens).toBe(22);
    expect(segments.some((s) => s.kind === "reserve")).toBe(false);
  });
});

describe("summarize", () => {
  it("says everything fits", () => {
    const r = resp({ messages: [msg(0, "kept", 10), msg(1, "kept", 20)], overflow_tokens: 0 });
    expect(summarize(r)).toEqual({ tone: "ok", text: "Everything fits: 34 of 80 available tokens used." });
  });
  it("describes dropped messages", () => {
    const s = summarize(resp());
    expect(s.tone).toBe("warn");
    expect(s.text).toContain("6 tokens over the limit");
    expect(s.text).toContain("1 message dropped");
  });
  it("describes dropped and cut messages together, with plurals", () => {
    const r = resp({ messages: [msg(0, "kept", 1), msg(1, "dropped", 5), msg(2, "dropped", 5), { ...msg(3, "partial", 9, 4), kept_chars: [0, 3] }] });
    expect(summarize(r).text).toContain("2 messages dropped and 1 message cut");
  });
  it("explains that an API would reject the request", () => {
    const s = summarize(resp({ strategy: "error", fits: false, overflow_tokens: 1234 }));
    expect(s.tone).toBe("bad");
    expect(s.text).toContain("1,234 tokens over the limit");
    expect(s.text).toContain("reject");
  });
  it("handles system messages that are too big", () => {
    expect(summarize(resp({ cannot_fit: true, fits: false })).tone).toBe("bad");
  });
  it("is honest when not even the newest message fits", () => {
    expect(summarize(resp({ nothing_fits: true })).text).toContain("Not even the newest message fits");
  });
});

describe("splitKept", () => {
  it("returns the whole text when nothing was cut", () => {
    expect(splitKept("hello", null)).toEqual({ before: "", kept: "hello", after: "" });
  });
  it("splits by characters, not UTF-16 units (emoji count once)", () => {
    expect(splitKept("a😊bc😊d", [1, 4])).toEqual({ before: "a", kept: "😊bc", after: "😊d" });
  });
  it("keeps the start or the end", () => {
    expect(splitKept("abcdef", [0, 2])).toEqual({ before: "", kept: "ab", after: "cdef" });
    expect(splitKept("abcdef", [4, 6])).toEqual({ before: "abcd", kept: "ef", after: "" });
  });
});
