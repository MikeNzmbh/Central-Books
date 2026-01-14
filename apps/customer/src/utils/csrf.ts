/**
 * CSRF Token Utility
 * 
 * Extracts CSRF token from cookies for use in POST/PATCH/DELETE requests.
 */

import { backendUrl } from "./apiClient";
import { parseCookies } from "./cookies";

let cachedToken: string | null = null;
let inflight: Promise<string> | null = null;

/**
 * Get the CSRF token from cookies or hidden form field.
 * Returns empty string if not found.
 */
export function getCsrfToken(): string {
    // Try cookies first
    const cookies = parseCookies(document.cookie || "");
    if (cookies.csrftoken) {
        return cookies.csrftoken;
    }

    // Fallback to hidden input field (server-rendered forms)
    const hiddenInput = document.querySelector<HTMLInputElement>(
        "[name=csrfmiddlewaretoken]"
    );
    if (hiddenInput?.value) {
        return hiddenInput.value;
    }

    return cachedToken || "";
}

export default getCsrfToken;

/**
 * Ensure a CSRF token is available even when the cookie is HttpOnly (production).
 *
 * Strategy:
 * - If token is readable from cookies/DOM, use it.
 * - Else fetch `/api/auth/config` (sets CSRF cookie server-side and returns token).
 * - Cache token in-memory for subsequent requests.
 */
export async function ensureCsrfToken(): Promise<string> {
    const existing = getCsrfToken();
    if (existing) {
        cachedToken = existing;
        return existing;
    }

    if (cachedToken) {
        return cachedToken;
    }

    if (inflight) {
        return inflight;
    }

    inflight = fetch(backendUrl("/api/auth/config"), { credentials: "include" })
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
}
