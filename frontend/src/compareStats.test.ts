import { describe, expect, it } from "vitest";
import { buildRows, formatVs, summaryLine } from "./compareStats";
import type { CompareResult } from "./types";

const r = (name: string, count: number | null, exact = true, error: string | null = null): CompareResult => ({
  name, family: "", algorithm: "", exact, has_tokens: exact, count, chars_per_token: null,
  tokens: [], truncated: false, error,
});

describe("buildRows", () => {
  it("sorts by count, fewest first, and marks the fewest", () => {
    const { rows, fewest } = buildRows([r("b", 24), r("a", 20), r("c", 21)]);
    expect(rows.map((x) => x.result.name)).toEqual(["a", "c", "b"]);
    expect(fewest).toBe(20);
    expect(rows.map((x) => x.isFewest)).toEqual([true, false, false]);
  });

  it("makes the largest count a full bar and scales the others", () => {
    const { rows } = buildRows([r("a", 10), r("b", 20)]);
    expect(rows.map((x) => x.share)).toEqual([0.5, 1]);
  });

  it("keeps request order for equal counts", () => {
    const { rows } = buildRows([r("x", 7), r("y", 7), r("z", 7)]);
    expect(rows.map((x) => x.result.name)).toEqual(["x", "y", "z"]);
    expect(rows.every((x) => x.isFewest)).toBe(true);
  });

  it("puts failed tokenizers last", () => {
    const { rows } = buildRows([r("bad", null, true, "offline"), r("a", 5)]);
    expect(rows.map((x) => x.result.name)).toEqual(["a", "bad"]);
    expect(rows[1]).toMatchObject({ share: 0, vsFewest: null, isFewest: false });
  });

  it("never lets an estimate be the fewest, and uses real tokenizers as the baseline", () => {
    const { rows, fewest } = buildRows([r("real", 13), r("guess", 9, false)]);
    expect(fewest).toBe(13);
    const guess = rows.find((x) => x.result.name === "guess")!;
    expect(guess.isFewest).toBe(false);
    expect(formatVs(guess)).toBe("−31%"); // an estimate can be LOWER than the real count
  });

  it("has no baseline when there are no exact results", () => {
    const { rows, fewest } = buildRows([r("guess", 9, false)]);
    expect(fewest).toBeNull();
    expect(formatVs(rows[0])).toBe("");
  });

  it("copes with no results and with zero counts", () => {
    expect(buildRows([]).rows).toEqual([]);
    expect(buildRows([r("a", 0), r("b", 0)]).rows.map((x) => x.share)).toEqual([0, 0]);
  });
});

describe("formatVs", () => {
  const rows = buildRows([r("a", 20), r("b", 24), r("c", 2001), r("d", 20, true)]).rows;
  it("says fewest, plus percent", () => {
    expect(formatVs(rows[0])).toBe("fewest");
    expect(formatVs(rows.find((x) => x.result.name === "b")!)).toBe("+20%");
  });
  it("shows +<1% instead of a misleading +0%", () => {
    expect(formatVs(rows.find((x) => x.result.name === "c")!)).toBe("+9905%");
    const tiny = buildRows([r("a", 1000), r("b", 1001)]).rows[1];
    expect(formatVs(tiny)).toBe("+<1%");
  });
});

describe("summaryLine", () => {
  it("compares the most and the fewest real tokenizers", () => {
    expect(summaryLine(buildRows([r("o200k", 20), r("gemma", 24), r("llama", 21)]).rows)).toBe(
      "gemma needs 20% more tokens than o200k (24 against 20).");
  });
  it("says so when all counts are equal", () => {
    expect(summaryLine(buildRows([r("a", 7), r("b", 7)]).rows)).toBe("All 2 tokenizers give the same count (7).");
  });
  it("ignores estimates and needs two real tokenizers", () => {
    expect(summaryLine(buildRows([r("a", 7), r("guess", 3, false)]).rows)).toBeNull();
    expect(summaryLine([])).toBeNull();
  });
});
