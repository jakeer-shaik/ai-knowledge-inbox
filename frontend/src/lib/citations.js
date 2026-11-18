const CITATION = /\[(\d+)\]/g;

/**
 * Splits an answer into text and citation segments.
 * Only markers that point at a real source (1..sourceCount) become citations;
 * anything else is left as plain text so a hallucinated "[7]" never renders as a link.
 */
export function splitCitations(text, sourceCount) {
  const segments = [];
  let lastIndex = 0;
  for (const match of text.matchAll(CITATION)) {
    const n = Number(match[1]);
    if (n < 1 || n > sourceCount) continue;
    if (match.index > lastIndex) segments.push({ type: "text", text: text.slice(lastIndex, match.index) });
    segments.push({ type: "cite", n });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) segments.push({ type: "text", text: text.slice(lastIndex) });
  return segments;
}
