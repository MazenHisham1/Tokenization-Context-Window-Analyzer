import { useEffect, useMemo, useState } from "react";
import { getLimits, getTokenizers } from "./api";
import { CompareView } from "./CompareView";
import { ContextView } from "./ContextView";
import { SingleView } from "./SingleView";
import type { Limits, TokenizerInfo } from "./types";
import { useDebounce } from "./useDebounce";

const SAMPLE = "Tokenization turns text into tokens. مرحبا 😊\nThe price is 1234567.89";

type Mode = "single" | "compare" | "context";

export default function App() {
  const [tokenizers, setTokenizers] = useState<TokenizerInfo[]>([]);
  const [limits, setLimits] = useState<Limits | null>(null);
  const [text, setText] = useState(SAMPLE);
  const [mode, setMode] = useState<Mode>("single");
  const [loadError, setLoadError] = useState<string | null>(null);

  const debouncedText = useDebounce(text, 300);

  // On start: ask the server which tokenizers exist and what the limits are.
  useEffect(() => {
    const ctrl = new AbortController();
    getTokenizers(ctrl.signal)
      .then(setTokenizers)
      .catch((e) => {
        if (e.name !== "AbortError") setLoadError(`Cannot reach the server: ${e.message}`);
      });
    getLimits(ctrl.signal).then(setLimits).catch(() => {});
    return () => ctrl.abort();
  }, []);

  // text.length counts UTF-16 units, so an emoji would count as 2. The server counts
  // Unicode characters (code points), and [...text] splits the same way, so the numbers match.
  const charCount = useMemo(() => [...text].length, [text]);
  const tooLong = limits !== null && charCount > limits.max_text_chars;
  // Estimates have a count but no tokens, so the single view cannot show them.
  const withTokens = useMemo(() => tokenizers.filter((t) => t.has_tokens), [tokenizers]);

  return (
    <main>
      <h1>Tokenization Analyzer</h1>
      <p className="lead">See how different tokenizers split the same text.</p>

      <div className="seg-control mode" role="group" aria-label="Mode">
        <button type="button" aria-pressed={mode === "single"} onClick={() => setMode("single")}>
          One tokenizer
        </button>
        <button type="button" aria-pressed={mode === "compare"} onClick={() => setMode("compare")}>
          Compare tokenizers
        </button>
        <button type="button" aria-pressed={mode === "context"} onClick={() => setMode("context")}>
          Context window
        </button>
      </div>

      {mode !== "context" && (
        <>
          <label className="block">
            Text
            <textarea rows={6} value={text} onChange={(e) => setText(e.target.value)} aria-describedby="limit" />
          </label>
          <p id="limit" className={tooLong ? "error-text" : "muted"}>
            {charCount.toLocaleString()}
            {limits ? ` / ${limits.max_text_chars.toLocaleString()}` : ""} characters
          </p>

        </>
      )}

      {loadError && (
        <p role="alert" className="error">
          {loadError}
        </p>
      )}

      {mode === "single" && <SingleView debouncedText={debouncedText} tokenizers={withTokens} />}
      {mode === "compare" && <CompareView debouncedText={debouncedText} tokenizers={tokenizers} />}
      {mode === "context" && <ContextView />}
    </main>
  );
}
