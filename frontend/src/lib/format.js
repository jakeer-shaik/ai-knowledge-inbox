const relativeFormatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
const absoluteFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

const UNITS = [
  ["year", 60 * 60 * 24 * 365],
  ["month", 60 * 60 * 24 * 30],
  ["day", 60 * 60 * 24],
  ["hour", 60 * 60],
  ["minute", 60],
];

export function relativeTime(iso, now = Date.now()) {
  const seconds = (new Date(iso).getTime() - now) / 1000;
  if (Math.abs(seconds) < 45) return "just now";
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return relativeFormatter.format(Math.round(seconds / size), unit);
  }
  return relativeFormatter.format(Math.round(seconds / 60), "minute");
}

export function absoluteTime(iso) {
  return absoluteFormatter.format(new Date(iso));
}

export function hostname(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function itemTitle(item) {
  return item.title || (item.url ? hostname(item.url) : "Untitled note");
}

/** "Note" or the site name, used as the secondary line under a title. */
export function sourceLabel(item) {
  return item.source_type === "url" ? hostname(item.url) : "Note";
}
