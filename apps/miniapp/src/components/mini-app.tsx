"use client";

import { useMemo, useState } from "react";

import type { CharacterItem, MiniAppState } from "../lib/api";

type Props = {
  state: MiniAppState;
  onAcceptExplicit: () => void | Promise<void>;
};

type Panel = "home" | "guide" | "access" | "profile";

export function MiniApp({ state, onAcceptExplicit }: Props) {
  const [selectedId, setSelectedId] = useState<string | null>(state.characters.items[0]?.id ?? null);
  const [activePanel, setActivePanel] = useState<Panel>("guide");
  const [tuneMessage, setTuneMessage] = useState<string>("");
  const selected = useMemo(
    () => state.characters.items.find((item) => item.id === selectedId) ?? state.characters.items[0],
    [selectedId, state.characters.items],
  );
  const selectedIndex = selected ? state.characters.items.findIndex((item) => item.id === selected.id) : -1;
  const selectedChannel = channelNumber(selectedIndex);
  const messageLimit = state.usage.messages.limit;
  const messageUsed = state.usage.messages.used;
  const passLabel = planPassLabel(state.entitlements.tier);
  const selectedAccess = selected ? accessLabel(selected) : "NO SIGNAL";

  function handleSelect(item: CharacterItem) {
    setSelectedId(item.id);
    setTuneMessage("");
    setActivePanel("guide");
  }

  function handleTune() {
    if (!selected) {
      setTuneMessage("Choose a channel first.");
      return;
    }

    if (selected.category === "explicit" && selected.access.reasons.includes("explicit_consent_required")) {
      setTuneMessage("18+ consent is required before this channel can be tuned.");
      setActivePanel("access");
      return;
    }

    if (!selected.access.allowed) {
      setTuneMessage(`${selected.title} is ${lockedReason(selected)}.`);
      setActivePanel("access");
      return;
    }

    setTuneMessage(`${selected.title} is ready. Return to Telegram and choose ${selected.title} in Mode.`);
  }

  function returnToTelegram() {
    window.Telegram?.WebApp?.close?.();
  }

  return (
    <main className="shell" id="home" data-testid="mini-app-shell">
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

      <section className={`preview ${selected?.access.allowed ? "" : "scrambled"}`} aria-label="Selected channel">
        <div className="preview-screen">
          <div className="preview-topline">
            <span className="tracking" data-testid="selected-channel-number">
              {selectedChannel}
            </span>
            <span className={`signal ${selected?.access.allowed ? "on-air" : "locked"}`}>{selectedAccess}</span>
          </div>
          <h2 data-testid="selected-channel-title">{selected?.title ?? "Channel Guide"}</h2>
          <p>{selected ? channelHint(selected.category) : "Choose a persona channel to tune the Telegram chat."}</p>
          {selected ? (
            <p className="mode-line">
              Mode signal <strong>{selected.mode}</strong>
            </p>
          ) : null}
        </div>
        <button className="primary-command" type="button" onClick={handleTune}>
          Tune In
        </button>
        {tuneMessage ? (
          <div className="tune-status" role="status">
            <p>{tuneMessage}</p>
            {selected?.access.allowed ? (
              <button className="secondary-command" type="button" onClick={returnToTelegram}>
                Return to Telegram
              </button>
            ) : null}
          </div>
        ) : null}
      </section>

      {activePanel === "home" ? (
        <section className="panel-stack" role="tabpanel" aria-label="Home">
          <article className="info-panel">
            <p className="label">Now airing</p>
            <h2>{selected?.title ?? "Channel Guide"}</h2>
            <p>{selected ? `${selectedChannel} ${channelHint(selected.category)}` : "Choose a channel from Chats."}</p>
            <p>{selected ? `${accessLabel(selected)} / ${passLabel}` : "No channel selected"}</p>
          </article>
        </section>
      ) : null}

      {activePanel === "guide" ? (
        <section className="guide" id="channels" role="tabpanel" aria-label="Guide">
          {state.characters.items.map((item, index) => {
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
                  <span className="channel-description">{channelHint(item.category)}</span>
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
                </span>
              </button>
            );
          })}
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

      <nav className="bottom-nav" aria-label="Mini App sections">
        <button type="button" aria-selected={activePanel === "home"} onClick={() => setActivePanel("home")}>
          Home
        </button>
        <button type="button" aria-selected={activePanel === "guide"} onClick={() => setActivePanel("guide")}>
          Chats
        </button>
        <button type="button" aria-selected={activePanel === "access"} onClick={() => setActivePanel("access")}>
          Access
        </button>
        <button type="button" aria-selected={activePanel === "profile"} onClick={() => setActivePanel("profile")}>
          Profile
        </button>
      </nav>
    </main>
  );
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
