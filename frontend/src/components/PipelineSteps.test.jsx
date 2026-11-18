import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PipelineBar, PipelineSteps } from "./PipelineSteps.jsx";
import { StatusBadge } from "./StatusBadge.jsx";

const step = (name, status, extra = {}) => ({ name, status, detail: null, duration_ms: null, ...extra });

const running = [
  step("received", "done", { detail: "Link received (example.com)" }),
  step("fetching", "done", { detail: "Loaded 17,323 characters from example.com", duration_ms: 588 }),
  step("chunking", "done", { detail: "29 chunks of up to 800 characters", duration_ms: 1 }),
  step("embedding", "running"),
  step("storing", "pending"),
];

const failed = [
  step("received", "done"),
  step("fetching", "failed", { detail: "The page returned HTTP 404." }),
  step("chunking", "pending"),
  step("embedding", "pending"),
  step("storing", "pending"),
];

describe("PipelineSteps", () => {
  it("lists every step in order with details and durations", () => {
    render(<PipelineSteps steps={running} />);
    const items = within(screen.getByRole("list", { name: "Ingestion pipeline" })).getAllByRole("listitem");

    expect(items.map((li) => li.querySelector("span.text-sm").textContent)).toEqual([
      "Received",
      "Loading page",
      "Chunking",
      "Creating vectors",
      "Storing in database",
    ]);
    expect(items[1]).toHaveTextContent("Loaded 17,323 characters");
    expect(items[1]).toHaveTextContent("588 ms");
    expect(items[3]).toHaveTextContent("In progress…");
    expect(items[4]).toHaveTextContent("Waiting");
  });

  it("shows the failure reason and marks later steps as skipped", () => {
    render(<PipelineSteps steps={failed} />);
    const items = screen.getAllByRole("listitem");

    expect(items[1]).toHaveTextContent("The page returned HTTP 404.");
    expect(items[2]).toHaveTextContent("Skipped");
    expect(items[4]).toHaveTextContent("Skipped");
  });

  it("reports progress on the bar", () => {
    render(<PipelineBar steps={running} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "3");
    expect(bar).toHaveAttribute("aria-valuemax", "5");
  });
});

describe("StatusBadge", () => {
  it("shows the running step and its position", () => {
    render(<StatusBadge item={{ status: "processing", steps: running }} />);
    expect(screen.getByText("Creating vectors (4/5)")).toBeInTheDocument();
  });

  it("names the step that failed", () => {
    render(<StatusBadge item={{ status: "failed", steps: failed }} />);
    expect(screen.getByText("Failed at Loading page")).toBeInTheDocument();
  });

  it("shows the chunk count when ready", () => {
    render(<StatusBadge item={{ status: "ready", chunk_count: 1, steps: [] }} />);
    expect(screen.getByText("1 chunk")).toBeInTheDocument();
  });
});
