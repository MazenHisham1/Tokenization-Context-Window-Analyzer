import { afterEach, describe, expect, it, vi } from "vitest";
import { formatDetail, tokenize } from "./api";
import { visible } from "./visible";

afterEach(() => vi.unstubAllGlobals());

const reply = (status: number, body: unknown) =>
  vi.fn().mockResolvedValue({
    ok: status < 400,
    status,
    statusText: "x",
    json: async () => body,
  });

describe("formatDetail", () => {
  it("passes a string through", () => expect(formatDetail("boom", "f")).toBe("boom"));
  it("reads FastAPI validation errors", () =>
    expect(formatDetail([{ loc: ["body", "text"], msg: "too long" }], "f")).toBe("text: too long"));
  it("uses the fallback for anything else", () => expect(formatDetail(null, "fallback")).toBe("fallback"));
});

describe("tokenize", () => {
  it("returns the parsed body on success", async () => {
    vi.stubGlobal("fetch", reply(200, { count: 3, tokens: [] }));
    expect((await tokenize("hi", "my-bpe")).count).toBe(3);
  });

  it("throws ApiError with the server's message on 503", async () => {
    vi.stubGlobal("fetch", reply(503, { detail: "cannot load llama-3" }));
    await expect(tokenize("hi", "llama-3")).rejects.toMatchObject({
      name: "ApiError",
      status: 503,
      message: "cannot load llama-3",
    });
  });

  it("sends the text and tokenizer as JSON", async () => {
    const f = reply(200, {});
    vi.stubGlobal("fetch", f);
    await tokenize("héllo", "t");
    expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({ text: "héllo", tokenizer: "t" });
  });
});

describe("visible", () => {
  it("shows spaces, newlines and tabs", () => expect(visible(" a\n\tb")).toBe("·a↵→b"));
});
