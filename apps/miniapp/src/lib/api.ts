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
  access: {
    allowed: boolean;
    reasons: string[];
  };
};

export type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: number;
};

export type ChatSummary = CharacterItem & {
  last_message: ChatMessage | null;
  unread_count: number;
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
  chats: {
    items: ChatSummary[];
  };
};

type ApiOptions = {
  apiBaseUrl: string;
  initData: string;
  tokenStore: TokenStore;
  fetchImpl?: typeof fetch;
  telegramInitMaxAgeSec?: number;
};

type ChatApiOptions = ApiOptions & {
  characterId: string;
};

type SendChatApiOptions = ChatApiOptions & {
  text: string;
};

export type ChatMessagesResponse = {
  items: ChatMessage[];
};

export type SendChatMessageResponse = {
  user_message: ChatMessage;
  assistant_message: ChatMessage;
  usage: {
    messages: UsageBucket;
  };
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
  const token = sessionTokenFromResponse(data);
  options.tokenStore.set(token);
  return token;
}

export async function loadMiniAppState(options: ApiOptions): Promise<MiniAppState> {
  const me = await authorizedJson<MiniAppState["me"]>(options, "/api/me");
  const characters = await authorizedJson<MiniAppState["characters"]>(options, "/api/characters");
  const entitlements = await authorizedJson<Entitlements>(options, "/api/entitlements");
  const usage = await authorizedJson<MiniAppState["usage"]>(options, "/api/usage");
  const chats = await authorizedJson<MiniAppState["chats"]>(options, "/api/miniapp/chats");
  return { me, characters, entitlements, usage, chats };
}

export async function acceptExplicitConsent(options: ApiOptions): Promise<Entitlements> {
  return authorizedJson<Entitlements>(options, "/api/consent/explicit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ accepted: true }),
  });
}

export async function loadChatMessages(options: ChatApiOptions): Promise<ChatMessagesResponse> {
  return authorizedJson<ChatMessagesResponse>(options, `/api/miniapp/chats/${options.characterId}/messages`);
}

export async function sendChatMessage(options: SendChatApiOptions): Promise<SendChatMessageResponse> {
  return authorizedJson<SendChatMessageResponse>(options, `/api/miniapp/chats/${options.characterId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: options.text }),
  });
}

async function authorizedJson<T>(options: ApiOptions, path: string, init: RequestInit = {}): Promise<T> {
  const fetchImpl = options.fetchImpl ?? fetch;
  const firstToken = options.tokenStore.get() ?? (await exchangeTelegramSession(options));
  let response = await fetchImpl(joinUrl(options.apiBaseUrl, path), withAuth(init, firstToken.accessToken));
  if (response.status === 401) {
    options.tokenStore.clear();
    if (!isTelegramInitDataFresh(options.initData, options.telegramInitMaxAgeSec ?? defaultTelegramInitMaxAgeSec())) {
      throw new Error("session_reauth_unavailable");
    }
    const refreshed = await exchangeTelegramSession(options);
    response = await fetchImpl(joinUrl(options.apiBaseUrl, path), withAuth(init, refreshed.accessToken));
  }
  if (!response.ok) {
    throw new Error(`api_request_failed:${path}:${response.status}`);
  }
  return (await response.json()) as T;
}

function sessionTokenFromResponse(data: SessionResponse): SessionToken {
  return {
    accessToken: data.access_token,
    expiresAt: data.expires_at,
  };
}

function withAuth(init: RequestInit, accessToken: string): RequestInit {
  const headers = { ...(init.headers as Record<string, string> | undefined), Authorization: `Bearer ${accessToken}` };
  return { ...init, headers };
}

function joinUrl(baseUrl: string, path: string): string {
  return `${baseUrl.replace(/\/$/, "")}${path}`;
}

function isTelegramInitDataFresh(initData: string, maxAgeSec: number): boolean {
  const authDateRaw = new URLSearchParams(initData).get("auth_date");
  if (!authDateRaw) {
    return false;
  }
  const authDate = Number(authDateRaw);
  if (!Number.isFinite(authDate)) {
    return false;
  }
  return authDate >= Math.floor(Date.now() / 1000) - maxAgeSec;
}

function defaultTelegramInitMaxAgeSec(): number {
  const raw = process.env.NEXT_PUBLIC_TELEGRAM_INIT_MAX_AGE_SEC;
  const parsed = raw ? Number(raw) : NaN;
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 7200;
}
