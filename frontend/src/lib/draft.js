import { validateUrl } from "./validators.js";

/** Accept "www.example.com" as shorthand for "https://www.example.com". */
export function normalizeUrl(text) {
  const trimmed = text.trim();
  return /^www\./i.test(trimmed) ? `https://${trimmed}` : trimmed;
}

export const validateLink = (value) => validateUrl(normalizeUrl(value));
