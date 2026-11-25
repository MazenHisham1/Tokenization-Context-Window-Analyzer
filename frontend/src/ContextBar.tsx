import { buildBar } from "./contextStats";
import type { SimulateResponse } from "./types";

/** The context window as one bar. The numbers below it say the same thing in text. */
export function ContextBar({ result }: { result: SimulateResponse }) {
  const { segments, limitPct } = buildBar(result);
  const label = `Context window of ${result.context_window.toLocaleString("en-US")} tokens: ${result.used_tokens.toLocaleString("en-US")} used by messages, ${result.reserve_output.toLocaleString("en-US")} reserved for the answer`;

  return (
    <div className="ctx-bar-wrap">
      <div className="ctx-bar" role="img" aria-label={label}>
        {segments.map((s, i) => (
          <div
            key={i}
            className={`seg ${s.kind}${s.role ? ` ${s.role}` : ""}${s.partial ? " cut" : ""}`}
            style={{ width: `${s.pct}%` }}
            title={
              s.kind === "message" ? `Message ${(s.index ?? 0) + 1} (${s.role}): ${s.tokens} tokens${s.partial ? ", cut" : ""}` :
              s.kind === "free" ? `Free: ${s.tokens} tokens` : `Reserved for the answer: ${s.tokens} tokens`
            }
          >
            {s.kind === "message" && s.pct > 5 ? `#${(s.index ?? 0) + 1}` : ""}
          </div>
        ))}
        {limitPct !== null && <div className="limit" style={{ left: `${limitPct}%` }} title="End of the context window" />}
      </div>
      <p className="ctx-legend muted small">
        <span><i className="sw message system" /> system</span>
        <span><i className="sw message user" /> user</span>
        <span><i className="sw message assistant" /> assistant</span>
        <span><i className="sw free" /> free</span>
        <span><i className="sw reserve" /> reserved for the answer</span>
        {limitPct !== null && <span><i className="sw limit-sw" /> end of the window</span>}
      </p>
    </div>
  );
}
