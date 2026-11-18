import { ItemRow } from "./ItemRow.jsx";
import { ErrorNotice } from "./ui/ErrorNotice.jsx";

function LoadingRows() {
  return Array.from({ length: 4 }, (_, i) => (
    <li key={i} aria-hidden="true" className="flex items-center gap-3.5 px-3 py-3">
      <span className="size-10 animate-pulse rounded-xl bg-night-raised motion-reduce:animate-none" />
      <span className="flex-1 space-y-2">
        <span className="block h-4 w-3/5 animate-pulse rounded bg-night-raised motion-reduce:animate-none" />
        <span className="block h-3 w-2/5 animate-pulse rounded bg-night-raised motion-reduce:animate-none" />
      </span>
    </li>
  ));
}

export function ItemList({ items, status, error, onRetry, highlightedItemId }) {
  const count = items.length;

  // The heading and count live in the sidebar tab ("Library 6").
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {status === "ready" && error && (
        <p role="status" className="px-6 pb-2 text-[0.8125rem] text-coral">
          Couldn't refresh the list. Showing the last saved state.
        </p>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-6">
        {status === "error" ? (
          <ErrorNotice
            className="mx-3"
            title="Couldn't load your library"
            message={error?.message}
            actionLabel="Try again"
            onAction={onRetry}
          />
        ) : status === "ready" && count === 0 ? (
          <div className="mx-3 rounded-2xl border border-dashed border-night-rule px-5 py-7 text-center">
            <p className="text-base font-semibold text-night-ink">Nothing saved yet</p>
            <p className="mx-auto mt-1 max-w-[30ch] text-sm leading-relaxed text-night-muted">
              Notes and links you add above show up here, ready to ask about.
            </p>
          </div>
        ) : (
          <ul className="space-y-1" aria-busy={status === "loading"}>
            {status === "loading" ? (
              <LoadingRows />
            ) : (
              items.map((item) => <ItemRow key={item.id} item={item} highlighted={item.id === highlightedItemId} />)
            )}
          </ul>
        )}
      </div>
    </div>
  );
}
