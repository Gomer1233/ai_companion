"use client";

import { useEffect, useMemo, useState } from "react";

import { MiniApp } from "../components/mini-app";
import { acceptExplicitConsent, createBrowserTokenStore, loadMiniAppState, type MiniAppState } from "../lib/api";

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData?: string;
        ready?: () => void;
        expand?: () => void;
      };
    };
  }
}

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const telegramInitDataWaitMs = 5000;
const telegramInitDataPollMs = 100;

export default function Page() {
  const [state, setState] = useState<MiniAppState | null>(null);
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

  return <MiniApp state={state} onAcceptExplicit={handleAcceptExplicit} />;
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
