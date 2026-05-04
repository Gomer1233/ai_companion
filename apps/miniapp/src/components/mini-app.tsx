"use client";

import type { MiniAppState } from "../lib/api";

type Props = {
  state: MiniAppState;
  onAcceptExplicit: () => void | Promise<void>;
};

export function MiniApp({ state, onAcceptExplicit }: Props) {
  const selected = state.characters.items[0];
  const messageLimit = state.usage.messages.limit;
  const messageUsed = state.usage.messages.used;
  const passLabel = planPassLabel(state.entitlements.tier);

  return (
    <main className="shell" id="home" data-testid="mini-app-shell">
      <header className="osd">
        <div>
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
      </section>

      <section className="preview" aria-label="Selected channel">
        <div className="preview-screen">
          <span className="tracking">CH 001</span>
          <h2>{selected?.title ?? "Channel Guide"}</h2>
          <p>{selected ? channelHint(selected.category) : "Choose a persona channel to tune the Telegram chat."}</p>
        </div>
        <button className="primary-command" type="button">
          Tune In
        </button>
      </section>

      <section className="guide" id="channels" aria-label="Channels">
        {state.characters.items.map((item, index) => (
          <article className={`channel-row ${item.category === "explicit" ? "restricted" : ""}`} key={item.id}>
            <div className="channel-number">CH {String(index + 1).padStart(3, "0")}</div>
            <div className="channel-copy">
              <h3>{item.title}</h3>
              <p>{channelHint(item.category)}</p>
            </div>
            <div className="badges">
              {item.default_tier === "premium" ? <span className="badge vip">VIP</span> : <span className="badge">FREE</span>}
              {!item.access.allowed ? (
                <span className="badge">LOCKED</span>
              ) : null}
              {item.category === "explicit" ? (
                <span className="badge danger">{item.access.allowed ? "18+ OPEN" : "18+ LOCKED"}</span>
              ) : null}
            </div>
          </article>
        ))}

        {!state.entitlements.explicit_consent ? (
          <article className="channel-row restricted consent-row">
            <div className="channel-number">CH 18+</div>
            <div className="channel-copy">
              <h3>Restricted 18+ Channel</h3>
              <p>Age-gated access is confirmed by the backend before explicit channels open.</p>
            </div>
            <button className="danger-command" type="button" onClick={onAcceptExplicit}>
              Confirm 18+ Access
            </button>
          </article>
        ) : null}
      </section>

      <section className="info-grid" aria-label="Limits and profile">
        <article className="info-panel" id="access">
          <p className="label">Limits</p>
          <h2>Access Meter</h2>
          <p>History {state.usage.history_limit}</p>
          <p>Cooldown {state.usage.image_cooldown_sec} sec</p>
          <p>
            Explicit images {state.usage.explicit_images.used} / {state.usage.explicit_images.limit}
          </p>
        </article>
        <article className="info-panel" id="profile">
          <p className="label">Profile</p>
          <h2>User {state.me.user_id}</h2>
          <p>Plan {state.entitlements.tier.toUpperCase()}</p>
          <p>Session {state.me.session_expires_at}</p>
        </article>
      </section>

      <nav className="bottom-nav" aria-label="Mini App sections">
        <a href="#home">Home</a>
        <a href="#channels">Chats</a>
        <a href="#access">Access</a>
        <a href="#profile">Profile</a>
      </nav>
    </main>
  );
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
