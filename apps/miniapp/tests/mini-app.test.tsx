import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MiniApp } from "../src/components/mini-app";
import type { MiniAppState } from "../src/lib/api";

const state: MiniAppState = {
  me: { user_id: "42", session_expires_at: 999 },
  characters: {
    items: [
      { id: "basic", mode: "basic", title: "AI Assistant", category: "assistant", default_tier: "free" },
      { id: "coach", mode: "coach_premium", title: "Coach", category: "practice", default_tier: "premium" },
      { id: "whore", mode: "whore", title: "Flirt 18+", category: "explicit", default_tier: "premium" },
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
  });

  it("uses a backend consent action for restricted 18+ access", () => {
    const onAcceptExplicit = vi.fn();

    render(<MiniApp state={state} onAcceptExplicit={onAcceptExplicit} />);
    fireEvent.click(screen.getByRole("button", { name: "Confirm 18+ Access" }));

    expect(onAcceptExplicit).toHaveBeenCalledOnce();
  });
});
