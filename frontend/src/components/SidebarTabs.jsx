import { useRef } from "react";

/** Accessible tabs (arrow keys move between them). Panels use id `${id}-panel`. */
export function SidebarTabs({ tabs, active, onChange }) {
  const refs = useRef({});

  function handleKeyDown(event, index) {
    const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = tabs[(index + step + tabs.length) % tabs.length];
    onChange(next.id);
    refs.current[next.id]?.focus();
  }

  return (
    <div role="tablist" aria-label="Sidebar" className="mx-6 mb-3 flex gap-6 border-b border-night-rule">
      {tabs.map((tab, index) => {
        const selected = tab.id === active;
        return (
          <button
            key={tab.id}
            ref={(el) => (refs.current[tab.id] = el)}
            id={`${tab.id}-tab`}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={`${tab.id}-panel`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.id)}
            onKeyDown={(event) => handleKeyDown(event, index)}
            className={`-mb-px flex items-center gap-2 border-b-2 pb-2.5 font-display text-base font-bold transition-colors motion-reduce:transition-none focus-visible:outline-accent-light ${
              selected ? "border-accent-light text-night-ink" : "border-transparent text-night-muted hover:text-night-ink"
            }`}
          >
            {tab.label}
            {tab.count != null && (
              <span
                className={`rounded-full px-2 py-0.5 font-sans text-xs font-semibold tabular-nums ${
                  selected ? "bg-accent/25 text-accent-light" : "bg-night-raised text-night-muted"
                }`}
              >
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
