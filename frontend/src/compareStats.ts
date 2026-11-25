// Numbers and wording for the comparison table. Pure functions, so they are easy to test.
import type { CompareResult } from "./types";

export interface Row {
  result: CompareResult;
  share: number; // bar length, 0..1, relative to the largest count
  vsFewest: number | null; // % more (or less) than the fewest EXACT count; null if unknown
  isFewest: boolean;
}

export function buildRows(results: CompareResult[]): { rows: Row[]; fewest: number | null } {
  const ok = results.filter((r) => r.count !== null);
  const exactCounts = ok.filter((r) => r.exact).map((r) => r.count as number);
  // The baseline is the fewest count among REAL tokenizers. An estimate never wins.
  const fewest = exactCounts.length ? Math.min(...exactCounts) : null;
  const largest = Math.max(1, ...ok.map((r) => r.count as number));

  const rows: Row[] = ok
    .map((r, i) => ({ r, i }))
    .sort((a, b) => (a.r.count as number) - (b.r.count as number) || a.i - b.i) // ties keep request order
    .map(({ r }) => ({
      result: r,
      share: (r.count as number) / largest,
      vsFewest: fewest ? (((r.count as number) - fewest) / fewest) * 100 : null,
      isFewest: r.exact && r.count === fewest,
    }));
  // Failed tokenizers go last, so a broken one never hides a result.
  for (const r of results.filter((r) => r.count === null)) {
    rows.push({ result: r, share: 0, vsFewest: null, isFewest: false });
  }
  return { rows, fewest };
}

/** "fewest", "+20%", "+<1%", "−31%" (an estimate can be lower), or "" when unknown. */
export function formatVs(row: Row): string {
  if (row.isFewest) return "fewest";
  const p = row.vsFewest;
  if (p === null) return "";
  const rounded = Math.round(p);
  if (p > 0 && rounded === 0) return "+<1%";
  if (p < 0 && rounded === 0) return "−<1%";
  return rounded > 0 ? `+${rounded}%` : rounded < 0 ? `−${-rounded}%` : "same";
}

/** One sentence about the real tokenizers, or null when there is nothing to compare. */
export function summaryLine(rows: Row[]): string | null {
  const exact = rows.filter((r) => r.result.exact && r.result.count !== null);
  if (exact.length < 2) return null;
  const lo = exact[0].result, hi = exact[exact.length - 1].result;
  if (lo.count === hi.count) return `All ${exact.length} tokenizers give the same count (${lo.count}).`;
  const pct = Math.round((((hi.count as number) - (lo.count as number)) / (lo.count as number)) * 100);
  return `${hi.name} needs ${pct > 0 ? pct : "<1"}% more tokens than ${lo.name} (${hi.count} against ${lo.count}).`;
}
