"use client";

import { useMemo, useState } from "react";
import type { FormEvent } from "react";

import type { ChatMessage, ChatSummary, CharacterItem, MiniAppState } from "../lib/api";

type Props = {
  state: MiniAppState;
  messagesByChat: Record<string, ChatMessage[]>;
  loadingChatIds?: Record<string, boolean>;
  chatErrors?: Record<string, string>;
  onAcceptExplicit: () => void | Promise<void>;
  onRefreshChat?: (characterId: string) => void | Promise<void>;
  onSelectChat?: (characterId: string) => void | Promise<void>;
  onSendMessage: (characterId: string, text: string) => void | Promise<void>;
};

type Panel = "chats" | "access" | "profile" | "support";

export function MiniApp({
  state,
  messagesByChat,
  loadingChatIds = {},
  chatErrors = {},
  onAcceptExplicit,
  onRefreshChat,
  onSelectChat,
  onSendMessage,
}: Props) {
  const chats = state.chats.items.length > 0 ? state.chats.items : state.characters.items.map(characterToChatSummary);
  const [selectedId, setSelectedId] = useState<string | null>(chats[0]?.id ?? null);
  const [activePanel, setActivePanel] = useState<Panel>("chats");
  const [draft, setDraft] = useState<string>("");
  const [isSending, setIsSending] = useState<boolean>(false);
  const [sendError, setSendError] = useState<string>("");
  const selected = useMemo(
    () => chats.find((item) => item.id === selectedId) ?? chats[0],
    [selectedId, chats],
  );
  const selectedIndex = selected ? chats.findIndex((item) => item.id === selected.id) : -1;
  const selectedChannel = channelNumber(selectedIndex);
  const messageLimit = state.usage.messages.limit;
  const messageUsed = state.usage.messages.used;
  const passLabel = planPassLabel(state.entitlements.tier);
  const selectedAccess = selected ? accessLabel(selected) : "NO SIGNAL";
  const selectedMessages = selected ? messagesByChat[selected.id] ?? [] : [];
  const selectedIsLoading = selected ? loadingChatIds[selected.id] === true : false;
  const selectedChatError = selected ? chatErrors[selected.id] ?? "" : "";
  const threadUnavailable = selectedIsLoading || selectedChatError.length > 0;
  const composerDisabled = !selected?.access.allowed || threadUnavailable;
  const lockText = selected && !selected.access.allowed ? lockedReason(selected) : "";
  const statusText = selectedIsLoading ? "Loading thread..." : selectedChatError || lockText || sendError;

  function handleSelect(item: ChatSummary) {
    setSelectedId(item.id);
    setActivePanel("chats");
    setDraft("");
    setSendError("");
    void onSelectChat?.(item.id);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!selected || !text || composerDisabled) {
      return;
    }
    setIsSending(true);
    setSendError("");
    try {
      await onSendMessage(selected.id, text);
      setDraft("");
    } catch (error) {
      setSendError(formatSendError(error));
    } finally {
      setIsSending(false);
    }
  }

  return (
    <main className="shell" data-testid="mini-app-shell">
      <header className="osd">
        <div className="osd-brand">
          <p className="osd-kicker">LIVE / MINI APP</p>
          <h1>Lina</h1>
        </div>
        <div className="osd-stack" aria-label="Account status">
          <span>{passLabel}</span>
          <span>USER {state.me.user_id}</span>
        </div>
      </header>

      <section className="access-panel" aria-label="Access pass">
        <div>
          <p className="label">Access</p>
          <strong>{passLabel}</strong>
        </div>
        <div>
          <p className="label">Messages</p>
          <strong>
            {messageUsed} / {messageLimit}
          </strong>
        </div>
        <div>
          <p className="label">18+</p>
          <strong>{state.entitlements.explicit_consent ? "OPEN" : "LOCKED"}</strong>
        </div>
        <div>
          <p className="label">History</p>
          <span>History {state.usage.history_limit}</span>
        </div>
        <div>
          <p className="label">Photo</p>
          <span>Cooldown {state.usage.image_cooldown_sec} sec</span>
        </div>
        <div>
          <p className="label">Profile</p>
          <span>User {state.me.user_id}</span>
        </div>
      </section>

      {activePanel === "chats" ? (
        <section className="chat-layout" id="channels" role="tabpanel" aria-label="Chats">
          <div className="guide" aria-label="Chats">
            {chats.map((item, index) => {
              const number = channelNumber(index);
              const isSelected = item.id === selected?.id;
              return (
                <button
                  aria-label={`${number} ${item.title}`}
                  aria-pressed={isSelected}
                  className={`channel-row ${item.category === "explicit" ? "restricted" : ""} ${isSelected ? "selected" : ""}`}
                  key={item.id}
                  type="button"
                  onClick={() => handleSelect(item)}
                >
                  <span className="channel-number">{number}</span>
                  <span className="channel-thumb" aria-hidden="true">
                    {channelInitial(item.title)}
                  </span>
                  <span className="channel-copy">
                    <span className="channel-title">{item.title}</span>
                    <span className="channel-description">{item.last_message?.content ?? channelHint(item.category)}</span>
                  </span>
                  <span className="badges">
                    {item.default_tier === "premium" ? (
                      <span className="badge vip">VIP</span>
                    ) : (
                      <span className="badge">FREE</span>
                    )}
                    {!item.access.allowed ? <span className="badge">LOCKED</span> : null}
                    {item.category === "explicit" ? (
                      <span className="badge danger">{item.access.allowed ? "18+ OPEN" : "18+ LOCKED"}</span>
                    ) : null}
                    {item.unread_count > 0 ? <span className="badge">{item.unread_count}</span> : null}
                  </span>
                </button>
              );
            })}
          </div>
          <section className={`chat-panel ${selected?.access.allowed ? "" : "scrambled"}`} aria-label="Selected chat">
            <div className="preview-topline">
              <span className="tracking" data-testid="selected-channel-number">
                {selectedChannel}
              </span>
              <div className="chat-actions">
                {selected ? (
                  <button
                    className="micro-command"
                    disabled={selectedIsLoading}
                    type="button"
                    onClick={() => void onRefreshChat?.(selected.id)}
                  >
                    Refresh thread
                  </button>
                ) : null}
                <span className={`signal ${selected?.access.allowed ? "on-air" : "locked"}`}>{selectedAccess}</span>
              </div>
            </div>
            <h2 data-testid="selected-channel-title">{selected?.title ?? "Channel Guide"}</h2>
            <div className="message-log" role="log" aria-label={`${selected?.title ?? "Lina"} chat history`}>
              {selectedIsLoading ? (
                <p className="empty-chat">Loading thread...</p>
              ) : selectedChatError ? (
                <p className="empty-chat">Thread unavailable.</p>
              ) : selectedMessages.length === 0 ? (
                <p className="empty-chat">{!selected?.access.allowed ? lockText : "Start this persona thread."}</p>
              ) : (
                selectedMessages.map((message) => (
                  <article className={`message-bubble ${message.role}`} key={message.id}>
                    <span>{message.role === "user" ? "You" : selected?.title ?? "Lina"}</span>
                    <p>{message.content}</p>
                  </article>
                ))
              )}
            </div>
            {statusText ? (
              <div className="tune-status" role="status">
                <p>{statusText}</p>
                {selectedChatError && selected ? (
                  <button className="secondary-command compact-command" type="button" onClick={() => void onRefreshChat?.(selected.id)}>
                    Retry thread
                  </button>
                ) : null}
              </div>
            ) : null}
            <form className="composer" onSubmit={handleSubmit}>
              <textarea
                aria-label={`Message ${selected?.title ?? "Lina"}`}
                disabled={composerDisabled}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={composerDisabled ? statusText : "Message"}
                value={draft}
              />
              <button className="primary-command" disabled={composerDisabled || isSending || draft.trim().length === 0} type="submit">
                {isSending ? "Sending" : "Send"}
              </button>
            </form>
          </section>
        </section>
      ) : null}

      {activePanel === "access" ? (
        <section className="panel-stack" id="access" role="tabpanel" aria-label="Access">
          <article className="info-panel">
            <p className="label">Limits</p>
            <h2>Access Meter</h2>
            <p>Plan {state.entitlements.tier.toUpperCase()}</p>
            <p>
              Messages {state.usage.messages.used} / {state.usage.messages.limit}
            </p>
            <p>
              Explicit images {state.usage.explicit_images.used} / {state.usage.explicit_images.limit}
            </p>
          </article>
          {!state.entitlements.explicit_consent ? (
            <article className="channel-row restricted consent-row">
              <div className="channel-number">CH 18+</div>
              <div className="channel-copy">
                <h3>18+ explicit access</h3>
                <p>
                  This area may include explicit sexual or adult AI content. By continuing, you confirm that you are at least
                  18 years old and that you will not request illegal, non-consensual, exploitative, minor-related, abusive, or
                  harmful content.
                </p>
              </div>
              <button className="danger-command" type="button" onClick={onAcceptExplicit}>
                I am 18+ and accept
              </button>
            </article>
          ) : null}
        </section>
      ) : null}

      {activePanel === "profile" ? (
        <section className="panel-stack" id="profile" role="tabpanel" aria-label="Profile">
          <article className="info-panel">
            <p className="label">Profile</p>
            <h2>User {state.me.user_id}</h2>
            <p>Plan {state.entitlements.tier.toUpperCase()}</p>
            <p>Session {state.me.session_expires_at}</p>
            <p>
              Support route <code>/support miniapp</code>
            </p>
          </article>
        </section>
      ) : null}

      {activePanel === "support" ? (
        <section className="panel-stack" id="support" role="tabpanel" aria-label="Support">
          <article className="info-panel">
            <p className="label">Support</p>
            <h2>Mini App support</h2>
            <p>
              Route <code>/support miniapp</code>
            </p>
            <p>Use this route for alpha access, session, consent, export, and deletion requests.</p>
          </article>
        </section>
      ) : null}

      <nav className="bottom-nav" aria-label="Mini App sections">
        <button type="button" aria-selected={activePanel === "chats"} onClick={() => setActivePanel("chats")}>
          Chats
        </button>
        <button type="button" aria-selected={activePanel === "access"} onClick={() => setActivePanel("access")}>
          Access
        </button>
        <button type="button" aria-selected={activePanel === "profile"} onClick={() => setActivePanel("profile")}>
          Profile
        </button>
        <button type="button" aria-selected={activePanel === "support"} onClick={() => setActivePanel("support")}>
          Support
        </button>
      </nav>
    </main>
  );
}

