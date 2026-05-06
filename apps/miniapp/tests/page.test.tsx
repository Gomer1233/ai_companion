import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MiniAppState } from "../src/lib/api";

const initialState: MiniAppState = {
  me: { user_id: "42", session_expires_at: 999 },
  characters: {
    items: [
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
    tier: "trial",
    tier_expires_at: 99999,
    has_premium: false,
    explicit_consent: false,
    consent_required: true,
    blocked_reasons: [],
  },
  usage: {
    history_limit: 12,
    image_cooldown_sec: 300,
    messages: { used: 0, limit: 100, reset_at: 1234 },
    explicit_images: { used: 0, limit: 3, reset_at: 1234 },
  },
  chats: {
    items: [
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

const updatedState: MiniAppState = {
  ...initialState,
  characters: {
    items: initialState.characters.items.map((item) => ({ ...item, access: { allowed: true, reasons: [] } })),
  },
  chats: {
    items: initialState.chats.items.map((item) => ({ ...item, access: { allowed: true, reasons: [] } })),
  },
  entitlements: { ...initialState.entitlements, explicit_consent: true, consent_required: false },
};

const loadMiniAppState = vi.fn();
const acceptExplicitConsent = vi.fn();
const loadChatMessages = vi.fn();
const sendChatMessage = vi.fn();

vi.mock("../src/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../src/lib/api")>();
  return {
    ...actual,
    createBrowserTokenStore: () => actual.createMemoryTokenStore(),
    loadMiniAppState,
    loadChatMessages,
    sendChatMessage,
    acceptExplicitConsent,
  };
});

describe("Mini App page", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://railway.example");
    loadMiniAppState.mockReset();
    acceptExplicitConsent.mockReset();
    loadChatMessages.mockReset().mockResolvedValue({ items: [] });
    sendChatMessage.mockReset();
    window.Telegram = { WebApp: { initData: "tg-init-data", ready: vi.fn(), expand: vi.fn() } };
  });

  it("reloads full state after explicit consent so channel access is not stale", async () => {
    loadMiniAppState.mockResolvedValueOnce(initialState).mockResolvedValueOnce(updatedState);
    acceptExplicitConsent.mockResolvedValueOnce(updatedState.entitlements);
    const { default: Page } = await import("../src/app/page");

    render(<Page />);
    expect((await screen.findAllByText("18+ LOCKED")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Access" }));
    fireEvent.click(screen.getByRole("button", { name: "I am 18+ and accept" }));

    await waitFor(() => expect(loadMiniAppState).toHaveBeenCalledTimes(2));
    expect(screen.queryByText("18+ LOCKED")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Chats" }));
    expect(screen.getAllByText("18+ OPEN").length).toBeGreaterThan(0);
  });

  it("waits for Telegram initData before declaring the session unavailable", async () => {
    window.Telegram = { WebApp: { initData: "", ready: vi.fn(), expand: vi.fn() } };
    loadMiniAppState.mockResolvedValueOnce(initialState);
    const { default: Page } = await import("../src/app/page");

    render(<Page />);
    expect(screen.getByText("Tuning channel guide...")).toBeInTheDocument();

    window.setTimeout(() => {
      window.Telegram!.WebApp!.initData = "late-tg-init-data";
    }, 25);

    await waitFor(() =>
      expect(loadMiniAppState).toHaveBeenCalledWith(expect.objectContaining({ initData: "late-tg-init-data" })),
    );
    expect((await screen.findAllByText("18+ LOCKED")).length).toBeGreaterThan(0);
  });

  it("surfaces initial thread loading state until messages arrive", async () => {
    const pendingMessages = deferred<{ items: [] }>();
    loadMiniAppState.mockResolvedValueOnce(updatedState);
    loadChatMessages.mockReturnValueOnce(pendingMessages.promise);
    const { default: Page } = await import("../src/app/page");

    render(<Page />);

    expect(await screen.findByRole("status")).toHaveTextContent("Loading thread...");

    pendingMessages.resolve({ items: [] });

    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
    expect(screen.getByText("Start this persona thread.")).toBeInTheDocument();
  });
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}
