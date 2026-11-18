import { AnswerBody } from "./AnswerBody.jsx";
import { SourceList } from "./SourceList.jsx";

const FRAME = {
  // Cited answer from the library: the full card with an emerald top rule.
  answer: "border-t-4 border-accent",
  // Nothing in the library covers it: a quieter card.
  not_found: "border-t-4 border-rule",
  // Greeting / thanks: a light reply, no card chrome beyond the border.
  small_talk: "",
};

const FOOTNOTE = {
  answer: "No saved passage matched this question closely enough to cite.",
  not_found: "Try rephrasing, or add a note or link about this in the sidebar.",
  small_talk: null,
};

/** One reply: the formatted text and, for library answers, the sources it cites. Anchors are unique per turn. */
export function AnswerView({ turnId, result, activeSource, onActivateSource }) {
  const { answer, sources } = result;
  const kind = result.kind ?? "answer";
  const anchorPrefix = `source-${turnId}`;
  const footnote = sources.length === 0 ? FOOTNOTE[kind] : null;

  return (
    <article
      aria-label="Answer"
      data-kind={kind}
      className={`overflow-hidden rounded-3xl border border-rule bg-surface ${
        kind === "answer" ? "shadow-[0_2px_4px_rgb(20_22_28/0.04),0_24px_48px_-24px_rgb(5_150_105/0.22)]" : ""
      }`}
    >
      <div className={`${FRAME[kind]} px-6 py-6 sm:px-9 sm:py-7`}>
        <AnswerBody
          text={answer}
          sourceCount={sources.length}
          anchorPrefix={anchorPrefix}
          activeSource={activeSource}
          onActivateSource={onActivateSource}
        />
        {footnote && <p className="mt-4 text-[0.9375rem] text-muted">{footnote}</p>}
      </div>
      {sources.length > 0 && (
        <SourceList sources={sources} anchorPrefix={anchorPrefix} activeSource={activeSource} onActivate={onActivateSource} />
      )}
    </article>
  );
}
