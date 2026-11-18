import { splitCitations } from "./citations.js";

/**
 * A deliberately small formatter for model answers: paragraphs, "-"/"*" bullet
 * lists, **bold**, `code` and [n] citations. Anything else stays plain text, and
 * nothing is ever injected as HTML.
 */

const BULLET = /^\s*(?:[-*•]|\d+[.)])\s+/;
const INLINE = /(`[^`\n]+`|\*\*[^*\n]+\*\*)/;

export function parseBlocks(text) {
  const blocks = [];
  let paragraph = [];

  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ type: "paragraph", text: paragraph.join(" ") });
    paragraph = [];
  };

  for (const line of text.split("\n")) {
    if (!line.trim()) {
      flushParagraph();
    } else if (BULLET.test(line)) {
      flushParagraph();
      const last = blocks.at(-1);
      const item = line.replace(BULLET, "").trim();
      if (last?.type === "list") last.items.push(item);
      else blocks.push({ type: "list", items: [item] });
    } else {
      paragraph.push(line.trim());
    }
  }
  flushParagraph();
  return blocks;
}

/** Inline segments: text | cite | code | bold. */
export function parseInline(text, sourceCount) {
  return text
    .split(INLINE)
    .filter(Boolean)
    .flatMap((part) => {
      if (part.startsWith("`") && part.endsWith("`")) return [{ type: "code", text: part.slice(1, -1) }];
      if (part.startsWith("**") && part.endsWith("**")) return [{ type: "bold", text: part.slice(2, -2) }];
      return splitCitations(part, sourceCount);
    });
}
