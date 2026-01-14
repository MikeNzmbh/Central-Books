import { buildApiUrl } from "./base";

let cachedToken: string | null = null;
let inflight: Promise<string> | null = null;

const parseCookies = (input: string): Record<string, string> => {
  return input
    .split(";")
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .reduce<Record<string, string>>((acc, pair) => {
      const idx = pair.indexOf("=");
      if (idx === -1) return acc;
      const key = decodeURIComponent(pair.slice(0, idx));
      const value = decodeURIComponent(pair.slice(idx + 1));
      acc[key] = value;
      return acc;
    }, {});
};

export const getCsrfToken = (): string => {
  if (typeof document === "undefined") return cachedToken || "";
  const cookies = parseCookies(document.cookie || "");
  if (cookies.csrftoken) return cookies.csrftoken;
  return cachedToken || "";
};

export const ensureCsrfToken = async (): Promise<string> => {
  const existing = getCsrfToken();
  if (existing) {
    cachedToken = existing;
    return existing;
  }

  if (cachedToken) return cachedToken;
  if (inflight) return inflight;

  inflight = fetch(buildApiUrl("/api/auth/config"), { credentials: "include" })
    .then(async (res) => {
      if (!res.ok) return "";
      const data = await res.json().catch(() => ({}));
      return typeof data?.csrfToken === "string" ? data.csrfToken : "";
    })
    .finally(() => {
      inflight = null;
    });

  const token = await inflight;
  cachedToken = token || null;
  return token;
};
