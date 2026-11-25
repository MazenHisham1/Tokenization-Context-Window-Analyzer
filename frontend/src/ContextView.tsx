import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, getModels, simulate } from "./api";
import { ContextResult } from "./ContextResult";
import { SAMPLE_MESSAGES } from "./contextSample";
import type { ModelInfo, Role, SimMessage, SimulateRequest, SimulateResponse, Strategy } from "./types";
import { useDebounce } from "./useDebounce";

interface Row extends SimMessage {
  id: number;
}

const STRATEGIES: { value: Strategy; label: string; help: string }[] = [
  { value: "drop_oldest", label: "Drop the oldest messages", help: "Keeps the newest messages whole and removes older ones. System messages always stay." },
  { value: "truncate_start", label: "Keep the newest text (cut the start)", help: "Like dropping, but the first message that does not fit is cut so that its end survives." },
  { value: "truncate_end", label: "Keep the oldest text (cut the end)", help: "Keeps messages from the beginning and cuts the first one that does not fit so that its start survives. Everything after is dropped." },
  { value: "error", label: "Reject (what most APIs do)", help: "Nothing is cut. If the conversation is too long, the API returns an error and you must shorten it yourself." },
];

const toInt = (s: string) => (/^\d+$/.test(s.trim()) ? Number(s) : NaN);

