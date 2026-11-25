import { buildRows, formatVs, summaryLine } from "./compareStats";
import type { CompareResult } from "./types";

const ANTHROPIC_DOCS = "https://platform.claude.com/docs/en/build-with-claude/token-counting";

/** One table that is also the bar chart: the length of each bar is the token count.
 *  Because the numbers are real text in the table, nothing depends on colour or on seeing the bars. */
export function ComparisonTable({ results }: { results: CompareResult[] }) {
  const { rows } = buildRows(results);
  const summary = summaryLine(rows);
  const estimates = results.filter((r) => !r.exact && r.count !== null);

  return (
    <section aria-labelledby="cmp-title">
      <h2 id="cmp-title">Token count for the same text</h2>
      {summary && <p className="summary">{summary}</p>}

      <div className="table-wrap">
        <table className="compare-table">
          <thead>
            <tr>
              <th scope="col">Tokenizer</th>
              <th scope="col">Tokens</th>
              <th scope="col">vs fewest</th>
              <th scope="col">Chars / token</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ result: r, share, isFewest, ...rest }) => (
              <tr key={r.name} className={r.error ? "row-error" : undefined}>
                <th scope="row">
                  {r.name}
                  {!r.exact && <span className="badge">estimate</span>}
                  <div className="muted small">{r.family}</div>
                </th>
                {r.error ? (
                  <td colSpan={3} className="error-text">
                    Could not run: {r.error}
                  </td>
                ) : (
                  <>
                    <td className="bar-cell">
                      <div className="bar-track" aria-hidden="true">
                        <div className={`bar${r.exact ? "" : " estimate"}`} style={{ width: `${Math.max(share * 100, 2)}%` }} />
                      </div>
                      <span className="bar-value">{(r.count as number).toLocaleString()}</span>
                    </td>
                    <td>
                      {!r.exact && "≈ "}
                      {formatVs({ result: r, share, isFewest, ...rest })}
                    </td>
                    <td>{r.chars_per_token ?? "–"}</td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {estimates.length > 0 && (
        <p className="note">
          <strong>Striped bars are estimates, not tokenizers.</strong> {estimates.map((e) => e.name).join(", ")} only
          guesses a count, so it has no tokens to show and is never marked as fewest. Not every vendor publishes a
          tokenizer you can run: Anthropic, for example, offers a{" "}
          <a href={ANTHROPIC_DOCS} target="_blank" rel="noreferrer">token-counting API</a>, and its docs call the
          result an estimate that depends on the model. A fixed rule such as "characters ÷ 4" also hides how much
          languages differ, so compare it with the real tokenizers above on Arabic or emoji text.
        </p>
      )}
    </section>
  );
}
