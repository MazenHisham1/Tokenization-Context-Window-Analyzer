import { ContextBar } from "./ContextBar";
import { splitKept, summarize } from "./contextStats";
import type { SimMessage, SimulateResponse } from "./types";

const fmt = (x: number) => x.toLocaleString("en-US");

/** `messages` are the texts the result was made from (the editor may already show newer text). */
export function ContextResult({ result, messages }: { result: SimulateResponse; messages: SimMessage[] }) {
  const { tone, text } = summarize(result);
  return (
    <section aria-labelledby="ctx-res">
      <h2 id="ctx-res">What the model would see</h2>
      <p className={`banner ${tone}`} role="status">{text}</p>

      <ContextBar result={result} />

      <dl className="ctx-stats">
        <Stat k="Context window" v={fmt(result.context_window)} />
        <Stat k="Reserved for the answer" v={fmt(result.reserve_output)} />
        <Stat k="Available for the conversation" v={fmt(result.budget)} />
        <Stat k="Whole conversation" v={fmt(result.total_tokens)} />
        <Stat k="Kept" v={fmt(result.used_tokens)} />
      </dl>

      <ol className="ctx-messages">
        {result.messages.map((m) => {
          const src = messages[m.index]?.text ?? "";
          const parts = m.status === "partial" ? splitKept(src, m.kept_chars) : { before: "", kept: src, after: "" };
          return (
            <li key={m.index} className={`ctx-msg ${m.status}`}>
              <header>
                <strong>#{m.index + 1} {m.role}</strong>
                <span className={`badge status-${m.status}`}>
                  {m.status === "kept" && "kept"}
                  {m.status === "partial" && `cut: ${fmt(m.kept_tokens)} of ${fmt(m.tokens)} tokens kept`}
                  {m.status === "dropped" && "dropped"}
                </span>
                <span className="muted small">{fmt(m.tokens)} tokens + {result.per_message_overhead} overhead</span>
              </header>
              <p className="ctx-text" dir="auto">
                {parts.before && <del>{parts.before}</del>}
                {m.status === "dropped" ? <del>{src}</del> : <span>{parts.kept}</span>}
                {parts.after && <del>{parts.after}</del>}
              </p>
            </li>
          );
        })}
      </ol>
      {!result.exact && <p className="note">The tokenizer for this model is an estimate, so these numbers are approximate.</p>}
    </section>
  );
}

function Stat({ k, v }: { k: string; v: string }) {
  return (
    <div>
      <dt className="muted small">{k}</dt>
      <dd>{v}</dd>
    </div>
  );
}
