import { useEffect, useState } from "react";
import { ApiError, tokenize } from "./api";
import { CopyIdsButton } from "./CopyIdsButton";
import { TokenChips } from "./TokenChips";
import { TokenTable } from "./TokenTable";
import type { TokenizeResponse, TokenizerInfo } from "./types";

// We keep the text together with its result. The text box may already show newer text
// than the one these tokens were made from, and the chips must use the matching text.
interface Analysis {
  text: string;
  data: TokenizeResponse;
}

type View = "chips" | "table";

interface Props {
  debouncedText: string;
  tokenizers: TokenizerInfo[]; // only the ones that can list tokens
}

/** One tokenizer, in detail: coloured text, tooltips, word splits, table. */
export function SingleView({ debouncedText, tokenizers }: Props) {
  const [selected, setSelected] = useState("");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState<View>("chips");
  const [showWhitespace, setShowWhitespace] = useState(true);

  // Pick the first tokenizer once the list has arrived.
  useEffect(() => {
    if (!selected && tokenizers.length > 0) setSelected(tokenizers[0].name);
  }, [selected, tokenizers]);

  // Whenever the (debounced) text or the tokenizer changes: tokenize.
  useEffect(() => {
    if (!selected) return;
    if (!debouncedText) {
      setAnalysis(null);
      setError(null);
      setLoading(false);
      return;
    }
    const ctrl = new AbortController(); // lets us cancel this request if inputs change again
    setLoading(true);
    setError(null);
    tokenize(debouncedText, selected, ctrl.signal)
      .then((data) => setAnalysis({ text: debouncedText, data }))
      .catch((e) => {
        if (e.name === "AbortError") return; // we cancelled it ourselves
        setAnalysis(null);
        setError(e instanceof ApiError ? e.message : `Cannot reach the server: ${e.message}`);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [debouncedText, selected]);

  const info = tokenizers.find((t) => t.name === selected);
  const result = analysis?.data ?? null;

  return (
    <>
      <div className="controls">
        <label>
          Tokenizer
          <select value={selected} onChange={(e) => setSelected(e.target.value)}>
            {tokenizers.map((t) => (
              <option key={t.name} value={t.name}>
                {t.name}
                {t.family ? ` (${t.family})` : ""}
              </option>
            ))}
          </select>
        </label>
        {info && <span className="muted">{info.algorithm || "algorithm not listed"}</span>}
      </div>

      <section aria-live="polite" className="stats">
        {loading && <span className="muted">Tokenizing…</span>}
        {!loading && result && (
          <>
            <Stat label="Tokens" value={result.count.toLocaleString()} />
            <Stat label="Characters" value={result.chars.toLocaleString()} />
            <Stat label="Bytes" value={result.bytes.toLocaleString()} />
            <Stat label="Chars / token" value={result.chars_per_token?.toString() ?? "–"} />
          </>
        )}
      </section>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      {analysis && result && result.tokens.length > 0 && (
        <>
          <div className="toolbar">
            <div className="seg-control" role="group" aria-label="View">
              <button type="button" aria-pressed={view === "chips"} onClick={() => setView("chips")}>
                Coloured text
              </button>
              <button type="button" aria-pressed={view === "table"} onClick={() => setView("table")}>
                Table
              </button>
            </div>
            {view === "chips" && (
              <label className="check">
                <input type="checkbox" checked={showWhitespace} onChange={(e) => setShowWhitespace(e.target.checked)} />
                Show spaces and new lines
              </label>
            )}
            <CopyIdsButton tokens={result.tokens} totalTokens={result.count} />
          </div>
          {view === "chips" ? (
            <TokenChips text={analysis.text} tokens={result.tokens} totalTokens={result.count} showWhitespace={showWhitespace} />
          ) : (
            <TokenTable tokens={result.tokens} totalTokens={result.count} />
          )}
        </>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
