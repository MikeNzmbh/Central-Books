const rawBase = import.meta.env.VITE_API_BASE_URL || "";

export const API_BASE_URL = rawBase.replace(/\/+$/, "");

export const buildApiUrl = (path: string): string => {
  if (!API_BASE_URL) return path;
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  if (path.startsWith("/")) return `${API_BASE_URL}${path}`;
  return `${API_BASE_URL}/${path}`;
};
