import type { Token } from "./types";

/** "[84, 260, 280]": a format you can paste straight into Python or JavaScript. */
export function formatIds(tokens: Pick<Token, "id">[]): string {
  return `[${tokens.map((t) => t.id).join(", ")}]`;
}

export type CopyOutcome = "copied" | "failed";

/** Copy text to the clipboard. Never throws: returns "failed" instead.
 *  `clipboard` is a parameter so a test can pass a fake one.
 *  Browsers only provide navigator.clipboard on https:// or localhost, so it can be missing. */
export async function copyText(
  text: string,
  clipboard: Pick<Clipboard, "writeText"> | undefined = typeof navigator !== "undefined"
    ? navigator.clipboard
    : undefined,
): Promise<CopyOutcome> {
  if (!clipboard) return "failed";
  try {
    await clipboard.writeText(text);
    return "copied";
  } catch {
    return "failed"; // permission denied, or the page is not focused
  }
}
