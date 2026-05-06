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

export default function Page() {
  const [state, setState] = useState<MiniAppState | null>(null);
  const [messagesByChat, setMessagesByChat] = useState<Record<string, ChatMessage[]>>({});
  const [loadingChatIds, setLoadingChatIds] = useState<Record<string, boolean>>({});
  const [chatErrors, setChatErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string>("");
  const tokenStore = useMemo(() => createBrowserTokenStore(), []);

  useEffect(() => {
    let cancelled = false;
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
