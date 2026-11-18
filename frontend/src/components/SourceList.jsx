import { useState } from "react";
import { hostname } from "../lib/format.js";

function MatchMeter({ score }) {
  const percent = Math.max(0, Math.min(100, Math.round(score * 100)));
  return (
    <span className="flex shrink-0 items-center gap-2 text-[0.8125rem] font-medium text-muted tabular-nums" title="How closely this passage matches the question">
      <span aria-hidden="true" className="h-1.5 w-12 overflow-hidden rounded-full bg-rule">
        <span className="block h-full rounded-full bg-mint" style={{ width: `${percent}%` }} />
      </span>
      {percent}% match
    </span>
  );
}

function SourceRow({ source, n, anchorId, active, onActivate }) {
  const [expanded, setExpanded] = useState(false);
  const title = source.title || (source.url ? hostname(source.url) : "Untitled note");
  const origin = source.source_type === "url" ? hostname(source.url) : "Note";

  return (
    <li
      id={anchorId}
      onMouseEnter={() => onActivate(n)}
      onMouseLeave={() => onActivate(null)}
      className="flex scroll-mt-6 gap-4 py-5 first:pt-0 last:pb-0"
    >
      <span
        className={`grid size-8 shrink-0 place-items-center rounded-lg text-sm font-bold tabular-nums transition-colors motion-reduce:transition-none ${
          active ? "bg-accent text-white" : "bg-accent-soft text-accent"
        }`}
      >
        {n}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <div className="min-w-0">
            {source.url ? (
              <a href={source.url} target="_blank" rel="noreferrer" className="text-base font-semibold hover:text-accent hover:underline">
                {title}
              </a>
            ) : (
              <p className="text-base font-semibold">{title}</p>
            )}
            <p className="text-[0.8125rem] text-muted">{origin}</p>
          </div>
          <MatchMeter score={source.score} />
        </div>
        <blockquote className={`mt-2.5 text-base leading-relaxed text-ink/85 ${expanded ? "" : "line-clamp-3"}`}>
          <mark
            className={`box-decoration-clone rounded px-0.5 transition-colors motion-reduce:transition-none ${
              active ? "bg-marker" : "bg-transparent"
            }`}
          >
            {source.snippet}
          </mark>
        </blockquote>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="mt-1.5 text-sm font-semibold text-accent hover:underline"
        >
          {expanded ? "Show less" : "Show full passage"}
        </button>
      </div>
    </li>
  );
}

export function SourceList({ sources, anchorPrefix, activeSource, onActivate }) {
  const headingId = `${anchorPrefix}-heading`;
  return (
    <section aria-labelledby={headingId} className="border-t border-rule bg-paper/50 px-6 py-6 sm:px-9">
      <h3 id={headingId} className="mb-5 font-display text-lg font-bold">
        {sources.length} {sources.length === 1 ? "source" : "sources"}
      </h3>
      <ol className="divide-y divide-rule">
        {sources.map((source, i) => (
          <SourceRow
            key={`${source.item_id}-${source.chunk_index ?? i}`}
            anchorId={`${anchorPrefix}-${i + 1}`}
            source={source}
            n={i + 1}
            active={activeSource === i + 1}
            onActivate={onActivate}
          />
        ))}
      </ol>
    </section>
  );
}
