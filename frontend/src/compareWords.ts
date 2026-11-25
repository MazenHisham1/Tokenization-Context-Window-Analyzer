// "Where do the tokenizers disagree?": the words that were split differently.
import { findWords, partsForWords, type Segment } from "./segments";

export interface TokenizerSegments {
  name: string;
  segments: Segment[];
  coveredEnd: number; // characters before this index have tokens (smaller than the text if truncated)
}

export interface WordRow {
  word: string;
  cells: { name: string; parts: string[] }[];
  spread: number; // most tokens minus fewest tokens for this word
}

export function compareWords(text: string, inputs: TokenizerSegments[], maxRows = 10) {
  const chars = [...text];
  const words = findWords(chars);
  if (inputs.length < 2) return { rows: [] as WordRow[], comparedWords: 0, totalWords: words.length };

  // If a tokenizer's token list was cut short, only compare the words ALL of them cover.
  const limit = Math.min(...inputs.map((i) => i.coveredEnd));
  const parts = inputs.map((i) => partsForWords(chars, words, i.segments, true)); // clip: compare the word itself

  const rows: WordRow[] = [];
  const seen = new Set<string>();
  let comparedWords = 0;
  words.forEach(([ws, we], w) => {
    if (we > limit) return;
    const cells = inputs.map((inp, k) => ({ name: inp.name, parts: parts[k][w] }));
    if (cells.some((c) => c.parts.length === 0)) return; // a tokenizer did not cover this word
    comparedWords++;
    const key = (p: string[]) => p.join("\u0000");
    if (cells.every((c) => key(c.parts) === key(cells[0].parts))) return; // everyone agrees
    const word = chars.slice(ws, we).join("");
    if (seen.has(word)) return; // list each word once
    seen.add(word);
    const counts = cells.map((c) => c.parts.length);
    rows.push({ word, cells, spread: Math.max(...counts) - Math.min(...counts) });
  });
  // Biggest disagreement first; keep text order for ties.
  rows.sort((a, b) => b.spread - a.spread);
  return { rows: rows.slice(0, maxRows), comparedWords, totalWords: words.length, differing: rows.length };
}
