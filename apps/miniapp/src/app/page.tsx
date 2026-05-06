"use client";

import { useEffect, useMemo, useState } from "react";

import { MiniApp } from "../components/mini-app";
import {
  acceptExplicitConsent,
  createBrowserTokenStore,
  loadChatMessages,
  loadMiniAppState,
  sendChatMessage,
  type ChatMessage,
  type MiniAppState,
} from "../lib/api";

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData?: string;
        ready?: () => void;
        expand?: () => void;
        close?: () => void;
      };
    };
  }
}

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const telegramInitDataWaitMs = 5000;
const telegramInitDataPollMs = 100;
const localDemoMessages: Record<string, ChatMessage[]> = {
  basic: [
    { id: 1, role: "assistant", content: "Local demo thread is ready.", created_at: 100 },
    { id: 2, role: "user", content: "Can I test the Mini App shell here?", created_at: 101 },
    { id: 3, role: "assistant", content: "Yes. This local demo does not call Telegram or Railway.", created_at: 102 },
  ],
};
const localDemoState: MiniAppState = {
  me: { user_id: "local-demo", session_expires_at: 0 },
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
    messages: { used: 3, limit: 30, reset_at: 0 },
    explicit_images: { used: 0, limit: 0, reset_at: 0 },
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
        last_message: localDemoMessages.basic[2],
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

export default function Page() {
  const [state, setState] = useState<MiniAppState | null>(null);
  const [messagesByChat, setMessagesByChat] = useState<Record<string, ChatMessage[]>>({});
  const [loadingChatIds, setLoadingChatIds] = useState<Record<string, boolean>>({});
  const [chatErrors, setChatErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string>("");
  const tokenStore = useMemo(() => createBrowserTokenStore(), []);

  useEffect(() => {
    let cancelled = false;
    if (shouldUseLocalDemo()) {
      setState(localDemoState);
      setMessagesByChat(localDemoMessages);
      return () => {
        cancelled = true;
      };
    }
    waitForTelegramInitData()
      .then((initData) => {
        if (cancelled) {
          return;
        }
        window.Telegram?.WebApp?.ready?.();
        window.Telegram?.WebApp?.expand?.();
        if (!apiBaseUrl || !initData) {
          setError(buildSessionUnavailableMessage(initData));
          return;
        }
        loadMiniAppState({ apiBaseUrl, initData, tokenStore })
          .then((nextState) => {
            if (!cancelled) {
              setState(nextState);
              const firstChatId = nextState.chats.items[0]?.id;
              if (firstChatId) {
                setLoadingChatIds((current) => ({ ...current, [firstChatId]: true }));
                setChatErrors((current) => ({ ...current, [firstChatId]: "" }));
                loadChatMessages({ apiBaseUrl, initData, tokenStore, characterId: firstChatId })
                  .then((messages) => {
                    if (!cancelled) {
                      setMessagesByChat((current) => ({ ...current, [firstChatId]: messages.items }));
                    }
                  })
                  .catch(() => {
                    if (!cancelled) {
                      setChatErrors((current) => ({ ...current, [firstChatId]: "Could not load this thread." }));
                    }
                  })
                  .finally(() => {
                    if (!cancelled) {
                      setLoadingChatIds((current) => ({ ...current, [firstChatId]: false }));
                    }
                  });
              }
            }
          })
          .catch(() => {
            if (!cancelled) {
              setError("Could not load Lina channel guide.");
            }
          });
      });
    return () => {
      cancelled = true;
    };
  }, [tokenStore]);

  async function handleAcceptExplicit() {
    const initData = window.Telegram?.WebApp?.initData ?? "";
    await acceptExplicitConsent({ apiBaseUrl, initData, tokenStore });
    setState(await loadMiniAppState({ apiBaseUrl, initData, tokenStore }));
  }

  async function handleSendMessage(characterId: string, text: string) {
    if (shouldUseLocalDemo()) {
      const createdAt = Date.now();
      const currentMessages = messagesByChat[characterId] ?? [];
      const nextId = currentMessages.reduce((maxId, message) => Math.max(maxId, message.id), 0) + 1;
      const userMessage: ChatMessage = { id: nextId, role: "user", content: text, created_at: createdAt };
      const assistantMessage: ChatMessage = {
        id: nextId + 1,
        role: "assistant",
        content: `Demo reply from ${state?.chats.items.find((item) => item.id === characterId)?.title ?? "Lina"}.`,
        created_at: createdAt + 1,
      };
      setMessagesByChat((current) => ({
        ...current,
        [characterId]: [...(current[characterId] ?? []), userMessage, assistantMessage],
      }));
      setState((current) =>
        current
          ? {
              ...current,
              usage: {
                ...current.usage,
                messages: { ...current.usage.messages, used: current.usage.messages.used + 1 },
              },
              chats: {
                items: current.chats.items.map((item) =>
                  item.id === characterId ? { ...item, last_message: assistantMessage } : item,
                ),
              },
            }
          : current,
      );
      return;
    }
    const initData = window.Telegram?.WebApp?.initData ?? "";
    const sent = await sendChatMessage({ apiBaseUrl, initData, tokenStore, characterId, text });
    setMessagesByChat((current) => ({
      ...current,
      [characterId]: [...(current[characterId] ?? []), sent.user_message, sent.assistant_message],
    }));
    setState((current) =>
      current
        ? {
            ...current,
            usage: {
              ...current.usage,
              messages: sent.usage.messages,
            },
            chats: {
              items: current.chats.items.map((item) =>
                item.id === characterId ? { ...item, last_message: sent.assistant_message } : item,
              ),
            },
          }
        : current,
    );
  }

  async function loadMessagesForChat(characterId: string, force = false) {
    if (!force && messagesByChat[characterId]) {
      return;
    }
    if (shouldUseLocalDemo()) {
      setMessagesByChat((current) => ({ ...current, [characterId]: current[characterId] ?? [] }));
      return;
    }
    const initData = window.Telegram?.WebApp?.initData ?? "";
    setLoadingChatIds((current) => ({ ...current, [characterId]: true }));
    setChatErrors((current) => ({ ...current, [characterId]: "" }));
    try {
      const messages = await loadChatMessages({ apiBaseUrl, initData, tokenStore, characterId });
      setMessagesByChat((current) => ({ ...current, [characterId]: messages.items }));
    } catch {
      setChatErrors((current) => ({ ...current, [characterId]: "Could not load this thread." }));
    } finally {
      setLoadingChatIds((current) => ({ ...current, [characterId]: false }));
    }
  }

  async function handleSelectChat(characterId: string) {
    await loadMessagesForChat(characterId);
  }

  async function handleRefreshChat(characterId: string) {
    await loadMessagesForChat(characterId, true);
  }

  if (error) {
    return (
      <main className="shell centered">
        <h1>Lina</h1>
        <p>{error}</p>
      </main>
    );
  }

  if (!state) {
    return (
      <main className="shell centered">
        <h1>Lina</h1>
        <p>Tuning channel guide...</p>
      </main>
    );
  }

  return (
    <MiniApp
      state={state}
      messagesByChat={messagesByChat}
      loadingChatIds={loadingChatIds}
      chatErrors={chatErrors}
      onAcceptExplicit={handleAcceptExplicit}
      onRefreshChat={handleRefreshChat}
      onSelectChat={handleSelectChat}
      onSendMessage={handleSendMessage}
    />
  );
}

function shouldUseLocalDemo(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  const host = window.location.hostname;
  const isLocal = host === "127.0.0.1" || host === "localhost";
  const demoParam = new URLSearchParams(window.location.search).get("demo");
  return isLocal && (demoParam === "1" || !apiBaseUrl);
}

async function waitForTelegramInitData(): Promise<string> {
  const startedAt = Date.now();
  while (Date.now() - startedAt < telegramInitDataWaitMs) {
    const initData = window.Telegram?.WebApp?.initData ?? "";
    if (initData) {
      return initData;
    }
    await new Promise((resolve) => window.setTimeout(resolve, telegramInitDataPollMs));
  }
  return window.Telegram?.WebApp?.initData ?? "";
}

function buildSessionUnavailableMessage(initData: string): string {
  const status = [
    `api:${apiBaseUrl ? "set" : "missing"}`,
    `tg:${window.Telegram ? "set" : "missing"}`,
    `webapp:${window.Telegram?.WebApp ? "set" : "missing"}`,
    `init:${initData.length}`,
  ].join(" ");
  return `Mini App session is unavailable. ${status}`;
}
