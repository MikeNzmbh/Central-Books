/**
 * CSRF Token Utility
 * 
 * Extracts CSRF token from cookies for use in POST/PATCH/DELETE requests.
 */

import { parseCookies } from "./cookies";

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

    // Fallback to hidden input field (Django templates)
    const hiddenInput = document.querySelector<HTMLInputElement>(
        "[name=csrfmiddlewaretoken]"
    );
    if (hiddenInput?.value) {
        return hiddenInput.value;
    }

    return "";
}

export default getCsrfToken;
