import { describe, expect, it, vi } from "vitest";
import { copyText, formatIds } from "./copyIds";

const tok = (id: number) => ({ id });

describe("formatIds", () => {
  it("formats ids as a list you can paste into code", () =>
    expect(formatIds([tok(84), tok(260), tok(280)])).toBe("[84, 260, 280]"));
  it("returns [] for no tokens", () => expect(formatIds([])).toBe("[]"));
  it("includes every token, not only the 1,000 shown in the table", () => {
    const ids = formatIds(Array.from({ length: 1500 }, (_, i) => tok(i)));
    expect(ids.split(",").length).toBe(1500);
  });
});

describe("copyText", () => {
  it("writes the exact text and reports success", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    expect(await copyText("[1, 2]", { writeText })).toBe("copied");
    expect(writeText).toHaveBeenCalledWith("[1, 2]");
  });
  it("reports failure instead of throwing when the browser refuses", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    expect(await copyText("x", { writeText })).toBe("failed");
  });
  it("reports failure when there is no clipboard (e.g. plain http)", async () => {
    expect(await copyText("x", undefined)).toBe("failed");
  });
});