export function ContextView() {
  const nextId = useRef(1);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [modelId, setModelId] = useState("");
  const [rows, setRows] = useState<Row[]>(() => SAMPLE_MESSAGES.map((m) => ({ ...m, id: nextId.current++ })));
  const [windowText, setWindowText] = useState("400");
  const [reserveText, setReserveText] = useState("100");
  const [overheadText, setOverheadText] = useState("4");
  const [strategy, setStrategy] = useState<Strategy>("drop_oldest");
  const [sim, setSim] = useState<{ messages: SimMessage[]; data: SimulateResponse } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    getModels(ctrl.signal)
      .then((list) => {
        setModels(list);
        if (list.length > 0) setModelId((cur) => cur || list[0].id);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setLoadError(`Cannot reach the server: ${e.message}`);
      });
    return () => ctrl.abort();
  }, []);

  const windowSize = toInt(windowText);
  const reserve = toInt(reserveText);
  const overhead = toInt(overheadText);
  const problem =
    Number.isNaN(windowSize) || windowSize < 1 ? "The context window must be a whole number of at least 1." :
    Number.isNaN(reserve) ? "The reserved answer space must be a whole number (0 or more)." :
    Number.isNaN(overhead) || overhead > 100 ? "The per-message overhead must be a whole number from 0 to 100." :
    reserve >= windowSize ? "The space reserved for the answer must be smaller than the context window." :
    rows.every((r) => !r.text) ? "Write at least one message." : null;

  // The request as text, so that useDebounce compares it by value.
  const payload = useMemo(
    () => (problem || !modelId ? null : JSON.stringify({
      model: modelId, strategy, context_window: windowSize, reserve_output: reserve, per_message_overhead: overhead,
      messages: rows.map(({ role, text }) => ({ role, text })),
    } satisfies SimulateRequest)),
    [problem, modelId, strategy, windowSize, reserve, overhead, rows],
  );
  const debounced = useDebounce(payload, 300);

  useEffect(() => {
    if (!debounced) {
      setSim(null);
      setError(null);
      setLoading(false);
      return;
    }
    const req = JSON.parse(debounced) as SimulateRequest;
    const ctrl = new AbortController();
    setLoading(true);
    setError(null);
    simulate(req, ctrl.signal)
      .then((data) => setSim({ messages: req.messages, data }))
      .catch((e) => {
        if (e.name === "AbortError") return;
        setSim(null);
        setError(e instanceof ApiError ? e.message : `Cannot reach the server: ${e.message}`);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });
    return () => ctrl.abort();
  }, [debounced]);

  const model = models.find((m) => m.id === modelId);
  const change = (id: number, patch: Partial<SimMessage>) => setRows((cur) => cur.map((r) => (r.id === id ? { ...r, ...patch } : r)));

  return (
    <>
      <p className="muted">
        Most APIs do not cut anything for you: a request that is too long fails. Dropping or cutting happens in <em>your</em> code,
        so pick what your app would do and see what the model would receive.
      </p>

      {loadError && <p role="alert" className="error">{loadError}</p>}

      <fieldset className="picker ctx-settings">
        <legend>Settings</legend>
        <label>
          Model (chooses the tokenizer)
          <select value={modelId} onChange={(e) => { setModelId(e.target.value); const m = models.find((x) => x.id === e.target.value); if (m) setWindowText(String(m.context_window)); }}>
            {models.map((m) => <option key={m.id} value={m.id}>{m.display_name}</option>)}
          </select>
        </label>
        <label>
          Context window (tokens)
          <input inputMode="numeric" value={windowText} onChange={(e) => setWindowText(e.target.value)} aria-invalid={Number.isNaN(windowSize)} />
        </label>
        <label>
          Reserved for the answer
          <input inputMode="numeric" value={reserveText} onChange={(e) => setReserveText(e.target.value)} aria-invalid={Number.isNaN(reserve)} />
        </label>
        <label>
          Overhead per message
          <input inputMode="numeric" value={overheadText} onChange={(e) => setOverheadText(e.target.value)} aria-invalid={Number.isNaN(overhead)} />
        </label>
        <label className="wide">
          When it does not fit
          <select value={strategy} onChange={(e) => setStrategy(e.target.value as Strategy)}>
            {STRATEGIES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </label>
        <p className="muted small wide">
          {STRATEGIES.find((s) => s.value === strategy)?.help}{" "}
          {model && (
            <>
              The model's real window is {model.context_window.toLocaleString("en-US")} tokens
              {" "}(<a href={model.source_url} target="_blank" rel="noreferrer">source</a>); the small default lets you see overflow.{" "}
              <button type="button" className="btn link" onClick={() => setWindowText(String(model.context_window))}>Use the real window</button>
            </>
          )}
        </p>
        <p className="muted small wide">
          Overhead: chat formats add a few tokens around every message (role markers and separators). The exact number depends on the
          vendor's template, so 4 is a rough default you can change.
        </p>
      </fieldset>

      <section aria-labelledby="ctx-msgs">
        <h2 id="ctx-msgs">Conversation</h2>
        <ol className="editor">
          {rows.map((r, i) => (
            <li key={r.id} className="editor-row">
              <label className="role">
                <span className="sr-only">Role of message {i + 1}</span>
                <select value={r.role} onChange={(e) => change(r.id, { role: e.target.value as Role })}>
                  <option value="system">system</option>
                  <option value="user">user</option>
                  <option value="assistant">assistant</option>
                </select>
              </label>
              <textarea rows={3} aria-label={`Text of message ${i + 1}`} value={r.text} onChange={(e) => change(r.id, { text: e.target.value })} />
              <button type="button" className="btn" disabled={rows.length === 1} onClick={() => setRows((cur) => cur.filter((x) => x.id !== r.id))} aria-label={`Remove message ${i + 1}`}>
                Remove
              </button>
            </li>
          ))}
        </ol>
        <div className="toolbar">
          <button type="button" className="btn" disabled={rows.length >= 50} onClick={() => setRows((cur) => [...cur, { id: nextId.current++, role: cur.at(-1)?.role === "user" ? "assistant" : "user", text: "" }])}>
            Add message
          </button>
          <button type="button" className="btn" onClick={() => { setRows(SAMPLE_MESSAGES.map((m) => ({ ...m, id: nextId.current++ }))); setWindowText("400"); setReserveText("100"); }}>
            Load sample chat
          </button>
        </div>
      </section>

      <div aria-live="polite" className="stats">
        {loading && <span className="muted">Counting tokens…</span>}
      </div>
      {problem && <p className="error-text">{problem}</p>}
      {error && <p role="alert" className="error">{error}</p>}
      {sim && !problem && <ContextResult result={sim.data} messages={sim.messages} />}
    </>
  );
}
