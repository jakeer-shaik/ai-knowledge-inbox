import { useState } from "react";
import { relativeTime } from "../lib/format.js";
import { ErrorNotice } from "./ui/ErrorNotice.jsx";

function TrashIcon(props) {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
      <path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3" />
    </svg>
  );
}

function PlusIcon(props) {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden="true" {...props}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

function ConversationRow({ conversation, active, onOpen, onDelete }) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const count = conversation.turn_count;

  async function confirmDelete() {
    setDeleting(true);
    try {
      await onDelete(conversation.id);
    } catch {
      setDeleting(false);
      setConfirming(false);
    }
  }

  if (confirming) {
    return (
      <li className="rounded-2xl bg-night-raised px-3 py-3">
        <p className="text-sm text-night-ink">Delete this conversation and its {count === 1 ? "answer" : `${count} answers`}?</p>
        <div className="mt-2.5 flex gap-2">
          <button
            type="button"
            onClick={confirmDelete}
            aria-busy={deleting || undefined}
            className="h-8 rounded-lg bg-coral px-3 text-sm font-semibold text-night hover:bg-coral/90"
          >
            {deleting ? "Deleting…" : "Delete conversation"}
          </button>
          <button
            type="button"
            onClick={() => setConfirming(false)}
            className="h-8 rounded-lg px-3 text-sm font-semibold text-night-muted hover:text-night-ink"
          >
            Keep
          </button>
        </div>
      </li>
    );
  }

  return (
    <li className={`group relative rounded-2xl ${active ? "bg-night-raised ring-1 ring-accent-light/50" : "hover:bg-night-raised"}`}>
      <button
        type="button"
        onClick={() => onOpen(conversation.id)}
        aria-current={active ? "true" : undefined}
        className="block w-full rounded-2xl px-3 py-3 pr-11 text-left focus-visible:outline-accent-light"
      >
        <span className="line-clamp-2 text-[0.9375rem] font-semibold leading-snug text-night-ink">{conversation.title}</span>
        <span className="mt-1 block text-[0.8125rem] text-night-muted">
          {relativeTime(conversation.updated_at)}, {count} {count === 1 ? "question" : "questions"}
        </span>
      </button>
      <button
        type="button"
        onClick={() => setConfirming(true)}
        aria-label={`Delete conversation "${conversation.title}"`}
        title="Delete conversation"
        className="absolute top-2.5 right-2 grid size-8 place-items-center rounded-lg text-night-muted opacity-0 group-hover:opacity-100 hover:bg-night-rule hover:text-coral focus-visible:opacity-100 focus-visible:outline-accent-light"
      >
        <TrashIcon />
      </button>
    </li>
  );
}

export function HistoryList({ conversations, status, error, onRetry, activeId, onOpen, onDelete, onNewChat }) {
  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-6">
      <button
        type="button"
        onClick={onNewChat}
        className="mb-2 flex w-full items-center gap-2 rounded-2xl border border-dashed border-night-rule px-3 py-2.5 text-sm font-semibold text-accent-light hover:border-accent-light/60 hover:bg-night-raised focus-visible:outline-accent-light"
      >
        <PlusIcon />
        New chat
      </button>

      {status === "error" ? (
        <ErrorNotice className="mx-3" title="Couldn't load your history" message={error?.message} actionLabel="Try again" onAction={onRetry} />
      ) : status === "ready" && conversations.length === 0 ? (
        <div className="mx-3 mt-2 px-2 py-5 text-center">
          <p className="text-base font-semibold text-night-ink">No conversations yet</p>
          <p className="mx-auto mt-1 max-w-[30ch] text-sm leading-relaxed text-night-muted">
            Every conversation is saved here, so you can reopen it and keep asking.
          </p>
        </div>
      ) : (
        <ul className="space-y-1" aria-busy={status === "loading"}>
          {conversations.map((conversation) => (
            <ConversationRow
              key={conversation.id}
              conversation={conversation}
              active={conversation.id === activeId}
              onOpen={onOpen}
              onDelete={onDelete}
            />
          ))}
        </ul>
      )}
    </div>
  );
}
