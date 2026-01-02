let installed = false;

const rawBase = import.meta.env.VITE_API_BASE_URL || "";
export const API_BASE_URL = rawBase.replace(/\/+$/, "");

export const backendUrl = (path: string): string => {
  if (!API_BASE_URL) return path;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (path.startsWith("/")) return `${API_BASE_URL}${path}`;
  return `${API_BASE_URL}/${path}`;
};

const isApiPath = (path: string): boolean => path === "/api" || path.startsWith("/api/");

export const createApiFetch = (baseFetch: typeof fetch) => {
  return (input: RequestInfo | URL, init?: RequestInit) => {
    if (typeof input === "string" && isApiPath(input)) {
      const nextInit: RequestInit = { ...init };
      if (!nextInit.credentials || nextInit.credentials === "same-origin") {
        nextInit.credentials = "include";
      }
      return baseFetch(backendUrl(input), nextInit);
    }
    return baseFetch(input, init);
  };
};

export const apiFetch = createApiFetch(
  typeof window !== "undefined" ? window.fetch.bind(window) : fetch
);

export const installApiFetch = (): void => {
  if (installed || typeof window === "undefined") return;
  const baseFetch = window.fetch.bind(window);
  window.fetch = createApiFetch(baseFetch);
  installed = true;
};
