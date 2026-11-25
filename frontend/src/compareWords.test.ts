import { describe, expect, it } from "vitest";
import { compareWords } from "./compareWords";
import { buildSegments, findWords, partsForWords } from "./segments";
import type { Token } from "./types";

function fromPieces(pieces: string[]): Token[] {
  const enc = new TextEncoder();
  let pos = 0;
  return pieces.map((p, id) => {
    const n = enc.encode(p).length;
    const t = { id, text: p, piece: p, start: pos, end: pos + n };
    pos += n;
    return t;
  });
}
const input = (name: string, text: string, pieces: string[], coveredEnd = [...text].length) => ({
  name, segments: buildSegments(text, fromPieces(pieces)), coveredEnd,
});

describe("partsForWords", () => {
  const text = " price!";
  const chars = [...text];
  const segs = buildSegments(text, fromPieces([" price", "!"]));
  it("keeps the leading space when not clipping", () =>
    expect(partsForWords(chars, findWords(chars), segs)).toEqual([[" price"]]));
  it("cuts the parts to the word when clipping", () =>
    expect(partsForWords(chars, findWords(chars), segs, true)).toEqual([["price"]]));
});

describe("compareWords", () => {
  it("lists words that are split differently, biggest difference first", () => {
    const text = "The price 1234567";
    const a = input("o200k", text, ["The", " price", " ", "123", "456", "7"]);
    const b = input("gemma", text, ["The", " price", " ", "1", "2", "3", "4", "5", "6", "7"]);
    const { rows, comparedWords, totalWords } = compareWords(text, [a, b]);
    expect(rows).toHaveLength(1);
    expect(rows[0].word).toBe("1234567");
    expect(rows[0].cells.map((c) => c.parts.length)).toEqual([3, 7]);
    expect(rows[0].spread).toBe(4);
    expect([comparedWords, totalWords]).toEqual([3, 3]);
  });

  it("is not fooled by where a tokenizer puts the space or punctuation", () => {
    const text = "a price.";
    const a = input("x", text, ["a", " price", "."]);   // space inside the token, '.' separate
    const b = input("y", text, ["a", " ", "price."]);   // space separate, '.' inside the token
    expect(compareWords(text, [a, b]).rows).toEqual([]);
  });

  it("also reports a different split with the same number of tokens", () => {
    const text = "token";
    const { rows } = compareWords(text, [input("a", text, ["to", "ken"]), input("b", text, ["tok", "en"])]);
    expect(rows).toHaveLength(1);
    expect(rows[0].spread).toBe(0);
  });

  it("sorts by how much the tokenizers disagree", () => {
    const text = "token abcdef";
    const a = input("a", text, ["to", "ken", " ", "abcdef"]);
    const b = input("b", text, ["tok", "en", " ", "a", "b", "c", "d", "e", "f"]);
    expect(compareWords(text, [a, b]).rows.map((r) => r.word)).toEqual(["abcdef", "token"]);
  });

  it("lists a repeated word once", () => {
    const text = "ab ab";
    const a = input("a", text, ["a", "b", " ", "a", "b"]);
    const b = input("b", text, ["ab", " ", "ab"]);
    expect(compareWords(text, [a, b]).rows).toHaveLength(1);
  });

  it("only compares words that every tokenizer covered, when a token list was cut short", () => {
    const text = "ab cd";
    const a = input("a", text, ["a", "b"], 2);            // only covers 'ab'
    const b = input("b", text, ["ab", " ", "cd"], 5);
    const { rows, comparedWords } = compareWords(text, [a, b]);
    expect(comparedWords).toBe(1);
    expect(rows.map((r) => r.word)).toEqual(["ab"]);
  });

  it("needs at least two tokenizers", () => {
    const text = "ab";
    expect(compareWords(text, [input("a", text, ["a", "b"])]).rows).toEqual([]);
  });

  it("works for Arabic", () => {
    const text = "مرحبا";
    const { rows } = compareWords(text, [input("a", text, ["مر", "حبا"]), input("b", text, ["مرحبا"])]);
    expect(rows[0].cells.map((c) => c.parts)).toEqual([["مر", "حبا"], ["مرحبا"]]);
  });
});
