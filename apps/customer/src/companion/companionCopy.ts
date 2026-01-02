/**
 * Companion Copy System
 * 
 * Customer-safe terminology for AI Companion UI.
 * Never show internal accounting jargon to customers.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Term Mapping: Internal → Customer-safe
// ─────────────────────────────────────────────────────────────────────────────

const TERM_MAP: Record<string, string> = {
    "journal entry": "change to your books",
    "journal entries": "changes to your books",
    "proposal": "AI suggestion",
    "proposals": "AI suggestions",
    "shadow ledger": "AI suggestions",
    "shadow event": "suggested change",
    "shadow events": "suggested changes",
    "canonical ledger": "your books",
    "categorization": "category",
    "reclassification": "category correction",
    "reconciliation": "matching",
    "anomaly": "issue",
    "anomalies": "issues",
    "autopilot": "auto-apply",
    "shadow mode": "learning mode",
    "suggest mode": "review mode",
};

/**
 * Replace internal terms with customer-safe equivalents
 */
export function toCustomerCopy(text: string | null | undefined): string {
    if (!text) return "";
    let result = text;
    for (const [internal, customer] of Object.entries(TERM_MAP)) {
        const regex = new RegExp(`\\b${internal}\\b`, "gi");
        result = result.replace(regex, customer);
    }
    // Avoid surfacing debit/credit terminology in customer copy.
    result = result.replace(/\bdebit(?! card)\b/gi, "increase");
    result = result.replace(/\bcredit(?! card)\b/gi, "decrease");
    return result;
}

// ─────────────────────────────────────────────────────────────────────────────
// Severity Labels
// ─────────────────────────────────────────────────────────────────────────────

export type SeverityLevel = "high" | "medium" | "low";

export const SEVERITY_LABELS: Record<SeverityLevel, string> = {
    high: "Needs attention",
    medium: "Review recommended",
    low: "Ready to apply",
};

export const SEVERITY_COLORS: Record<SeverityLevel, { bg: string; text: string; border: string }> = {
    high: { bg: "bg-rose-50", text: "text-rose-700", border: "border-rose-200" },
    medium: { bg: "bg-slate-100", text: "text-slate-700", border: "border-slate-200" },
    low: { bg: "bg-emerald-50", text: "text-emerald-700", border: "border-emerald-200" },
};

export function getSeverityLabel(severity: string): string {
    return SEVERITY_LABELS[severity as SeverityLevel] || severity;
}

export function getSeverityColors(severity: string) {
    return SEVERITY_COLORS[severity as SeverityLevel] || SEVERITY_COLORS.low;
}

// ─────────────────────────────────────────────────────────────────────────────
// Action Labels & Templates
// ─────────────────────────────────────────────────────────────────────────────

export const ACTION_LABELS = {
    apply: "Apply this change",
    dismiss: "Dismiss",
    review: "Open review",
    snooze: "Remind me later",
    undo: "Undo",
} as const;

export const CONFIRMATION_TEMPLATES = {
    applySuccess: "Done! We've applied this change to your books.",
    applySuccessWithUndo: "Done! We've applied this change. Undo available for 30 seconds.",
    dismissSuccess: "Got it. We won't suggest this again.",
    snoozeSuccess: (date: string) => `We'll remind you about this on ${date}.`,
    applyError: "Something went wrong. Please try again.",
};

// ─────────────────────────────────────────────────────────────────────────────
// Preview Templates (What Will Change)
// ─────────────────────────────────────────────────────────────────────────────

export interface ChangePreview {
    action: string;
    details: string[];
}

export function formatChangePreview(action: string, metadata?: Record<string, any>): ChangePreview {
    const details: string[] = [];

    // Build human-readable details based on action type
    if (metadata?.amount) {
        const formatted = new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: metadata.currency || "USD",
        }).format(metadata.amount);
        details.push(`Amount: ${formatted}`);
    }

    if (metadata?.category) {
        details.push(`Category: ${metadata.category}`);
    }

    if (metadata?.customer || metadata?.supplier) {
        details.push(`${metadata.customer ? "Customer" : "Supplier"}: ${metadata.customer || metadata.supplier}`);
    }

    if (metadata?.date) {
        details.push(`Date: ${new Date(metadata.date).toLocaleDateString()}`);
    }

    return {
        action: toCustomerCopy(action),
        details,
    };
}

// ─────────────────────────────────────────────────────────────────────────────
// Panel Titles
// ─────────────────────────────────────────────────────────────────────────────

export const PANEL_TITLES = {
    suggestions: "AI Suggestions",
    issues: "Open Issues",
    close: "Close Assistant",
} as const;

export type PanelType = keyof typeof PANEL_TITLES;

export function getPanelTitle(panel: string): string {
    return PANEL_TITLES[panel as PanelType] || panel;
}

// ─────────────────────────────────────────────────────────────────────────────
// Surface Labels
// ─────────────────────────────────────────────────────────────────────────────

export const SURFACE_LABELS: Record<string, string> = {
    bank: "Bank",
    invoices: "Invoices",
    expenses: "Expenses",
    receipts: "Receipts",
    tax: "Tax",
    books: "Books",
};

export function getSurfaceLabel(surface: string): string {
    return SURFACE_LABELS[surface] || surface;
}

// ─────────────────────────────────────────────────────────────────────────────
// Empty States
// ─────────────────────────────────────────────────────────────────────────────

export const EMPTY_STATES = {
    suggestions: "No suggestions to review. Check back later.",
    issues: "All clear! No open issues.",
    close: "No items to review for this period.",
};

export function getEmptyState(panel: string): string {
    return EMPTY_STATES[panel as keyof typeof EMPTY_STATES] || "Nothing to show.";
}
