import { forwardRef } from "react";
import { useField } from "../hooks/useField.js";
import { validateQuestion } from "../lib/validators.js";
import { Button } from "./ui/Button.jsx";
import { FieldMessage } from "./ui/FieldMessage.jsx";
import { ArrowUpIcon } from "./ui/icons.jsx";

/** The question box. Clears after sending; Enter sends. */
export const ChatInput = forwardRef(function ChatInput({ label, placeholder, hint, busy, onSend, labelHidden = false }, ref) {
  const question = useField("", validateQuestion);
  const hasText = question.value.trim().length > 0;

  function handleSubmit(event) {
    event.preventDefault();
    if (busy || !hasText || question.validateNow()) return;
    onSend(question.value.trim());
    question.reset();
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <label htmlFor="question" className={labelHidden ? "sr-only" : undefined}>
        {label}
      </label>
      <div
        className={`flex items-center gap-2 rounded-2xl border-2 bg-surface p-2 pl-5 shadow-[0_2px_4px_rgb(20_22_28/0.04),0_20px_40px_-20px_rgb(5_150_105/0.4)] transition-[border-color,box-shadow] motion-reduce:transition-none focus-within:ring-4 ${
          question.error ? "border-bad focus-within:ring-bad/15" : "border-rule focus-within:border-accent focus-within:ring-accent/15"
        }`}
      >
        <input
          id="question"
          ref={ref}
          type="text"
          autoComplete="off"
          enterKeyHint="send"
          placeholder={placeholder}
          aria-describedby="question-message"
          className="h-12 min-w-0 flex-1 bg-transparent text-lg text-ink placeholder:text-muted/70 focus:outline-none focus-visible:outline-none"
          {...question.inputProps}
        />
        {/* Disabled until there's a question to send (also blocks Enter on an empty box). */}
        <Button type="submit" className="h-12 px-6 text-base" disabled={!hasText} busy={busy} busyLabel="Asking…">
          <span>Ask</span>
          <ArrowUpIcon width={18} height={18} />
        </Button>
      </div>
      <FieldMessage id="question-message" tone={question.error ? "error" : "hint"}>
        {question.error ?? hint}
      </FieldMessage>
    </form>
  );
});
