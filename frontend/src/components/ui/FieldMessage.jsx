const TONES = {
  light: { hint: "text-muted", error: "text-bad", success: "text-mint" },
  dark: { hint: "text-night-muted", error: "text-coral", success: "text-mint" },
};

/**
 * One message slot under a field. Errors and confirmations replace the hint in the
 * same slot, so the layout never jumps when validation runs.
 */
export function FieldMessage({ id, tone = "hint", theme = "light", children }) {
  return (
    <p
      id={id}
      role={tone === "error" ? "alert" : tone === "success" ? "status" : undefined}
      className={`mt-2 min-h-5 text-sm leading-5 ${TONES[theme][tone]}`}
    >
      {children}
    </p>
  );
}
