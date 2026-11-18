import { Fragment, useMemo } from "react";
import { parseBlocks, parseInline } from "../lib/answerFormat.js";
import { CitationChip } from "./CitationChip.jsx";

function Inline({ text, sourceCount, anchorPrefix, activeSource, onActivateSource }) {
  return parseInline(text, sourceCount).map((segment, i) => {
    switch (segment.type) {
      case "cite":
        return (
          <CitationChip
            key={i}
            n={segment.n}
            anchorId={`${anchorPrefix}-${segment.n}`}
            active={activeSource === segment.n}
            onActivate={onActivateSource}
          />
        );
      case "code":
        return (
          <code key={i} className="rounded-md bg-paper px-1.5 py-0.5 font-mono text-[0.85em] text-ink">
            {segment.text}
          </code>
        );
      case "bold":
        return (
          <strong key={i} className="font-semibold">
            {segment.text}
          </strong>
        );
      default:
        return <Fragment key={i}>{segment.text}</Fragment>;
    }
  });
}

/** Renders a model answer: paragraphs and bullet lists with inline citations. */
export function AnswerBody({ text, sourceCount, anchorPrefix, activeSource, onActivateSource }) {
  const blocks = useMemo(() => parseBlocks(text), [text]);
  const inlineProps = { sourceCount, anchorPrefix, activeSource, onActivateSource };

  return (
    <div className="space-y-4 text-xl leading-[1.7] text-ink">
      {blocks.map((block, i) =>
        block.type === "list" ? (
          <ul key={i} className="space-y-2.5 pl-1">
            {block.items.map((item, j) => (
              <li key={j} className="flex gap-3">
                <span aria-hidden="true" className="mt-[0.7em] size-1.5 shrink-0 rounded-full bg-accent" />
                <span>
                  <Inline text={item} {...inlineProps} />
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p key={i}>
            <Inline text={block.text} {...inlineProps} />
          </p>
        ),
      )}
    </div>
  );
}
