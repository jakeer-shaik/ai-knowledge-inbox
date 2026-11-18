import { useCallback, useEffect, useState } from "react";
import { api } from "../api";

/** Conversation history, most recent first. New turns update it locally, without a refetch. */
export function useHistory() {
  const [conversations, setConversations] = useState([]);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setConversations(await api.listConversations());
      setStatus("ready");
      setError(null);
    } catch (err) {
      setError(err);
      setStatus("error");
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  /** Move the turn's conversation to the top (creating it on the first turn). */
  const recordTurn = useCallback((turn) => {
    setConversations((current) => {
      const existing = current.find((c) => c.id === turn.conversation_id);
      const updated = existing
        ? { ...existing, turn_count: existing.turn_count + 1, updated_at: turn.created_at }
        : { id: turn.conversation_id, title: turn.question, turn_count: 1, created_at: turn.created_at, updated_at: turn.created_at };
      return [updated, ...current.filter((c) => c.id !== turn.conversation_id)];
    });
  }, []);

  const remove = useCallback(async (id) => {
    await api.deleteConversation(id);
    setConversations((current) => current.filter((c) => c.id !== id));
  }, []);

  return { conversations, status, error, refresh, recordTurn, remove };
}
