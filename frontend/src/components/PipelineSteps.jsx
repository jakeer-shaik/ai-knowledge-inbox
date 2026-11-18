import { formatDuration, pipelineProgress, stepLabel } from "../lib/pipeline.js";

const SEGMENT = {
  done: "bg-accent-light",
  running: "bg-accent-light/50 animate-pulse motion-reduce:animate-none",
  failed: "bg-coral",
  pending: "bg-night-rule",
};

/** Compact progress: one segment per pipeline step. */
export function PipelineBar({ steps }) {
  const { total, done } = pipelineProgress(steps);
  return (
    <span
      role="progressbar"
      aria-label="Ingestion progress"
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={done}
      className="flex gap-1"
    >
      {steps.map((step) => (
        <span key={step.name} className={`h-1 flex-1 rounded-full ${SEGMENT[step.status]}`} />
      ))}
    </span>
  );
}

function StepMarker({ status, number }) {
  if (status === "done") {
    return (
      <span className="grid size-6 place-items-center rounded-full bg-accent text-white">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden="true">
          <path d="m5 12.5 4.5 4.5L19 7.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="grid size-6 place-items-center rounded-full bg-coral text-night">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" aria-hidden="true">
          <path d="M7 7l10 10M17 7 7 17" strokeLinecap="round" />
        </svg>
      </span>
    );
  }
  if (status === "running") {
    return (
      <span className="grid size-6 place-items-center">
        <span className="size-5 animate-spin rounded-full border-2 border-accent-light border-t-transparent motion-reduce:animate-none" />
      </span>
    );
  }
  return (
    <span className="grid size-6 place-items-center rounded-full border-2 border-night-rule text-[0.6875rem] font-bold text-night-muted">
      {number}
    </span>
  );
}

const STATUS_TEXT = { done: null, running: "In progress…", pending: "Waiting", failed: null };

/** Full pipeline view: every step with its status, what happened, and how long it took. */
export function PipelineSteps({ steps }) {
  const stopped = steps.some((step) => step.status === "failed");
  const placeholder = (status) => (stopped && status === "pending" ? "Skipped" : STATUS_TEXT[status]);

  return (
    <ol aria-label="Ingestion pipeline" className="space-y-0">
      {steps.map((step, i) => (
        <li key={step.name} className="relative flex gap-3 pb-3.5 last:pb-0">
          {i < steps.length - 1 && (
            <span
              aria-hidden="true"
              className={`absolute top-7 bottom-0.5 left-3 w-0.5 -translate-x-1/2 rounded-full ${
                step.status === "done" ? "bg-accent/70" : "bg-night-rule"
              }`}
            />
          )}
          <StepMarker status={step.status} number={i + 1} />
          <div className="min-w-0 flex-1 pt-0.5">
            <div className="flex items-baseline justify-between gap-3">
              <span
                className={`text-sm font-semibold ${
                  step.status === "pending" ? "text-night-muted" : step.status === "failed" ? "text-coral" : "text-night-ink"
                }`}
              >
                {stepLabel(step.name)}
              </span>
              {step.status === "done" && step.name !== "received" && (
                <span className="shrink-0 text-xs text-night-muted tabular-nums">{formatDuration(step.duration_ms)}</span>
              )}
            </div>
            {(step.detail || placeholder(step.status)) && (
              <p
                className={`mt-0.5 text-[0.8125rem] leading-snug ${
                  step.status === "failed" ? "text-coral/90" : "text-night-muted"
                }`}
              >
                {step.detail ?? placeholder(step.status)}
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
