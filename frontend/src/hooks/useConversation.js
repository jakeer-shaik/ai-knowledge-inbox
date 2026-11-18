import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";

const EMPTY = { conversationId: null, turns: [], pending: null, failed: null, opening: false, openError: null };

/**
 * The conversation on the main stage.
 *  - send(question): asks in the current conversation (or starts one), appending the turn
 *  - open(id):       loads a past conversation from history
 *  - newChat():      clears the stage for a fresh conversation
 * Starting any of these cancels the previous request, so a slow reply can't land in the wrong thread.
 */
export function useConversation({ onTurn } = {}) {
  const [state, setState] = useState(EMPTY);
  const stateRef = useRef(state);
  stateRef.current = state;
  const controllerRef = useRef(null);
  const onTurnRef = useRef(onTurn);
  onTurnRef.current = onTurn;

  const startRequest = () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    return controller;
  };

  const send = useCallback(async (question) => {
    const controller = startRequest();
    const { conversationId } = stateRef.current;
    setState((s) => ({ ...s, pending: { question }, failed: null }));

    try {
      const turn = await api.query(
        conversationId ? { question, conversation_id: conversationId } : { question },
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      setState((s) => ({ ...s, conversationId: turn.conversation_id, turns: [...s.turns, turn], pending: null }));
      onTurnRef.current?.(turn, { isNewConversation: !conversationId });
    } catch (err) {
      if (err.name === "AbortError" || controller.signal.aborted) return;
      setState((s) => ({ ...s, pending: null, failed: { question, error: err } }));
    }
  }, []);

  const open = useCallback(async (id) => {
    const controller = startRequest();
    setState({ ...EMPTY, conversationId: id, opening: true });
    try {
      const conversation = await api.getConversation(id, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setState({ ...EMPTY, conversationId: id, turns: conversation.turns });
    } catch (err) {
      if (err.name === "AbortError" || controller.signal.aborted) return;
      setState({ ...EMPTY, openError: err });
    }
  }, []);

  const newChat = useCallback(() => {
    controllerRef.current?.abort();
    setState(EMPTY);
  }, []);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const isEmpty = state.turns.length === 0 && !state.pending && !state.failed && !state.opening && !state.openError;
  return { ...state, isEmpty, send, open, newChat };
}
