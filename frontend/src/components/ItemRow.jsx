import { useId, useState } from "react";
import { absoluteTime, itemTitle, relativeTime, sourceLabel } from "../lib/format.js";
import { PipelineBar, PipelineSteps } from "./PipelineSteps.jsx";
import { StatusBadge } from "./StatusBadge.jsx";
import { AlertIcon, ChevronIcon, LinkIcon, NoteIcon } from "./ui/icons.jsx";

const ICON_STYLES = {
  failed: { Icon: AlertIcon, className: "bg-coral/15 text-coral" },
  url: { Icon: LinkIcon, className: "bg-teal/15 text-teal" },
  note: { Icon: NoteIcon, className: "bg-mint/15 text-mint" },
};

const isInProgress = (item) => item.status === "pending" || item.status === "processing";

function ItemIcon({ item }) {
  const { Icon, className } = ICON_STYLES[item.status === "failed" ? "failed" : item.source_type];
  return (
    <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${className}`}>
      <Icon width={18} height={18} />
    </span>
  );
}

/**
 * One saved item. Items still in the pipeline open by default so the steps can be
 * watched live; any row can be expanded to see its steps and captured text.
 */
export function ItemRow({ item, highlighted }) {
  const [open, setOpen] = useState(() => isInProgress(item));
  const detailsId = useId();
  const hasSteps = item.steps?.length > 0;

  return (
    <li
      className={`rounded-2xl transition-colors motion-reduce:transition-none ${
        highlighted ? "bg-accent/20 ring-1 ring-accent-light/60" : open ? "bg-night-raised" : ""
      }`}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={detailsId}
        className="group flex w-full items-center gap-3.5 rounded-2xl px-3 py-3 text-left hover:bg-night-raised focus-visible:outline-accent-light"
      >
        <ItemIcon item={item} />
        <span className="min-w-0 flex-1">
          <span className="flex items-baseline justify-between gap-3">
            <span className="truncate text-base font-semibold text-night-ink">{itemTitle(item)}</span>
            <span className="shrink-0 text-[0.8125rem] text-night-muted">{relativeTime(item.created_at)}</span>
          </span>
          <span className="mt-0.5 flex items-center justify-between gap-3 text-[0.8125rem]">
            <span className="truncate text-night-muted">{sourceLabel(item)}</span>
            <StatusBadge item={item} />
          </span>
          {isInProgress(item) && hasSteps && (
            <span className="mt-2 block">
              <PipelineBar steps={item.steps} />
            </span>
          )}
        </span>
        <ChevronIcon
          width={16}
          height={16}
          className={`shrink-0 text-night-muted/60 transition-transform group-hover:text-night-muted motion-reduce:transition-none ${
            open ? "rotate-90" : ""
          }`}
        />
      </button>

      {open && (
        <div id={detailsId} className="space-y-4 px-3 pb-4 pl-[4.25rem] text-sm">
          {hasSteps && <PipelineSteps steps={item.steps} />}
          {item.status === "failed" && item.error && !hasSteps && <p className="leading-relaxed text-coral">{item.error}</p>}
          {item.content_preview && (
            <p className="line-clamp-4 border-l-2 border-night-rule pl-3 text-[0.9375rem] leading-relaxed text-night-ink/80">
              {item.content_preview}
            </p>
          )}
          <p className="leading-relaxed text-night-muted">
            Saved {absoluteTime(item.created_at)}
            {item.url && (
              <>
                {" from "}
                <a href={item.url} target="_blank" rel="noreferrer" className="break-all text-accent-light underline underline-offset-2">
                  {item.url}
                </a>
              </>
            )}
          </p>
        </div>
      )}
    </li>
  );
}
