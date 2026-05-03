export type SessionResponse = {
  access_token: string;
  token_type: "Bearer";
  expires_at: number;
};

export type SessionToken = {
  accessToken: string;
  expiresAt: number;
};

export type TokenStore = {
  get(): SessionToken | null;
  set(token: SessionToken): void;
  clear(): void;
};

export type CharacterItem = {
  id: string;
  mode: string;
  title: string;
  category: string;
  default_tier: string;
};

export type Entitlements = {
  tier: string;
  tier_expires_at: number | null;
  has_premium: boolean;
  explicit_consent: boolean;
  consent_required: boolean;
  blocked_reasons: string[];
};

export type UsageBucket = {
  used: number;
  limit: number;
  reset_at: number;
};

export type MiniAppState = {
  me: {
    user_id: string;
    session_expires_at: number;
  };
  characters: {
    items: CharacterItem[];
  };
  entitlements: Entitlements;
  usage: {
    history_limit: number;
    image_cooldown_sec: number;
    messages: UsageBucket;
    explicit_images: UsageBucket;
  };
};

type ApiOptions = {
  apiBaseUrl: string;
  initData: string;
  tokenStore: TokenStore;
  fetchImpl?: typeof fetch;
};

export function createMemoryTokenStore(): TokenStore {
  let current: SessionToken | null = null;
  return {
    get: () => current,
    set: (token) => {
      current = token;
    },
    clear: () => {
      current = null;
    },
  };
}

export function createBrowserTokenStore(key = "lina-miniapp-session"): TokenStore {
  if (typeof window === "undefined") {
    return createMemoryTokenStore();
  }
  return {
    get: () => {
      const raw = window.sessionStorage.getItem(key);
      return raw ? (JSON.parse(raw) as SessionToken) : null;
    },
    set: (token) => {
      window.sessionStorage.setItem(key, JSON.stringify(token));
    },
    clear: () => {
      window.sessionStorage.removeItem(key);
    },
  };
}

export async function exchangeTelegramSession(options: ApiOptions): Promise<SessionToken> {
  const response = await (options.fetchImpl ?? fetch)(joinUrl(options.apiBaseUrl, "/api/session/telegram"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ init_data: options.initData }),
  });
  if (!response.ok) {
    throw new Error(`session_exchange_failed:${response.status}`);
  }
  const data = (await response.json()) as SessionResponse;
  const token = { accessToken: data.access_token, expiresAt: data.expires_at };
  options.tokenStore.set(token);
  return token;
}

export async function loadMiniAppState(options: ApiOptions): Promise<MiniAppState> {
  const me = await authorizedJson<MiniAppState["me"]>(options, "/api/me");
  const characters = await authorizedJson<MiniAppState["characters"]>(options, "/api/characters");
  const entitlements = await authorizedJson<Entitlements>(options, "/api/entitlements");
  const usage = await authorizedJson<MiniAppState["usage"]>(options, "/api/usage");
  return { me, characters, entitlements, usage };
}

export async function acceptExplicitConsent(options: ApiOptions): Promise<Entitlements> {
  return authorizedJson<Entitlements>(options, "/api/consent/explicit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ accepted: true }),
  });
}

async function authorizedJson<T>(options: ApiOptions, path: string, init: RequestInit = {}): Promise<T> {
  const fetchImpl = options.fetchImpl ?? fetch;
  const firstToken = options.tokenStore.get() ?? (await exchangeTelegramSession(options));
  let response = await fetchImpl(joinUrl(options.apiBaseUrl, path), withAuth(init, firstToken.accessToken));
  if (response.status === 401) {
    options.tokenStore.clear();
    const refreshed = await exchangeTelegramSession(options);
    response = await fetchImpl(joinUrl(options.apiBaseUrl, path), withAuth(init, refreshed.accessToken));
  }
  if (!response.ok) {
    throw new Error(`api_request_failed:${path}:${response.status}`);
  }
  return (await response.json()) as T;
}

function withAuth(init: RequestInit, accessToken: string): RequestInit {
  const headers = { ...(init.headers as Record<string, string> | undefined), Authorization: `Bearer ${accessToken}` };
  return { ...init, headers };
}

function joinUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/$/, "")}${path}`;
}
