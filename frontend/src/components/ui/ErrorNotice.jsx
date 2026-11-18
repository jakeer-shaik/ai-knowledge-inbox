import { Button } from "./Button.jsx";

/** Explains what went wrong and offers the way forward. */
export function ErrorNotice({ title, message, actionLabel, onAction, className = "" }) {
  return (
    <div role="alert" className={`rounded-xl border border-bad/25 bg-bad-soft px-4 py-3.5 ${className}`}>
      <p className="text-[0.9375rem] font-semibold text-bad">{title}</p>
      {message && <p className="mt-0.5 text-[0.9375rem] text-ink">{message}</p>}
      {actionLabel && (
        <Button type="button" variant="secondary" size="sm" className="mt-3" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
