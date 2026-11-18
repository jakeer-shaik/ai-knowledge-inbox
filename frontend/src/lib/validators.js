/** Field validators. Each returns an error message that says how to fix it, or null. */

export const MAX_NOTE_CHARS = 20_000;
export const MAX_QUESTION_CHARS = 500;

export function validateNote(value) {
  const text = value.trim();
  if (!text) return "Write something to save.";
  if (text.length > MAX_NOTE_CHARS) return `Shorten the note to under ${MAX_NOTE_CHARS.toLocaleString()} characters.`;
  return null;
}

export function validateUrl(value) {
  const text = value.trim();
  if (!text) return "Paste a link to save, like https://example.com/article.";
  let url;
  try {
    url = new URL(text);
  } catch {
    return "Enter the full link, starting with https://";
  }
  if (url.protocol !== "http:" && url.protocol !== "https:") return "Use a link that starts with http:// or https://";
  return null;
}

export function validateQuestion(value) {
  const text = value.trim();
  if (!text) return "Type a question to ask.";
  if (text.length > MAX_QUESTION_CHARS) return `Shorten the question to under ${MAX_QUESTION_CHARS} characters.`;
  return null;
}
