const VARIANTS = {
  primary:
    "bg-accent text-white shadow-[0_6px_16px_-6px_rgb(5_150_105/0.55)] enabled:hover:bg-accent-strong disabled:cursor-not-allowed disabled:bg-accent/35 disabled:shadow-none",
  secondary: "border border-rule bg-surface text-ink enabled:hover:bg-paper disabled:cursor-not-allowed disabled:opacity-50",
};

const SIZES = {
  sm: "h-9 rounded-lg px-3.5 text-sm",
  md: "h-11 rounded-xl px-5 text-[0.9375rem]",
};

/** Never rendered disabled: while busy it ignores clicks but stays focusable and labelled. */
export function Button({ variant = "primary", size = "md", busy = false, busyLabel, className = "", children, onClick, ...props }) {
  return (
    <button
      {...props}
      aria-busy={busy || undefined}
      onClick={(event) => (busy ? event.preventDefault() : onClick?.(event))}
      className={`inline-flex shrink-0 items-center justify-center gap-1.5 font-semibold transition-colors motion-reduce:transition-none ${
        busy ? "cursor-progress opacity-80" : ""
      } ${SIZES[size]} ${VARIANTS[variant]} ${className}`}
    >
      {busy && busyLabel ? busyLabel : children}
    </button>
  );
}
