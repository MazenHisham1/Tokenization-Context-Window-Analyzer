import { useEffect, useMemo, useState } from "react";
import { ApiError, compare } from "./api";
import { ComparePanels } from "./ComparePanels";
import { ComparisonTable } from "./ComparisonTable";
import type { CompareResponse, TokenizerInfo } from "./types";
import { WordMatrix } from "./WordMatrix";

interface Comparison {
  text: string; // the text these results were made from (the text box may have changed since)
  data: CompareResponse;
}

interface Props {
  debouncedText: string;
  tokenizers: TokenizerInfo[]; // every tokenizer, including estimates
}

export function CompareView({ debouncedText, tokenizers }: Props) {
  // We store what the user switched OFF, so a tokenizer that appears later is on by default.
  const [off, setOff] = useState<string[]>([]);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showWhitespace, setShowWhitespace] = useState(true);

  const selected = useMemo(() => tokenizers.map((t) => t.name).filter((n) => !off.includes(n)), [tokenizers, off]);

  useEffect(() => {
    if (selected.length === 0 || !debouncedText) {
      setComparison(null);
      setError(null);
      setLoading(false);
      return;
    }
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    compare(debouncedText, selected, ctrl.signal)
      .then((data) => setComparison({ text: debouncedText, data }))
      .catch((e) => {
        if (e.name === "AbortError") return;
        setComparison(null);
        setError(e instanceof ApiError ? e.message : `Cannot reach the server: ${e.message}`);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [debouncedText, selected]);

  const toggle = (name: string) =>
    setOff((cur) => (cur.includes(name) ? cur.filter((n) => n !== name) : [...cur, name]));

  const results = comparison?.data.results ?? [];
  const withTokens = results.filter((r) => r.has_tokens && !r.error);

  return (
    <>
      <fieldset className="picker">
        <legend>Tokenizers to compare</legend>
        {tokenizers.map((t) => (
          <label key={t.name} className="check">
            <input type="checkbox" checked={!off.includes(t.name)} onChange={() => toggle(t.name)} />
            {t.name}
            {!t.exact && <span className="badge">estimate</span>}
          </label>
        ))}
      </fieldset>

      {selected.length === 0 && <p className="muted">Select at least one tokenizer.</p>}

      <section aria-live="polite" className="stats">
        {loading && <span className="muted">Comparing {selected.length} tokenizers… the first run can be slow while models load.</span>}
        {!loading && comparison && (
          <span className="muted">
            {comparison.data.chars.toLocaleString()} characters · {comparison.data.bytes.toLocaleString()} bytes
          </span>
        )}
      </section>

      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      {comparison && results.length > 0 && (
        <>
          <ComparisonTable results={results} />
          <WordMatrix text={comparison.text} results={results} />

          <section aria-labelledby="side-title" className="words">
            <h2 id="side-title">Side by side</h2>
            {withTokens.length > 0 && (
              <label className="check">
                <input type="checkbox" checked={showWhitespace} onChange={(e) => setShowWhitespace(e.target.checked)} />
                Show spaces and new lines
              </label>
            )}
            <ComparePanels text={comparison.text} results={results} showWhitespace={showWhitespace} />
          </section>
        </>
      )}
    </>
  );
}
