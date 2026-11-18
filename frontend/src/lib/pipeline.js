/** User-facing names for the backend's ingestion pipeline steps. */
export const STEP_LABELS = {
  received: "Received",
  fetching: "Loading page",
  chunking: "Chunking",
  embedding: "Creating vectors",
  storing: "Storing in database",
};

export const stepLabel = (name) => STEP_LABELS[name] ?? name;

/** Where an item is in its pipeline: { total, done, current, failed }. */
export function pipelineProgress(steps = []) {
  return {
    total: steps.length,
    done: steps.filter((s) => s.status === "done").length,
    current: steps.find((s) => s.status === "running") ?? steps.find((s) => s.status === "pending") ?? null,
    failed: steps.find((s) => s.status === "failed") ?? null,
  };
}

export function formatDuration(ms) {
  if (ms == null) return "";
  if (ms < 1) return "<1 ms";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}
