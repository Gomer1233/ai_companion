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

export default function Page() {
  const [state, setState] = useState<MiniAppState | null>(null);
  const [error, setError] = useState<string>("");
  const tokenStore = useMemo(() => createBrowserTokenStore(), []);

  useEffect(() => {
    window.Telegram?.WebApp?.ready?.();
    window.Telegram?.WebApp?.expand?.();
    const initData = window.Telegram?.WebApp?.initData ?? "";
    if (!apiBaseUrl || !initData) {
      setError("Mini App session is unavailable.");
      return;
    }
    loadMiniAppState({ apiBaseUrl, initData, tokenStore })
      .then(setState)
      .catch(() => setError("Could not load Lina channel guide."));
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
