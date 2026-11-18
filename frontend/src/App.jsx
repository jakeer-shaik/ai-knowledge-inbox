import { useState } from "react";
import { AppHeader } from "./components/AppHeader.jsx";
import { ChatPanel } from "./components/ChatPanel.jsx";
import { Composer } from "./components/Composer.jsx";
import { HistoryList } from "./components/HistoryList.jsx";
import { ItemList } from "./components/ItemList.jsx";
import { SidebarTabs } from "./components/SidebarTabs.jsx";
import { useConversation } from "./hooks/useConversation.js";
import { useHistory } from "./hooks/useHistory.js";
import { useItems } from "./hooks/useItems.js";

/**
 * Split pane: the sidebar holds the add box plus Library / History tabs; the main
 * stage is the conversation. App owns cross-pane state: the active tab and which
 * cited source ({ turnId, n }) is highlighted, so its library item lights up too.
 */
export default function App() {
  const items = useItems();
  const history = useHistory();
  const chat = useConversation({ onTurn: history.recordTurn });
  const [tab, setTab] = useState("library");
  const [activeSource, setActiveSource] = useState(null);

  const activeTurn = activeSource && chat.turns.find((turn) => turn.id === activeSource.turnId);
  const highlightedItemId = activeTurn?.sources[activeSource.n - 1]?.item_id ?? null;

  function openConversation(id) {
    setActiveSource(null);
    chat.open(id);
  }

  function startNewChat() {
    setActiveSource(null);
    chat.newChat();
  }

  async function deleteConversation(id) {
    await history.remove(id);
    if (id === chat.conversationId) startNewChat();
  }

  const tabs = [
    { id: "library", label: "Library", count: items.status === "ready" ? items.items.length : null },
    { id: "history", label: "History", count: history.status === "ready" ? history.conversations.length : null },
  ];

  return (
    <div className="grid min-h-dvh grid-cols-1 lg:grid-cols-[minmax(360px,420px)_minmax(0,1fr)]">
      <aside aria-label="Your library" className="flex min-w-0 flex-col bg-night lg:sticky lg:top-0 lg:h-dvh">
        <AppHeader />
        <div className="px-6 pb-5">
          <Composer onSave={items.addItem} />
        </div>

        <SidebarTabs tabs={tabs} active={tab} onChange={setTab} />
        <div id={`${tab}-panel`} role="tabpanel" aria-labelledby={`${tab}-tab`} className="flex min-h-0 flex-1 flex-col">
          {tab === "library" ? (
            <ItemList
              items={items.items}
              status={items.status}
              error={items.error}
              onRetry={items.refresh}
              highlightedItemId={highlightedItemId}
            />
          ) : (
            <HistoryList
              conversations={history.conversations}
              status={history.status}
              error={history.error}
              onRetry={history.refresh}
              activeId={chat.conversationId}
              onOpen={openConversation}
              onDelete={deleteConversation}
              onNewChat={startNewChat}
            />
          )}
        </div>
      </aside>

      <main className="min-w-0 px-4 pt-4 sm:px-8 lg:px-16">
        <div className="mx-auto max-w-3xl">
          <ChatPanel chat={chat} readyCount={items.readyCount} activeSource={activeSource} onActivateSource={setActiveSource} />
        </div>
      </main>
    </div>
  );
}
