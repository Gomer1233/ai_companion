import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MiniApp } from "../src/components/mini-app";
import type { MiniAppState } from "../src/lib/api";

const state: MiniAppState = {
  me: { user_id: "42", session_expires_at: 999 },
  characters: {
    items: [
      {
        id: "basic",
        mode: "basic",
        title: "AI Assistant",
        category: "assistant",
        default_tier: "free",
        access: { allowed: true, reasons: [] },
      },
      {
        id: "coach",
        mode: "coach_premium",
        title: "Coach",
        category: "practice",
        default_tier: "premium",
        access: { allowed: false, reasons: ["premium_required"] },
      },
      {
        id: "whore",
        mode: "whore",
        title: "Flirt 18+",
        category: "explicit",
        default_tier: "premium",
        access: { allowed: false, reasons: ["explicit_consent_required"] },
      },
    ],
  },
  entitlements: {
    tier: "free",
    tier_expires_at: null,
    has_premium: false,
    explicit_consent: false,
    consent_required: true,
    blocked_reasons: [],
  },
  usage: {
    history_limit: 12,
    image_cooldown_sec: 300,
    messages: { used: 4, limit: 30, reset_at: 1234 },
    explicit_images: { used: 0, limit: 0, reset_at: 1234 },
  },
};

describe("MiniApp", () => {
  it("renders the midnight channel guide from backend-owned state", () => {
    render(<MiniApp state={state} onAcceptExplicit={vi.fn()} />);

    expect(screen.getByText("Lina")).toBeInTheDocument();
    expect(screen.getAllByText("FREE PASS")).toHaveLength(2);
    expect(screen.getAllByText("CH 001")).toHaveLength(2);
    expect(screen.getAllByText("AI Assistant")).toHaveLength(2);
    expect(screen.getByText("Coach")).toBeInTheDocument();
    expect(screen.getAllByText("VIP")).toHaveLength(2);
    expect(screen.getAllByText("LOCKED")).toHaveLength(3);
    expect(screen.getByText("18+ LOCKED")).toBeInTheDocument();
    expect(screen.getByText("4 / 30")).toBeInTheDocument();
    expect(screen.getByText("History 12")).toBeInTheDocument();
    expect(screen.getByText("Cooldown 300 sec")).toBeInTheDocument();
    expect(screen.getByText("User 42")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Mini App sections" })).toBeInTheDocument();
    expect(document.getElementById("home")).not.toBeNull();
    expect(document.getElementById("channels")).not.toBeNull();
  });

  it("renders explicit trial access from backend access flags", () => {
    render(
      <MiniApp
        state={{
          ...state,
          characters: {
            items: state.characters.items.map((item) =>
              item.category === "explicit" ? { ...item, access: { allowed: true, reasons: [] } } : item,
            ),
          },
          entitlements: { ...state.entitlements, tier: "trial", explicit_consent: true, consent_required: false },
        }}
        onAcceptExplicit={vi.fn()}
      />,
    );

    expect(screen.getAllByText("TRIAL PASS")).toHaveLength(2);
    expect(screen.queryByText("FREE PASS")).not.toBeInTheDocument();
    expect(screen.queryByText("18+ LOCKED")).not.toBeInTheDocument();
    expect(screen.getByText("18+ OPEN")).toBeInTheDocument();
  });

  it("uses a backend consent action for restricted 18+ access", () => {
    const onAcceptExplicit = vi.fn();

    render(<MiniApp state={state} onAcceptExplicit={onAcceptExplicit} />);
    fireEvent.click(screen.getByRole("button", { name: "Access" }));
    expect(screen.getByText("18+ explicit access")).toBeInTheDocument();
    expect(
      screen.getByText(
        /This area may include explicit sexual or adult AI content.*you will not request illegal, non-consensual, exploitative, minor-related, abusive, or harmful content\./,
      ),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "I am 18+ and accept" }));

    expect(onAcceptExplicit).toHaveBeenCalledOnce();
  });

  it("lets the user select a channel and tune back in Telegram", () => {
    render(<MiniApp state={state} onAcceptExplicit={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /CH 002 Coach/ }));

    expect(screen.getByTestId("selected-channel-title")).toHaveTextContent("Coach");
    expect(screen.getByTestId("selected-channel-number")).toHaveTextContent("CH 002");

    fireEvent.click(screen.getByRole("button", { name: "Tune In" }));

    expect(screen.getByRole("status")).toHaveTextContent("Coach is Premium locked");
    expect(screen.getByRole("tabpanel", { name: "Access" })).toBeInTheDocument();
  });

  it("turns an open channel tune action into a Telegram chat instruction", () => {
    render(<MiniApp state={state} onAcceptExplicit={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Tune In" }));

    expect(screen.getByRole("status")).toHaveTextContent("AI Assistant is ready");
    expect(screen.getByRole("button", { name: "Return to Telegram" })).toBeInTheDocument();
    expect(screen.getByText(/choose AI Assistant in/)).toBeInTheDocument();
  });

  it("switches bottom panels instead of using inert links", () => {
    render(<MiniApp state={state} onAcceptExplicit={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Profile" }));

    expect(screen.getByRole("button", { name: "Profile" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "Profile" })).toHaveTextContent("User 42");
    expect(screen.getByText("/support miniapp")).toBeInTheDocument();
  });

  it("makes Home a distinct active destination", () => {
    render(<MiniApp state={state} onAcceptExplicit={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Profile" }));
    fireEvent.click(screen.getByRole("button", { name: "Home" }));

    expect(screen.getByRole("button", { name: "Home" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("button", { name: "Chats" })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("tabpanel", { name: "Home" })).toHaveTextContent("Now airing");
  });

  it("sends explicit locked selections to the consent contract", () => {
    render(<MiniApp state={state} onAcceptExplicit={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /CH 003 Flirt 18\+/ }));
    fireEvent.click(screen.getByRole("button", { name: "Tune In" }));

    expect(screen.getByRole("status")).toHaveTextContent("18+ consent is required");
    expect(screen.getByText("18+ explicit access")).toBeInTheDocument();
  });
});
