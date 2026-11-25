import { describe, expect, it } from "vitest";
import { buildSegments, charSpans, wordSplits } from "./segments";
import type { Token } from "./types";

/** Build tokens from byte-string pieces, like a byte-level tokenizer would. */
function fromBytes(parts: number[][]): Token[] {
  let pos = 0;
  return parts.map((p, id) => {
    const t = { id, text: "", piece: "", start: pos, end: pos + p.length };
    pos += p.length;
    return t;
  });
}
/** Build tokens from text pieces (the pieces must join to the full text). */
function fromPieces(pieces: string[]): Token[] {
  const enc = new TextEncoder();
  return fromBytes(pieces.map((p) => [...enc.encode(p)]));
}
const joined = (segs: { text: string }[]) => segs.map((s) => s.text).join("");

describe("charSpans", () => {
  it("is 1 to 1 for ASCII", () => {
    expect(charSpans([..."abc"], [{ start: 0, end: 1 }, { start: 1, end: 3 }])).toEqual([[0, 1], [1, 3]]);
  });
  it("counts an emoji as ONE character (4 bytes)", () => {
    expect(charSpans([..."a😊b"], [{ start: 1, end: 5 }, { start: 5, end: 6 }])).toEqual([[1, 2], [2, 3]]);
  });
  it("counts Arabic letters as 2 bytes each", () => {
    expect(charSpans([..."مرحبا"], [{ start: 0, end: 4 }, { start: 4, end: 10 }])).toEqual([[0, 2], [2, 5]]);
  });
  it("gives a half-character token the whole character", () => {
    expect(charSpans([..."😊"], [{ start: 0, end: 2 }, { start: 2, end: 4 }])).toEqual([[0, 1], [0, 1]]);
  });
  it("clamps spans that point outside the text", () => {
    expect(charSpans([..."ab"], [{ start: 5, end: 9 }])).toEqual([[2, 2]]);
  });
});

describe("buildSegments", () => {
  it("makes one segment per token and the text is complete", () => {
    const text = "low lowest";
    const segs = buildSegments(text, fromPieces(["low", " low", "est"]));
    expect(segs.map((s) => s.kind)).toEqual(["token", "token", "token"]);
    expect(segs.map((s) => s.text)).toEqual(["low", " low", "est"]);
    expect(joined(segs)).toBe(text);
  });

  it("gives neighbouring segments different colour numbers", () => {
    const segs = buildSegments("abcd", fromPieces(["a", "b", "c", "d"]));
    expect(segs.map((s) => s.color)).toEqual([0, 1, 2, 3]);
  });

  it("merges the byte tokens of one emoji into ONE shared segment", () => {
    const bytes = [[97], [0xf0], [0x9f], [0x98], [0x8a], [98]]; // a, 4 emoji bytes, b
    const segs = buildSegments("a😊b", fromBytes(bytes));
    expect(segs.map((s) => [s.kind, s.text])).toEqual([["token", "a"], ["shared", "😊"], ["token", "b"]]);
    expect(segs[1].tokenIdx).toEqual([1, 2, 3, 4]);
    expect([segs[1].byteStart, segs[1].byteEnd]).toEqual([1, 5]);
  });

  it("merges a token that ends inside an emoji with the neighbouring characters", () => {
    // "a" + first 2 bytes of the emoji in one token, then the last 2 bytes in the next
    const segs = buildSegments("a😊", fromBytes([[97, 0xf0, 0x9f], [0x98, 0x8a]]));
    expect(segs).toHaveLength(1);
    expect(segs[0]).toMatchObject({ kind: "shared", text: "a😊" });
  });

  it("keeps text that no token covers as gap segments (WordPiece drops spaces)", () => {
    const tokens: Token[] = [
      { id: 1, text: "hello", piece: "hello", start: 0, end: 5 },
      { id: 2, text: "world", piece: "world", start: 6, end: 11 },
    ];
    const segs = buildSegments("hello world", tokens);
    expect(segs.map((s) => [s.kind, s.text])).toEqual([["token", "hello"], ["gap", " "], ["token", "world"]]);
    expect(segs[1].color).toBe(-1);
  });

  it("covers leading and trailing text without tokens", () => {
    const tokens: Token[] = [{ id: 1, text: "b", piece: "b", start: 1, end: 2 }];
    expect(buildSegments("abc", tokens).map((s) => [s.kind, s.text])).toEqual([
      ["gap", "a"], ["token", "b"], ["gap", "c"],
    ]);
  });

  it("returns one gap when there are no tokens, and nothing for empty text", () => {
    expect(buildSegments("hi", []).map((s) => s.kind)).toEqual(["gap"]);
    expect(buildSegments("", [])).toEqual([]);
  });

  it("handles a token with no text (zero width)", () => {
    const segs = buildSegments("ab", [{ id: 9, text: "", piece: "[CLS]", start: 0, end: 0 }, ...fromPieces(["ab"])]);
    expect(segs[0]).toMatchObject({ kind: "token", text: "" });
    expect(joined(segs)).toBe("ab");
  });

  it("splits Arabic by characters, not bytes", () => {
    const segs = buildSegments("مرحبا", fromBytes([[1, 2, 3, 4], [5, 6, 7, 8, 9, 10]]));
    expect(segs.map((s) => s.text)).toEqual(["مر", "حبا"]);
  });

  it("never loses or repeats text, whatever the tokenization", () => {
    const text = "Hello 😊 مرحبا\n123";
    const enc = [...new TextEncoder().encode(text)];
    for (const size of [1, 2, 3, 5, 7]) {
      const parts: number[][] = [];
      for (let i = 0; i < enc.length; i += size) parts.push(enc.slice(i, i + size));
      expect(joined(buildSegments(text, fromBytes(parts)))).toBe(text);
    }
  });
});

describe("wordSplits", () => {
  it("lists words made of several tokens", () => {
    const pieces = ["un", "believ", "able", " price", " ", "123", "456", "7"];
    const text = pieces.join("");
    const { splits, wordCount, splitCount } = wordSplits(text, buildSegments(text, fromPieces(pieces)));
    expect(splits.map((s) => [s.word, s.parts])).toEqual([
      ["unbelievable", ["un", "believ", "able"]],
      ["1234567", ["123", "456", "7"]],
    ]);
    expect(wordCount).toBe(3);
    expect(splitCount).toBe(2);
  });

  it("does not count a word that is one token, even with a leading space", () => {
    const pieces = ["The", " price"];
    const text = pieces.join("");
    expect(wordSplits(text, buildSegments(text, fromPieces(pieces))).splits).toEqual([]);
  });

  it("ignores punctuation and emoji, which are not words", () => {
    const pieces = ["Hi", "!", " ", "😊"];
    const text = pieces.join("");
    const r = wordSplits(text, buildSegments(text, fromPieces(pieces)));
    expect(r.wordCount).toBe(1);
    expect(r.splits).toEqual([]);
  });

  it("works for Arabic words", () => {
    const text = "مرحبا";
    const r = wordSplits(text, buildSegments(text, fromPieces(["مر", "حبا"])));
    expect(r.splits[0]).toMatchObject({ word: "مرحبا", parts: ["مر", "حبا"] });
  });

  it("counts a repeated split word every time but lists it once", () => {
    const pieces = ["ab", "cd", " ", "ab", "cd"];
    const text = pieces.join("");
    const r = wordSplits(text, buildSegments(text, fromPieces(pieces)));
    expect(r.splitCount).toBe(2);
    expect(r.splits).toHaveLength(1);
  });
});
