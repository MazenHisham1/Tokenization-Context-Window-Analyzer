import { TokenChips } from "./TokenChips";
import type { CompareResult } from "./types";

const PANEL_CHIPS = 1000; // four panels of 2,000 coloured blocks would be slow

/** The same text, one panel per tokenizer. */
export function ComparePanels({ text, results, showWhitespace }: {
  text: string; results: CompareResult[]; showWhitespace: boolean;
}) {
  return (
    <div className="panels">
      {results.map((r) => (
        <article key={r.name} className="panel" aria-label={`${r.name} tokens`}>
          <header>
            <h3>{r.name}</h3>
            {!r.exact && <span className="badge">estimate</span>}
            {r.count !== null && <span className="muted">{r.count.toLocaleString()} tokens</span>}
          </header>
          {r.error ? (
            <p className="error-text">Could not run: {r.error}</p>
          ) : !r.has_tokens ? (
            <p className="muted">Estimate only: there is no token breakdown to show.</p>
          ) : (
            <TokenChips text={text} tokens={r.tokens} label={`${r.name}: text coloured by token`} showWhitespace={showWhitespace} compact
              maxChips={PANEL_CHIPS} totalTokens={r.count ?? undefined} />
          )}
        </article>
      ))}
    </div>
  );
}