function characterToChatSummary(item: CharacterItem): ChatSummary {
  return {
    ...item,
    last_message: null,
    unread_count: 0,
  };
}

function formatSendError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error ?? "");
  if (message.includes(":429")) {
    return "Message limit reached.";
  }
  if (message.includes(":403")) {
    return "This persona is locked.";
  }
  return "Message could not be sent.";
}

function channelNumber(index: number): string {
  return index < 0 ? "CH 000" : `CH ${String(index + 1).padStart(3, "0")}`;
}

function channelInitial(title: string): string {
  return title.trim().charAt(0).toUpperCase() || "L";
}

function channelHint(category: string): string {
  const hints: Record<string, string> = {
    assistant: "Utility channel",
    practice: "Practice channel",
    wellbeing: "Support channel",
    life: "Life channel",
    entertainment: "Late-night channel",
    explicit: "Restricted channel",
  };
  return hints[category] ?? "Persona channel";
}

function accessLabel(item: CharacterItem): string {
  if (item.category === "explicit") {
    return item.access.allowed ? "18+ OPEN" : "18+ LOCKED";
  }
  return item.access.allowed ? "ON AIR" : "LOCKED";
}

function lockedReason(item: CharacterItem): string {
  if (item.access.reasons.includes("explicit_consent_required")) {
    return "18+ consent locked";
  }
  if (item.access.reasons.includes("premium_required")) {
    return "Premium locked";
  }
  return "currently locked";
}

function planPassLabel(tier: string): string {
  const normalized = tier.trim().toLowerCase();
  if (normalized === "premium" || normalized === "lifetime") {
    return "VIP PASS";
  }
  if (normalized === "trial") {
    return "TRIAL PASS";
  }
  if (normalized === "free") {
    return "FREE PASS";
  }
  return `${normalized.toUpperCase()} PASS`;
}
