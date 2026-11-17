import { useEffect, useMemo, useState } from "react";
import { ApiError, getLimits, getTokenizers, tokenize } from "./api";
import { CopyIdsButton } from "./CopyIdsButton";
import { TokenTable } from "./TokenTable";
import type { Limits, TokenizeResponse, TokenizerInfo } from "./types";
import { useDebounce } from "./useDebounce";

const SAMPLE = "Tokenization turns text into tokens. مرحبا 😊\nThe price is 1234567.89";

export default function App() {
  const [tokenizers, setTokenizers] = useState<TokenizerInfo[]>([]);
  const [selected, setSelected] = useState("");
  const [limits, setLimits] = useState<Limits | null>(null);
  const [text, setText] = useState(SAMPLE);
  const [result, setResult] = useState<TokenizeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const debouncedText = useDebounce(text, 300);

  // 1) On start: ask the server which tokenizers exist.
  useEffect(() => {
    const ctrl = new AbortController();
    getTokenizers(ctrl.signal)
      .then((list) => {
        setTokenizers(list);
        setSelected((cur) => cur || list[0]?.name || "");
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(`Cannot reach the server: ${e.message}`);
      });
    getLimits(ctrl.signal).then(setLimits).catch(() => {});
    return () => ctrl.abort();
  }, []);

  // 2) Whenever the (debounced) text or the tokenizer changes: tokenize.
  useEffect(() => {
    if (!selected) return;
    if (!debouncedText) {
      setResult(null);
      setError(null);
      setLoading(false);
      return;
    }
    const ctrl = new AbortController(); // lets us cancel this request if inputs change again
    setLoading(true);
    setError(null);
    tokenize(debouncedText, selected, ctrl.signal)
      .then(setResult)
      .catch((e) => {
        if (e.name === "AbortError") return; // we cancelled it ourselves
        setResult(null);
        setError(e instanceof ApiError ? e.message : `Cannot reach the server: ${e.message}`);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [debouncedText, selected]);

  const info = tokenizers.find((t) => t.name === selected);
  // text.length counts UTF-16 units, so an emoji would count as 2. The server counts
  // Unicode characters (code points), and [...text] splits the same way, so the numbers match.
  const charCount = useMemo(() => [...text].length, [text]);
  const tooLong = limits !== null && charCount > limits.max_text_chars;

  return (
    <main>
      <h1>Tokenization Analyzer</h1>
      <p className="lead">See how different tokenizers split the same text.</p>

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

      <label className="block">
        Text
        <textarea
          rows={6}
          value={text}
          onChange={(e) => setText(e.target.value)}
          aria-describedby="limit"
        />
      </label>
      <p id="limit" className={tooLong ? "error-text" : "muted"}>
        {charCount.toLocaleString()}
        {limits ? ` / ${limits.max_text_chars.toLocaleString()}` : ""} characters
      </p>

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

      {result && result.tokens.length > 0 && (
        <>
          <div className="toolbar">
            <CopyIdsButton tokens={result.tokens} />
          </div>
          <TokenTable tokens={result.tokens} />
        </>
      )}
    </main>
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
