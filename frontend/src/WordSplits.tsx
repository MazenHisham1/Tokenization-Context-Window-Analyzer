import type { WordSplit } from "./segments";
import { visible } from "./visible";

const MAX_LISTED = 12;

interface Props {
  splits: WordSplit[];
  wordCount: number;
  splitCount: number;
}

export function WordSplits({ splits, wordCount, splitCount }: Props) {
  if (wordCount === 0) return null;
  return (
    <div className="words">
      <h2>Words split into several tokens</h2>
      <p className="muted">
        {splitCount === 0
          ? `All ${wordCount.toLocaleString()} words are single tokens.`
          : `${splitCount.toLocaleString()} of ${wordCount.toLocaleString()} words were split.`}
      </p>
      {splits.length > 0 && (
        <ul>
          {splits.slice(0, MAX_LISTED).map((s) => (
            <li key={s.word}>
              <span className="word" dir="auto">{s.word}</span>
              <span aria-hidden="true"> → </span>
              <span className="sr-only"> is split into </span>
              {s.parts.map((p, i) => (
                <span key={i}>
                  {i > 0 && <span className="bar" aria-hidden="true"> | </span>}
                  <span className="part" dir="auto">{visible(p)}</span>
                </span>
              ))}
              <span className="muted"> ({s.parts.length} tokens)</span>
            </li>
          ))}
        </ul>
      )}
      {splits.length > MAX_LISTED && <p className="muted">…and {splits.length - MAX_LISTED} more</p>}
    </div>
  );
}
