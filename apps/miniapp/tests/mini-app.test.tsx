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
  chats: {
    items: [
      {
        id: "basic",
        mode: "basic",
        title: "AI Assistant",
        category: "assistant",
        default_tier: "free",
        access: { allowed: true, reasons: [] },
        last_message: { id: 10, role: "assistant", content: "Ready to help", created_at: 100 },
        unread_count: 0,
      },
      {
        id: "coach",
        mode: "coach_premium",
        title: "Coach",
        category: "practice",
        default_tier: "premium",
        access: { allowed: false, reasons: ["premium_required"] },
        last_message: null,
        unread_count: 0,
      },
      {
        id: "whore",
        mode: "whore",
        title: "Flirt 18+",
        category: "explicit",
        default_tier: "premium",
        access: { allowed: false, reasons: ["explicit_consent_required"] },
        last_message: null,
        unread_count: 0,
      },
    ],
  },
};

describe("MiniApp", () => {
  it("renders the midnight channel guide from backend-owned state", () => {
    render(<MiniApp state={state} messagesByChat={{ basic: [] }} onAcceptExplicit={vi.fn()} onSendMessage={vi.fn()} />);

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
    expect(document.getElementById("channels")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Chats" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByRole("button", { name: "Home" })).not.toBeInTheDocument();
  });

  it("renders explicit trial access from backend access flags", () => {
    render(
      <MiniApp
        state={{
          ...state,
          chats: {
            items: state.chats.items.map((item) =>
              item.category === "explicit" ? { ...item, access: { allowed: true, reasons: [] } } : item,
            ),
          },
          characters: {
            items: state.characters.items.map((item) =>
              item.category === "explicit" ? { ...item, access: { allowed: true, reasons: [] } } : item,
            ),
          },
          entitlements: { ...state.entitlements, tier: "trial", explicit_consent: true, consent_required: false },
        }}
        messagesByChat={{ basic: [] }}
        onAcceptExplicit={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getAllByText("TRIAL PASS")).toHaveLength(2);
    expect(screen.queryByText("FREE PASS")).not.toBeInTheDocument();
    expect(screen.queryByText("18+ LOCKED")).not.toBeInTheDocument();
    expect(screen.getByText("18+ OPEN")).toBeInTheDocument();
  });

  it("uses a backend consent action for restricted 18+ access", () => {
    const onAcceptExplicit = vi.fn();

    render(<MiniApp state={state} messagesByChat={{ basic: [] }} onAcceptExplicit={onAcceptExplicit} onSendMessage={vi.fn()} />);
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

  it("lets the user select a locked persona and keeps the chat blocked", () => {
    render(<MiniApp state={state} messagesByChat={{ basic: [] }} onAcceptExplicit={vi.fn()} onSendMessage={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /CH 002 Coach/ }));

    expect(screen.getByTestId("selected-channel-title")).toHaveTextContent("Coach");
    expect(screen.getByTestId("selected-channel-number")).toHaveTextContent("CH 002");
    expect(screen.getByRole("status")).toHaveTextContent("Premium locked");
    expect(screen.getByRole("textbox", { name: "Message Coach" })).toBeDisabled();
  });

  it("turns an open channel composer submit into a Mini App send", () => {
    const onSendMessage = vi.fn();

    render(<MiniApp state={state} messagesByChat={{ basic: [] }} onAcceptExplicit={vi.fn()} onSendMessage={onSendMessage} />);

    fireEvent.change(screen.getByRole("textbox", { name: "Message AI Assistant" }), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(onSendMessage).toHaveBeenCalledWith("basic", "hello");
    expect(screen.queryByRole("button", { name: "Return to Telegram" })).not.toBeInTheDocument();
  });

  it("switches bottom panels instead of using inert links", () => {
    render(<MiniApp state={state} messagesByChat={{ basic: [] }} onAcceptExplicit={vi.fn()} onSendMessage={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Profile" }));

    expect(screen.getByRole("button", { name: "Profile" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "Profile" })).toHaveTextContent("User 42");
    expect(screen.getByText("/support miniapp")).toBeInTheDocument();
  });

  it("keeps support as a secondary app section", () => {
    render(<MiniApp state={state} messagesByChat={{ basic: [] }} onAcceptExplicit={vi.fn()} onSendMessage={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Profile" }));
    fireEvent.click(screen.getByRole("button", { name: "Support" }));

    expect(screen.getByRole("button", { name: "Chats" })).toHaveAttribute("aria-selected", "false");
    expect(screen.getByRole("button", { name: "Support" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tabpanel", { name: "Support" })).toHaveTextContent("/support miniapp");
  });

  it("keeps chat before the persona guide in DOM focus order", () => {
    render(<MiniApp state={state} messagesByChat={{ basic: [] }} onAcceptExplicit={vi.fn()} onSendMessage={vi.fn()} />);

    const chatPanel = screen.getByRole("region", { name: "Selected chat" });
    const firstPersona = screen.getByRole("button", { name: "CH 001 AI Assistant" });

    expect(chatPanel.compareDocumentPosition(firstPersona)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  it("sends explicit locked selections to the consent contract", () => {
    render(<MiniApp state={state} messagesByChat={{ basic: [] }} onAcceptExplicit={vi.fn()} onSendMessage={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /CH 003 Flirt 18\+/ }));

    expect(screen.getByRole("status")).toHaveTextContent("18+ consent locked");
    fireEvent.click(screen.getByRole("button", { name: "Access" }));
    expect(screen.getByText("18+ explicit access")).toBeInTheDocument();
  });

  it("renders a per-persona chat and sends text without returning to Telegram", () => {
    const onSendMessage = vi.fn();

    render(
      <MiniApp
        state={state}
        messagesByChat={{
          basic: [
            { id: 1, role: "user", content: "Hello", created_at: 10 },
            { id: 2, role: "assistant", content: "Hi from AI Assistant", created_at: 11 },
          ],
        }}
        onAcceptExplicit={vi.fn()}
        onSendMessage={onSendMessage}
      />,
    );

    expect(screen.getByRole("log", { name: "AI Assistant chat history" })).toHaveTextContent("Hi from AI Assistant");
    fireEvent.change(screen.getByRole("textbox", { name: "Message AI Assistant" }), {
      target: { value: "New message" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(onSendMessage).toHaveBeenCalledWith("basic", "New message");
    expect(screen.queryByRole("button", { name: "Return to Telegram" })).not.toBeInTheDocument();
  });

  it("switches persona chat history and disables locked composers", () => {
    render(
      <MiniApp
        state={state}
        messagesByChat={{
          basic: [{ id: 1, role: "assistant", content: "Basic only", created_at: 10 }],
          coach: [],
        }}
        onAcceptExplicit={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /CH 002 Coach/ }));

    expect(screen.getByRole("log", { name: "Coach chat history" })).not.toHaveTextContent("Basic only");
    expect(screen.getByRole("textbox", { name: "Message Coach" })).toBeDisabled();
    expect(screen.getAllByText("Premium locked").length).toBeGreaterThan(0);
  });

  it("shows usage-limit send errors from the backend", async () => {
    const onSendMessage = vi.fn().mockRejectedValue(new Error("api_request_failed:/api/miniapp/chats/basic/messages:429"));

    render(<MiniApp state={state} messagesByChat={{ basic: [] }} onAcceptExplicit={vi.fn()} onSendMessage={onSendMessage} />);

    fireEvent.change(screen.getByRole("textbox", { name: "Message AI Assistant" }), {
      target: { value: "one more" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Message limit reached.");
  });

  it("shows loading state while a selected persona thread is loading", () => {
    render(
      <MiniApp
        state={state}
        messagesByChat={{ basic: [] }}
        loadingChatIds={{ basic: true }}
        onAcceptExplicit={vi.fn()}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Loading thread...");
    expect(screen.getByRole("textbox", { name: "Message AI Assistant" })).toBeDisabled();
  });

  it("shows chat load errors with retry for the selected persona", () => {
    const onRefreshChat = vi.fn();

    render(
      <MiniApp
        state={state}
        messagesByChat={{ basic: [] }}
        chatErrors={{ basic: "Could not load this thread." }}
        onAcceptExplicit={vi.fn()}
        onRefreshChat={onRefreshChat}
        onSendMessage={vi.fn()}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Could not load this thread.");
    fireEvent.click(screen.getByRole("button", { name: "Retry thread" }));

    expect(onRefreshChat).toHaveBeenCalledWith("basic");
  });
});
