import { describe, expect, it } from "vitest";
import { visible, visibleInline } from "./visible";

describe("visible", () => {
  it("shows spaces, newlines and tabs", () => expect(visible(" a\n\tb")).toBe("·a↵→b"));
});

describe("visibleInline", () => {
  it("marks a newline AND keeps the line break", () => expect(visibleInline("a\nb")).toBe("a↵\nb"));
  it("marks spaces like visible()", () => expect(visibleInline(" a ")).toBe("·a·"));
});
