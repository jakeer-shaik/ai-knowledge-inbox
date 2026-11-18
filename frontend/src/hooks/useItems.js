import { useCallback, useEffect, useState } from "react";
import { api } from "../api";

const IN_PROGRESS = new Set(["pending", "processing"]);

/**
 * Saved items + ingestion.
 * Polls only while at least one item is still being indexed, then stops.
 */
export function useItems({ pollIntervalMs = 1000 } = {}) {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setItems(await api.listItems());
      setStatus("ready");
      setError(null);
    } catch (err) {
      setError(err);
      // Keep showing the last good list if a background refresh fails.
      setStatus((current) => (current === "ready" ? "ready" : "error"));
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const isIndexing = items.some((item) => IN_PROGRESS.has(item.status));

  useEffect(() => {
    if (!isIndexing) return undefined;
    const timer = setInterval(refresh, pollIntervalMs);
    return () => clearInterval(timer);
  }, [isIndexing, pollIntervalMs, refresh]);

  const addItem = useCallback(async (payload) => {
    const item = await api.ingest(payload);
    setItems((current) => [item, ...current]);
    return item;
  }, []);

  const readyCount = items.filter((item) => item.status === "ready").length;

  return { items, status, error, refresh, addItem, isIndexing, readyCount };
}
