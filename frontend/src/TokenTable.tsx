import type { Token } from "./types";
import { visible } from "./visible";

// Rendering 50,000 rows would freeze the page. Phase 4 replaces this table with a
// virtualised, colour-coded view. Until then we show the first rows and say so.
export const MAX_ROWS = 1000;

export function TokenTable({ tokens }: { tokens: Token[] }) {
  const shown = tokens.slice(0, MAX_ROWS);
  return (
    <div className="table-wrap">
      <table>
        <caption className="sr-only">Tokens produced by the selected tokenizer</caption>
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">ID</th>
            <th scope="col">Text</th>
            <th scope="col">Piece</th>
            <th scope="col">Bytes</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((t, i) => (
            <tr key={i}>
              <td>{i + 1}</td>
              <td className="mono">{t.id}</td>
              <td className="mono">{visible(t.text)}</td>
              <td className="mono muted">{visible(t.piece)}</td>
              <td className="mono muted">
                {t.start}–{t.end}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {tokens.length > MAX_ROWS && (
        <p className="notice">
          Showing the first {MAX_ROWS.toLocaleString()} of {tokens.length.toLocaleString()} tokens.
        </p>
      )}
    </div>
  );
}
