import { type ReactNode, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { describeSegment, nextChip } from "./chipNav";
import { buildSegments, wordSplits, type Segment } from "./segments";
import type { Token } from "./types";
import { visible, visibleInline } from "./visible";
import { WordSplits } from "./WordSplits";

// A page with 50,000 coloured elements would be slow, so we colour the first tokens only.
export const MAX_CHIPS = 2000;
const PALETTE_SIZE = 8; // keep in sync with .c0 ... .c7 in styles.css

interface Props {
  text: string; // the text the tokens were made from (not the text box: it may have changed)
  tokens: Token[];
  showWhitespace: boolean;
  label?: string; // accessible name of the region; give each panel its own
  compact?: boolean; // side-by-side panels: no legend and no word list (the page shows one of each)
  maxChips?: number; // how many tokens to colour
  totalTokens?: number; // the real token count, if the server sent only the first tokens
}

export function TokenChips({ text, tokens, showWhitespace, label = "Text coloured by token", compact = false, maxChips = MAX_CHIPS, totalTokens }: Props) {
  const total = Math.max(totalTokens ?? tokens.length, tokens.length);
  const truncated = total > maxChips || total > tokens.length;

  const segments = useMemo(() => {
    const segs = buildSegments(text, tokens.slice(0, maxChips));
    // After the cut, the rest of the text has no colours. Do not render it.
    if (truncated && segs.length && segs[segs.length - 1].kind === "gap") segs.pop();
    return segs;
  }, [text, tokens, truncated, maxChips]);

  const words = useMemo(() => (compact ? null : wordSplits(text, segments)), [text, segments, compact]);

  // One tooltip for the whole component: `active` is the chip under the mouse or finger.
  // `via` says how it was opened: pointer tooltips close on scroll, keyboard ones follow their chip.
  const [active, setActive] = useState<{ index: number; rect: DOMRect; via: "pointer" | "keyboard" } | null>(null);
  const chipsRef = useRef<HTMLDivElement>(null);
  const chipRect = useCallback(
    (index: number) => chipsRef.current?.querySelector<HTMLElement>(`[data-seg="${index}"]`)?.getBoundingClientRect(),
    [],
  );

  useEffect(() => {
    const onScroll = () =>
      setActive((cur) => {
        if (!cur || cur.via === "pointer") return null; // a fixed tooltip would float away from its chip
        const rect = chipRect(cur.index);
        return rect ? { ...cur, rect } : null;
      });
    window.addEventListener("scroll", onScroll, true);
    return () => window.removeEventListener("scroll", onScroll, true);
  }, [chipRect]);

  // Event delegation: 3 handlers on the container instead of 2,000 on the chips.
  const point = (e: React.MouseEvent) => {
    const el = (e.target as HTMLElement).closest<HTMLElement>("[data-seg]");
    if (!el) return setActive(null);
    const index = Number(el.dataset.seg);
    setActive((cur) => (cur?.index === index ? cur : { index, rect: el.getBoundingClientRect(), via: "pointer" }));
  };

  // Keyboard: the text is one tab stop; the arrow keys move between tokens.
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") return setActive(null);
    const next = nextChip(segments, active?.index ?? null, e.key);
    if (next === undefined) return;
    e.preventDefault(); // do not scroll the page
    const el = chipsRef.current?.querySelector<HTMLElement>(`[data-seg="${next}"]`);
    if (!el) return;
    el.scrollIntoView({ block: "nearest", inline: "nearest" });
    setActive({ index: next, rect: el.getBoundingClientRect(), via: "keyboard" });
  };

  const fmt = showWhitespace ? visibleInline : (s: string) => s;
  const seg = active ? segments[active.index] : null;

  return (
    <section aria-label={label}>
      {/* biome-ignore lint/a11y/useKeyWithMouseEvents: the pointer events are delegated to the chips; keyboard users use onKeyDown below */}
      <div
        ref={chipsRef}
        className="chips"
        dir="auto"
        role="group"
        // biome-ignore lint/a11y/noNoninteractiveTabindex: one tab stop; arrow keys move between tokens and each one is announced
        tabIndex={0}
        aria-label="Tokens. Use the arrow keys to move between them."
        onMouseOver={point}
        onClick={point}
        onMouseLeave={() => setActive((cur) => (cur?.via === "pointer" ? null : cur))}
        onKeyDown={onKeyDown}
        onBlur={() => setActive((cur) => (cur?.via === "keyboard" ? null : cur))}
      >
        {segments.map((s, i) =>
          s.kind === "gap" ? (
            <span key={i} className="gap">{fmt(s.text)}</span>
          ) : s.charEnd === s.charStart ? (
            <span key={i} data-seg={i} className={`chip empty c${s.color % PALETTE_SIZE}${active?.index === i ? " active" : ""}`}>
              ⟨{visible(tokens[s.tokenIdx[0]].piece)}⟩
            </span>
          ) : (
            <span key={i} data-seg={i} className={`chip c${s.color % PALETTE_SIZE}${s.kind === "shared" ? " shared" : ""}${active?.index === i ? " active" : ""}`}>
              {fmt(s.text)}
              {s.kind === "shared" && <sup className="count">×{s.tokenIdx.length}</sup>}
            </span>
          ),
        )}
      </div>

      {/* Screen readers do not see the tooltip, so the focused token is announced here. */}
      <p className="sr-only" role="status">{active?.via === "keyboard" && seg ? describeSegment(seg, tokens) : ""}</p>

      {truncated && (
        <p className="notice">
          Coloured view shows the first {Math.min(maxChips, tokens.length).toLocaleString()} of {total.toLocaleString()} tokens.
        </p>
      )}

      {!compact && (
      <p className="legend muted">
        Each colour block is one token. A <span className="chip shared c0 mini">dashed</span> block is a character
        the tokenizer split into several byte tokens. {showWhitespace && "· is a space, ↵ a new line, → a tab."} Hover
        or tap a block for details, or focus the text and use the arrow keys.
      </p>
      )}

      {words && <WordSplits {...words} />}

      {active && seg && (
        <Tooltip anchor={active.rect}>
          <TooltipBody seg={seg} tokens={tokens} />
        </Tooltip>
      )}
    </section>
  );
}

