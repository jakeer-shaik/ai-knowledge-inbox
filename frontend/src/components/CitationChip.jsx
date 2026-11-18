/** Inline [n] marker. Hover or focus highlights the matching source; click jumps to it. */
export function CitationChip({ n, anchorId, active, onActivate }) {
  return (
    <a
      href={`#${anchorId}`}
      aria-label={`Source ${n}`}
      onMouseEnter={() => onActivate(n)}
      onMouseLeave={() => onActivate(null)}
      onFocus={() => onActivate(n)}
      onBlur={() => onActivate(null)}
      className={`mx-0.5 inline-flex h-6 min-w-6 items-center justify-center rounded-lg px-1.5 align-[0.15em] text-[0.8125rem] leading-none font-bold no-underline tabular-nums transition-colors motion-reduce:transition-none ${
        active ? "bg-accent text-white" : "bg-accent-soft text-accent hover:bg-accent hover:text-white"
      }`}
    >
      {n}
    </a>
  );
}
