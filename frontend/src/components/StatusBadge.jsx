import { pipelineProgress, stepLabel } from "../lib/pipeline.js";

/** One-line pipeline status for a library row. */
export function StatusBadge({ item }) {
  if (item.status === "ready") {
    return (
      <span className="text-night-muted tabular-nums">
        {item.chunk_count} {item.chunk_count === 1 ? "chunk" : "chunks"}
      </span>
    );
  }

  const { total, done, current, failed } = pipelineProgress(item.steps);

  if (item.status === "failed") {
    return <span className="font-semibold text-coral">{failed ? `Failed at ${stepLabel(failed.name)}` : "Failed"}</span>;
  }

  return (
    <span className="inline-flex items-center gap-1.5 font-semibold text-accent-light">
      <span aria-hidden="true" className="size-1.5 animate-pulse rounded-full bg-accent-light motion-reduce:animate-none" />
      {item.status === "pending" || !current ? "Queued" : `${stepLabel(current.name)} (${done + 1}/${total})`}
    </span>
  );
}
