import { useEffect, useState } from "react";
import { copyText, formatIds, type CopyOutcome } from "./copyIds";
import type { Token } from "./types";

export function CopyIdsButton({ tokens }: { tokens: Token[] }) {
  const [status, setStatus] = useState<CopyOutcome | "idle">("idle");

  // Go back to "Copy token IDs" after 2 seconds. The cleanup stops the timer if the
  // component disappears or the button is clicked again first.
  useEffect(() => {
    if (status === "idle") return;
    const id = setTimeout(() => setStatus("idle"), 2000);
    return () => clearTimeout(id);
  }, [status]);

  const label =
    status === "copied" ? "Copied!" : status === "failed" ? "Copy failed" : "Copy token IDs";

  return (
    <>
      <button
        type="button"
        className="btn"
        onClick={async () => setStatus(await copyText(formatIds(tokens)))}
      >
        {label}
      </button>
      {/* Screen readers do not notice a button's text changing, so announce it. */}
      <span role="status" className="sr-only">
        {status === "copied"
          ? `Copied ${tokens.length} token IDs`
          : status === "failed"
            ? "Could not copy to the clipboard"
            : ""}
      </span>
    </>
  );
}
