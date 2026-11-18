import { useEffect, useRef, useState } from "react";
import { useField } from "../hooks/useField.js";
import { normalizeUrl, validateLink } from "../lib/draft.js";
import { validateNote } from "../lib/validators.js";
import { Button } from "./ui/Button.jsx";
import { FieldMessage } from "./ui/FieldMessage.jsx";
import { LinkIcon, NoteIcon } from "./ui/icons.jsx";

const MODES = {
  note: {
    label: "Note",
    Icon: NoteIcon,
    action: "Save note",
    hint: "Plain text. Ctrl + Enter saves.",
    saved: "Note saved. Follow its progress in the library.",
  },
  url: {
    label: "Link",
    Icon: LinkIcon,
    action: "Save link",
    hint: "The page is loaded on the server and its text is saved.",
    saved: "Link saved. Follow its progress in the library.",
  },
};

const boxClass = (error) =>
  `rounded-2xl border bg-night-raised transition-[border-color,box-shadow] motion-reduce:transition-none focus-within:ring-4 ${
    error ? "border-coral focus-within:ring-coral/20" : "border-night-rule focus-within:border-accent-light focus-within:ring-accent/30"
  }`;

const inputClass =
  "block w-full bg-transparent text-base text-night-ink placeholder:text-night-muted/80 focus:outline-none focus-visible:outline-none";

function ModeToggle({ mode, onChange }) {
  return (
    <fieldset className="mb-3">
      <legend className="sr-only">What do you want to add?</legend>
      <div className="grid grid-cols-2 gap-1 rounded-xl bg-night-raised p-1">
        {Object.entries(MODES).map(([value, { label, Icon }]) => (
          <label
            key={value}
            className={`flex cursor-pointer items-center justify-center gap-2 rounded-lg py-2 text-sm font-semibold transition-colors motion-reduce:transition-none has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-accent-light ${
              mode === value ? "bg-accent text-white" : "text-night-muted hover:text-night-ink"
            }`}
          >
            <input
              type="radio"
              name="ingest-mode"
              value={value}
              checked={mode === value}
              onChange={() => onChange(value)}
              className="sr-only"
            />
            <Icon width={16} height={16} />
            {label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** Add a note or a link. Each mode keeps its own draft, so switching never loses text. */
export function Composer({ onSave }) {
  const [mode, setMode] = useState("note");
  const note = useField("", validateNote);
  const link = useField("", validateLink);
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState(null); // { tone: "success" | "error", text }
  const noteRef = useRef(null);
  const linkRef = useRef(null);

  const field = mode === "note" ? note : link;
  const config = MODES[mode];

  useEffect(() => {
    if (notice?.tone !== "success") return undefined;
    const timer = setTimeout(() => setNotice(null), 4000);
    return () => clearTimeout(timer);
  }, [notice]);

  function switchMode(next) {
    setMode(next);
    setNotice(null);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return;
    setNotice(null);
    if (field.validateNow()) {
      (mode === "note" ? noteRef : linkRef).current?.focus();
      return;
    }

    const payload =
      mode === "note" ? { type: "note", content: note.value.trim() } : { type: "url", url: normalizeUrl(link.value) };
    setSubmitting(true);
    try {
      await onSave(payload);
      field.reset();
      setNotice({ tone: "success", text: config.saved });
    } catch (err) {
      if (err.status === 422) field.setError(err.details?.[0]?.message ?? err.message);
      else setNotice({ tone: "error", text: `Couldn't save: ${err.message}` });
    } finally {
      setSubmitting(false);
    }
  }

  function submitOnModEnter(event) {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) event.currentTarget.form.requestSubmit();
  }

  const message = field.error ? { tone: "error", text: field.error } : notice ?? { tone: "hint", text: config.hint };

  return (
    <form onSubmit={handleSubmit} noValidate>
      <p className="mb-2.5 text-sm font-semibold text-night-ink">Add to your inbox</p>
      <ModeToggle mode={mode} onChange={switchMode} />

      <div className={boxClass(field.error)}>
        {mode === "note" ? (
          <>
            <label htmlFor="note-input" className="sr-only">
              Note
            </label>
            <textarea
              id="note-input"
              ref={noteRef}
              rows={4}
              placeholder="Write or paste your note"
              aria-describedby="composer-message"
              onKeyDown={submitOnModEnter}
              className={`${inputClass} max-h-64 min-h-[7rem] resize-none px-4 pt-3.5 leading-relaxed [field-sizing:content]`}
              {...note.inputProps}
            />
          </>
        ) : (
          <>
            <label htmlFor="link-input" className="sr-only">
              Page link
            </label>
            <div className="flex items-center gap-2.5 px-4 pt-3.5 pb-1">
              <LinkIcon width={17} height={17} className="shrink-0 text-teal" />
              <input
                id="link-input"
                ref={linkRef}
                type="url"
                inputMode="url"
                autoComplete="url"
                placeholder="https://example.com/article"
                aria-describedby="composer-message"
                className={`${inputClass} h-9`}
                {...link.inputProps}
              />
            </div>
          </>
        )}
        <div className="flex justify-end px-3 pt-1 pb-3">
          <Button type="submit" size="sm" busy={submitting} busyLabel="Saving…">
            {config.action}
          </Button>
        </div>
      </div>

      <FieldMessage id="composer-message" theme="dark" tone={message.tone}>
        {message.text}
      </FieldMessage>
    </form>
  );
}
