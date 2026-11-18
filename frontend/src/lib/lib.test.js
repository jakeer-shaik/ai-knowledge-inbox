import { describe, expect, it } from "vitest";
import { parseBlocks, parseInline } from "./answerFormat.js";
import { splitCitations } from "./citations.js";
import { normalizeUrl, validateLink } from "./draft.js";
import { hostname, itemTitle, relativeTime } from "./format.js";
import { formatDuration, pipelineProgress, stepLabel } from "./pipeline.js";
import { validateNote, validateQuestion } from "./validators.js";

describe("validators", () => {
  it("requires note text and caps its length", () => {
    expect(validateNote("   ")).toBe("Write something to save.");
    expect(validateNote("x".repeat(20_001))).toMatch(/under 20,000/);
    expect(validateNote("hello")).toBeNull();
  });

  it("accepts only full http(s) links", () => {
    expect(validateLink("")).toMatch(/Paste a link/);
    expect(validateLink("notalink")).toBe("Enter the full link, starting with https://");
    expect(validateLink("ftp://example.com")).toMatch(/http:\/\/ or https:\/\//);
    expect(validateLink("https://example.com/a")).toBeNull();
    expect(validateLink("www.example.com")).toBeNull();
  });

  it("normalizes www. shorthand to https", () => {
    expect(normalizeUrl("  www.example.com/x ")).toBe("https://www.example.com/x");
    expect(normalizeUrl("http://a.com")).toBe("http://a.com");
  });

  it("validates questions", () => {
    expect(validateQuestion(" ")).toBe("Type a question to ask.");
    expect(validateQuestion("x".repeat(501))).toMatch(/under 500/);
    expect(validateQuestion("Why?")).toBeNull();
  });
});

describe("splitCitations", () => {
  it("turns [n] into citation segments", () => {
    expect(splitCitations("Use PgBouncer [1][2].", 2)).toEqual([
      { type: "text", text: "Use PgBouncer " },
      { type: "cite", n: 1 },
      { type: "cite", n: 2 },
      { type: "text", text: "." },
    ]);
  });

  it("leaves markers without a matching source as plain text", () => {
    expect(splitCitations("Claim [7] here.", 2)).toEqual([{ type: "text", text: "Claim [7] here." }]);
  });
});

describe("answer formatting", () => {
  it("groups bullet lines into a list and keeps paragraphs", () => {
    const text = "To fix it:\n\n* Use PgBouncer [1].\n* Cap pools [1].\n\nThat's all.";
    expect(parseBlocks(text)).toEqual([
      { type: "paragraph", text: "To fix it:" },
      { type: "list", items: ["Use PgBouncer [1].", "Cap pools [1]."] },
      { type: "paragraph", text: "That's all." },
    ]);
  });

  it("parses code, bold and citations inline", () => {
    expect(parseInline("Keep `max_connections` at **200** [1].", 1)).toEqual([
      { type: "text", text: "Keep " },
      { type: "code", text: "max_connections" },
      { type: "text", text: " at " },
      { type: "bold", text: "200" },
      { type: "text", text: " " },
      { type: "cite", n: 1 },
      { type: "text", text: "." },
    ]);
  });
});

describe("pipeline helpers", () => {
  const steps = [
    { name: "received", status: "done" },
    { name: "fetching", status: "done" },
    { name: "chunking", status: "running" },
    { name: "embedding", status: "pending" },
    { name: "storing", status: "pending" },
  ];

  it("finds the current step and counts progress", () => {
    const progress = pipelineProgress(steps);
    expect(progress).toMatchObject({ total: 5, done: 2, failed: null });
    expect(progress.current.name).toBe("chunking");
  });

  it("reports the failed step", () => {
    const failed = steps.map((s) => (s.name === "chunking" ? { ...s, status: "failed" } : s));
    expect(pipelineProgress(failed).failed.name).toBe("chunking");
  });

  it("labels steps and durations for people", () => {
    expect(stepLabel("embedding")).toBe("Creating vectors");
    expect(stepLabel("fetching")).toBe("Loading page");
    expect(formatDuration(0.4)).toBe("<1 ms");
    expect(formatDuration(588)).toBe("588 ms");
    expect(formatDuration(3020)).toBe("3.0 s");
  });
});

describe("format", () => {
  it("derives titles and hosts", () => {
    expect(hostname("https://www.example.com/a")).toBe("example.com");
    expect(itemTitle({ title: null, url: "https://en.wikipedia.org/x" })).toBe("en.wikipedia.org");
    expect(itemTitle({ title: null, url: null })).toBe("Untitled note");
  });

  it("formats relative time", () => {
    const now = Date.parse("2026-11-18T12:00:00Z");
    expect(relativeTime("2026-11-18T11:59:50Z", now)).toBe("just now");
    expect(relativeTime("2026-11-18T11:55:00Z", now)).toBe("5 minutes ago");
  });
});
