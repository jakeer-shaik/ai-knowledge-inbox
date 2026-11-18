import { useEffect, useRef } from "react";
import { AnswerView } from "./AnswerView.jsx";
import { ChatInput } from "./ChatInput.jsx";
import { Button } from "./ui/Button.jsx";
import { BookLoader } from "./ui/BookLoader.jsx";
import { ErrorNotice } from "./ui/ErrorNotice.jsx";

const prefersReducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

function QuestionBubble({ children }) {
  return (
    <div className="flex justify-end">
      <p className="max-w-[85%] rounded-3xl rounded-br-lg bg-accent px-5 py-3 text-lg leading-snug text-white">{children}</p>
    </div>
  );
}

function SearchedFor({ query }) {
  return (
    <p className="mt-2 text-right text-[0.8125rem] text-muted">
      Searched for <span className="font-medium text-ink">“{query}”</span>
    </p>
  );
}

function Turn({ turn, activeSource, onActivateSource }) {
  const isActive = activeSource?.turnId === turn.id;
  return (
    <section aria-label={`Question: ${turn.question}`} className="space-y-4">
      <div>
        <QuestionBubble>{turn.question}</QuestionBubble>
        {turn.search_query && turn.search_query !== turn.question && <SearchedFor query={turn.search_query} />}
      </div>
      <AnswerView
        turnId={turn.id}
        result={turn}
        activeSource={isActive ? activeSource.n : null}
        onActivateSource={(n) => onActivateSource(n ? { turnId: turn.id, n } : null)}
      />
    </section>
  );
}

function hintFor(readyCount) {
  if (readyCount === 0) return "Save a note or a link first. Answers come only from your library.";
  return `Searching ${readyCount} saved ${readyCount === 1 ? "item" : "items"}. Every answer cites the passages it used.`;
}

/** The main stage: a centred prompt for a new chat, or the thread with a follow-up box pinned below. */
export function ChatPanel({ chat, readyCount, activeSource, onActivateSource }) {
  const endRef = useRef(null);
  const inputRef = useRef(null);
  const busy = Boolean(chat.pending);

  // Keep the newest exchange in view as the thread grows.
  useEffect(() => {
    if (chat.isEmpty) return;
    endRef.current?.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "end" });
  }, [chat.turns.length, chat.pending, chat.failed, chat.isEmpty]);

  // New chat: put the cursor straight in the box.
  useEffect(() => {
    if (chat.isEmpty) inputRef.current?.focus({ preventScroll: true });
  }, [chat.isEmpty, chat.conversationId]);

  if (chat.isEmpty) {
    return (
      <section aria-labelledby="ask-heading" className="lg:pt-[13vh]">
        <h1
          id="ask-heading"
          className="mb-7 font-display text-[2.25rem] leading-[1.05] font-extrabold tracking-tight text-balance text-ink sm:text-[3.25rem]"
        >
          What do you want to know?
        </h1>
        <ChatInput
          ref={inputRef}
          label="What do you want to know?"
          labelHidden
          placeholder="Ask about anything you've saved"
          hint={hintFor(readyCount)}
          busy={busy}
          onSend={chat.send}
        />
      </section>
    );
  }

  const title = chat.turns[0]?.question ?? chat.pending?.question ?? chat.failed?.question ?? "Conversation";

  return (
    <section aria-label="Conversation" className="flex min-h-[calc(100dvh-2rem)] flex-col">
      <header className="sticky top-0 z-10 -mx-4 mb-6 flex items-center justify-between gap-4 border-b border-rule bg-paper/90 px-4 py-3 backdrop-blur sm:-mx-8 sm:px-8">
        <h1 className="truncate font-display text-lg font-bold text-ink">{title}</h1>
        <Button type="button" variant="secondary" size="sm" onClick={chat.newChat}>
          New chat
        </Button>
      </header>

      <div className="flex-1 space-y-10 pb-8">
        {chat.opening && <BookLoader label="Opening conversation" />}
        {chat.openError && (
          <ErrorNotice title="Couldn't open this conversation" message={chat.openError.message} actionLabel="Start a new chat" onAction={chat.newChat} />
        )}

        {chat.turns.map((turn) => (
          <Turn key={turn.id} turn={turn} activeSource={activeSource} onActivateSource={onActivateSource} />
        ))}

        {chat.pending && (
          <section aria-label="Waiting for answer" className="space-y-4" aria-busy="true">
            <QuestionBubble>{chat.pending.question}</QuestionBubble>
            <BookLoader label="Searching your library" />
          </section>
        )}

        {chat.failed && (
          <section className="space-y-4">
            <QuestionBubble>{chat.failed.question}</QuestionBubble>
            <ErrorNotice
              title="Couldn't get an answer"
              message={chat.failed.error?.message}
              actionLabel="Ask again"
              onAction={() => chat.send(chat.failed.question)}
            />
          </section>
        )}
        <div ref={endRef} />
      </div>

      <div className="sticky bottom-0 -mx-4 bg-gradient-to-t from-paper from-70% to-transparent px-4 pt-6 pb-4 sm:-mx-8 sm:px-8">
        <ChatInput
          ref={inputRef}
          label="Ask a follow-up question"
          labelHidden
          placeholder="Ask a follow-up…"
          hint="Follow-ups are read in the context of this conversation."
          busy={busy || chat.opening}
          onSend={chat.send}
        />
      </div>
    </section>
  );
}
