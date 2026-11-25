import { useMemo } from "react";
import { compareWords } from "./compareWords";
import { buildSegments } from "./segments";
import type { CompareResult } from "./types";
import { visible } from "./visible";

/** Which words did the tokenizers cut differently? Only words with a difference are listed. */
export function WordMatrix({ text, results }: { text: string; results: CompareResult[] }) {
  const usable = results.filter((r) => r.has_tokens && !r.error && r.count !== null);

  const comparison = useMemo(() => {
    const chars = [...text];
    const inputs = usable.map((r) => {
      const segments = buildSegments(text, r.tokens);
      const lastColoured = [...segments].reverse().find((s) => s.kind !== "gap");
      return { name: r.name, segments, coveredEnd: r.truncated ? (lastColoured?.charEnd ?? 0) : chars.length };
    });
    return compareWords(text, inputs);
  }, [text, usable]);

  if (usable.length < 2) return null;
  const { rows, comparedWords, differing = 0 } = comparison;

  return (
    <section aria-labelledby="wm-title" className="words">
      <h2 id="wm-title">Where the tokenizers disagree</h2>
      <p className="muted">
        {differing === 0
          ? `All ${comparedWords.toLocaleString()} words are cut the same way by every tokenizer.`
          : `${differing.toLocaleString()} of ${comparedWords.toLocaleString()} words are cut differently.`}{" "}
        Only the word itself is compared, not the space or punctuation next to it.
      </p>
      {rows.length > 0 && (
        <div className="table-wrap">
          <table className="word-matrix">
            <thead>
              <tr>
                <th scope="col">Word</th>
                {rows[0].cells.map((c) => (
                  <th key={c.name} scope="col">{c.name}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.word}>
                  <th scope="row" dir="auto">{row.word}</th>
                  {row.cells.map((c) => (
                    <td key={c.name}>
                      {c.parts.map((p, i) => (
                        <span key={i}>
                          {i > 0 && <span className="bar-sep" aria-hidden="true"> | </span>}
                          <span className="part" dir="auto">{visible(p)}</span>
                        </span>
                      ))}
                      <span className="muted small"> ({c.parts.length})</span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
