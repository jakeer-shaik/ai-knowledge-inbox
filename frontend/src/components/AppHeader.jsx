import { useHealth } from "../hooks/useHealth.js";
import { InboxMark } from "./ui/icons.jsx";

const STATUS = {
  checking: { dot: "bg-night-muted", text: "Connecting…" },
  online: { dot: "bg-mint", text: "Connected" },
  offline: { dot: "bg-coral", text: "Server offline" },
};

export function AppHeader() {
  const { status } = useHealth();
  const { dot, text } = STATUS[status];

  return (
    <header className="flex items-center justify-between gap-4 px-6 pt-6 pb-5">
      <div className="flex items-center gap-3">
        <span className="grid size-9 place-items-center rounded-xl bg-accent text-white">
          <InboxMark width={20} height={20} />
        </span>
        <span className="font-display text-lg font-bold tracking-tight text-night-ink">Knowledge Inbox</span>
      </div>
      <p className="flex items-center gap-2 text-[0.8125rem] text-night-muted" role="status">
        <span aria-hidden="true" className={`size-2 rounded-full ${dot}`} />
        {text}
      </p>
    </header>
  );
}