function TooltipBody({ seg, tokens }: { seg: Segment; tokens: Token[] }) {
  const first = tokens[seg.tokenIdx[0]];
  if (seg.kind === "shared") {
    const shown = seg.tokenIdx.slice(0, 6);
    return (
      <>
        <strong>{seg.tokenIdx.length} tokens share “{visible(seg.text)}”</strong>
        <p>The tokenizer has no single token for this text, so it falls back to raw bytes.</p>
        <table>
          <tbody>
            {shown.map((n) => (
              <tr key={n}>
                <td>#{n + 1}</td>
                <td>ID {tokens[n].id}</td>
                <td className="mono">{visible(tokens[n].piece)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {seg.tokenIdx.length > shown.length && <p>…and {seg.tokenIdx.length - shown.length} more</p>}
        <p>Bytes {seg.byteStart}–{seg.byteEnd}</p>
      </>
    );
  }
  return (
    <>
      <strong>Token #{seg.tokenIdx[0] + 1}</strong>
      <dl>
        <dt>ID</dt><dd>{first.id}</dd>
        <dt>Piece</dt><dd className="mono">{visible(first.piece) || "(empty)"}</dd>
        <dt>Text</dt><dd className="mono">{visible(seg.text) || "(none)"}</dd>
        <dt>Bytes</dt><dd>{first.start}–{first.end} ({first.end - first.start})</dd>
        <dt>Characters</dt><dd>{seg.charStart}–{seg.charEnd}</dd>
      </dl>
    </>
  );
}

/** Positioned with `position: fixed` next to the chip, then moved so it stays on screen. */
function Tooltip({ anchor, children }: { anchor: DOMRect; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const margin = 8;
    const left = Math.min(anchor.left, window.innerWidth - el.offsetWidth - margin);
    let top = anchor.top - el.offsetHeight - 6; // above the chip...
    if (top < margin) top = anchor.bottom + 6; // ...or below it when there is no room
    el.style.left = `${Math.max(left, margin)}px`;
    el.style.top = `${top}px`;
    el.style.visibility = "visible";
  });
  return (
    <div ref={ref} className="tooltip" role="tooltip" style={{ visibility: "hidden", left: 0, top: 0 }}>
      {children}
    </div>
  );
}
