import { describe, expect, it, vi } from "vitest";

import {
  acceptExplicitConsent,
  createMemoryTokenStore,
  loadChatMessages,
  loadMiniAppState,
  sendChatMessage,
} from "../src/lib/api";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("Mini App API client", () => {
  it("loads backend-owned app state and silently re-auths on 401", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "old-token", expiresAt: 111 });
    vi.setSystemTime(new Date(1_100_000));
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ detail: "invalid_token" }, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({ access_token: "new-token", token_type: "Bearer", expires_at: 999 }))
      .mockResolvedValueOnce(jsonResponse({ user_id: "42", session_expires_at: 999 }))
      .mockResolvedValueOnce(
        jsonResponse({
          items: [
            {
              id: "coach",
              mode: "coach_premium",
              title: "Coach",
              category: "practice",
              default_tier: "premium",
              access: { allowed: false, reasons: ["premium_required"] },
            },
          ],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          tier: "free",
          tier_expires_at: null,
          has_premium: false,
          explicit_consent: false,
          consent_required: true,
          blocked_reasons: [],
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          history_limit: 12,
          image_cooldown_sec: 300,
          messages: { used: 2, limit: 30, reset_at: 1234 },
          explicit_images: { used: 0, limit: 0, reset_at: 1234 },
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          items: [
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
          ],
        }),
      );

    const state = await loadMiniAppState({
      apiBaseUrl: "https://railway.example",
      initData: "auth_date=1000&user={}&hash=test",
      tokenStore,
      fetchImpl,
      telegramInitMaxAgeSec: 300,
    });

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "https://railway.example/api/me",
      expect.objectContaining({ headers: { Authorization: "Bearer old-token" } }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "https://railway.example/api/session/telegram",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ init_data: "auth_date=1000&user={}&hash=test" }),
      }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      3,
      "https://railway.example/api/me",
      expect.objectContaining({ headers: { Authorization: "Bearer new-token" } }),
    );
    expect(tokenStore.get()).toEqual({ accessToken: "new-token", expiresAt: 999 });
    expect(state.me.user_id).toBe("42");
    expect(state.characters.items[0].mode).toBe("coach_premium");
    expect(state.chats.items[0].id).toBe("coach");
    expect(state.entitlements.consent_required).toBe(true);
    vi.useRealTimers();
  });

  it("does not retry session exchange with stale Telegram init data on 401", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "old-token", expiresAt: 111 });
    vi.setSystemTime(new Date(1_400_000));
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValueOnce(jsonResponse({ detail: "invalid_token" }, { status: 401 }));

    await expect(
      loadMiniAppState({
        apiBaseUrl: "https://railway.example",
        initData: "auth_date=1000&user={}&hash=test",
        tokenStore,
        fetchImpl,
        telegramInitMaxAgeSec: 300,
      }),
    ).rejects.toThrow("session_reauth_unavailable");

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    expect(fetchImpl).not.toHaveBeenCalledWith(
      "https://railway.example/api/session/telegram",
      expect.anything(),
    );
    expect(tokenStore.get()).toBeNull();
    vi.useRealTimers();
  });

  it("accepts explicit consent through the backend endpoint", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "session-token", expiresAt: 999 });
    const fetchImpl = vi.fn<typeof fetch>().mockResolvedValueOnce(
      jsonResponse({
        tier: "premium",
        tier_expires_at: 99999,
        has_premium: true,
        explicit_consent: true,
        consent_required: false,
        blocked_reasons: [],
      }),
    );

    const result = await acceptExplicitConsent({
      apiBaseUrl: "https://railway.example",
      initData: "tg-init-data",
      tokenStore,
      fetchImpl,
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "https://railway.example/api/consent/explicit",
      expect.objectContaining({
        method: "POST",
        headers: { Authorization: "Bearer session-token", "Content-Type": "application/json" },
        body: JSON.stringify({ accepted: true }),
      }),
    );
    expect(result.explicit_consent).toBe(true);
  });

  it("loads and sends per-persona Mini App chat messages", async () => {
    const tokenStore = createMemoryTokenStore();
    tokenStore.set({ accessToken: "session-token", expiresAt: 999 });
    const fetchImpl = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ items: [{ id: 1, role: "user", content: "hi", created_at: 10 }] }))
      .mockResolvedValueOnce(
        jsonResponse({
          user_message: { id: 2, role: "user", content: "hello", created_at: 11 },
          assistant_message: { id: 3, role: "assistant", content: "reply", created_at: 12 },
          usage: { messages: { used: 1, limit: 30, reset_at: 1234 } },
        }),
      );

    const messages = await loadChatMessages({
      apiBaseUrl: "https://railway.example",
      initData: "tg-init-data",
      tokenStore,
      fetchImpl,
      characterId: "basic",
    });
    const sent = await sendChatMessage({
      apiBaseUrl: "https://railway.example",
      initData: "tg-init-data",
      tokenStore,
      fetchImpl,
      characterId: "basic",
      text: "hello",
    });

    expect(fetchImpl).toHaveBeenNthCalledWith(
      1,
      "https://railway.example/api/miniapp/chats/basic/messages",
      expect.objectContaining({ headers: { Authorization: "Bearer session-token" } }),
    );
    expect(fetchImpl).toHaveBeenNthCalledWith(
      2,
      "https://railway.example/api/miniapp/chats/basic/messages",
      expect.objectContaining({
        method: "POST",
        headers: { Authorization: "Bearer session-token", "Content-Type": "application/json" },
        body: JSON.stringify({ text: "hello" }),
      }),
    );
    expect(messages.items[0].content).toBe("hi");
    expect(sent.assistant_message.content).toBe("reply");
  });

});
