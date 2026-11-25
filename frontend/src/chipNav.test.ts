import { describe, expect, it } from "vitest";
import { describeSegment, nextChip, speak } from "./chipNav";
import type { Segment } from "./segments";
import type { Token } from "./types";

const seg = (kind: Segment["kind"], text = "x", tokenIdx: number[] = [0]): Segment => ({
  kind, text, charStart: 0, charEnd: text.length, byteStart: 0, byteEnd: 1, tokenIdx, color: 0,
});
const SEGS = [seg("gap", " ", []), seg("token"), seg("gap", " ", []), seg("token"), seg("shared")]; // chips at 1, 3, 4

describe("nextChip", () => {
  it("moves right and left over chips and skips gaps", () => {
    expect(nextChip(SEGS, 1, "ArrowRight")).toBe(3);
    expect(nextChip(SEGS, 3, "ArrowLeft")).toBe(1);
    expect(nextChip(SEGS, 3, "ArrowDown")).toBe(4);
  });
  it("stops at both ends instead of wrapping", () => {
    expect(nextChip(SEGS, 4, "ArrowRight")).toBe(4);
    expect(nextChip(SEGS, 1, "ArrowLeft")).toBe(1);
  });
  it("starts at the right end for a first press", () => {
    expect(nextChip(SEGS, null, "ArrowRight")).toBe(1);
    expect(nextChip(SEGS, null, "ArrowLeft")).toBe(4);
    expect(nextChip(SEGS, null, "End")).toBe(4);
  });
  it("supports Home and End", () => {
    expect(nextChip(SEGS, 3, "Home")).toBe(1);
    expect(nextChip(SEGS, 3, "End")).toBe(4);
  });
  it("ignores other keys and empty lists", () => {
    expect(nextChip(SEGS, 1, "a")).toBeUndefined();
    expect(nextChip([seg("gap")], null, "ArrowRight")).toBeUndefined();
  });
});

describe("speak", () => {
  it("names whitespace", () => {
    expect(speak(" turns")).toBe("space turns");
    expect(speak("\n")).toBe("new line");
    expect(speak("a\tb")).toBe("a tab b");
    expect(speak("  ")).toBe("2 spaces");
    expect(speak("")).toBe("empty");
  });
});

describe("describeSegment", () => {
  const tokens = [{ id: 42, text: " turns", piece: "Ġturns", start: 12, end: 18 }] as Token[];
  it("describes a normal token", () => {
    expect(describeSegment(seg("token", " turns"), tokens)).toBe("Token 1: space turns. ID 42. Bytes 12 to 18.");
  });
  it("describes a character split into several byte tokens", () => {
    const many = [0, 1, 2].map((i) => ({ id: 100 + i, text: "", piece: "", start: i, end: i + 1 })) as Token[];
    const text = describeSegment({ ...seg("shared", "😊", [0, 1, 2]), byteEnd: 3 }, many);
    expect(text).toContain("3 tokens share the text 😊");
    expect(text).toContain("IDs 100, 101, 102");
  });
});
