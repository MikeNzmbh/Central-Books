/**
 * Tests for CompanionBanner component
 */
import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { CompanionBanner } from "./CompanionBanner";
import * as useCompanionSummaryModule from "./useCompanionSummary";
import { AuthProvider } from "../contexts/AuthContext";

// Mock the hooks
vi.mock("./useCompanionSummary", () => ({
    useCompanionSummary: vi.fn(),
    clearCompanionSummaryCache: vi.fn(),
}));

// Mock fetch for AuthContext
const mockFetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({ authenticated: true, user: { firstName: "Mike", lastName: "Test" } }),
});
vi.stubGlobal("fetch", mockFetch);

const mockSummary: useCompanionSummaryModule.CompanionSummary = {
    ai_companion_enabled: true,
    radar: {
        cash_reconciliation: { score: 85, open_issues: 1 },
        revenue_invoices: { score: 92, open_issues: 0 },
        expenses_receipts: { score: 78, open_issues: 2 },
        tax_compliance: { score: 88, open_issues: 1 },
    },
    coverage: {
        receipts: { coverage_percent: 88, total_items: 50, covered_items: 44 },
        invoices: { coverage_percent: 72, total_items: 36, covered_items: 26 },
        banking: { coverage_percent: 91, total_items: 110, covered_items: 100 },
        books: { coverage_percent: 80, total_items: 20, covered_items: 16 },
    },
    close_readiness: { status: "ready", blocking_reasons: [] },
    playbook: [],
    global: { open_issues_total: 4, open_issues_by_severity: { high: 0, medium: 2, low: 2 } },
};

const renderWithProvider = (ui: React.ReactElement) => {
    return render(<AuthProvider>{ui}</AuthProvider>);
};

describe("CompanionBanner", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("renders loading state", () => {
        vi.mocked(useCompanionSummaryModule.useCompanionSummary).mockReturnValue({
            summary: null,
            isLoading: true,
            error: null,
            refetch: vi.fn(),
        });

        renderWithProvider(<CompanionBanner surface="receipts" />);
        expect(screen.getByTestId("companion-banner")).toBeInTheDocument();
    });

    it("renders all_clear status for high score", async () => {
        vi.mocked(useCompanionSummaryModule.useCompanionSummary).mockReturnValue({
            summary: mockSummary,
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        });

        renderWithProvider(<CompanionBanner surface="invoices" />);

        await waitFor(() => {
            expect(screen.getByText("On track")).toBeInTheDocument();
        });
    });

    it("renders watchlist status for medium score", async () => {
        const watchlistSummary: useCompanionSummaryModule.CompanionSummary = {
            ...mockSummary,
            radar: {
                ...mockSummary.radar!,
                expenses_receipts: { score: 65, open_issues: 3 },
            },
        };

        vi.mocked(useCompanionSummaryModule.useCompanionSummary).mockReturnValue({
            summary: watchlistSummary,
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        });

        renderWithProvider(<CompanionBanner surface="receipts" />);

        await waitFor(() => {
            expect(screen.getByText("Needs attention")).toBeInTheDocument();
        });
    });

    it("renders fire_drill status for low score", async () => {
        const fireDrillSummary: useCompanionSummaryModule.CompanionSummary = {
            ...mockSummary,
            radar: {
                ...mockSummary.radar!,
                cash_reconciliation: { score: 35, open_issues: 5 },
            },
        };

        vi.mocked(useCompanionSummaryModule.useCompanionSummary).mockReturnValue({
            summary: fireDrillSummary,
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        });

        renderWithProvider(<CompanionBanner surface="bank" />);

        await waitFor(() => {
            expect(screen.getByText("Action required")).toBeInTheDocument();
        });
    });

    it("renders fallback when summary fetch fails", async () => {
        vi.mocked(useCompanionSummaryModule.useCompanionSummary).mockReturnValue({
            summary: null,
            isLoading: false,
            error: new Error("Network error"),
            refetch: vi.fn(),
        });

        renderWithProvider(<CompanionBanner surface="books" />);

        await waitFor(() => {
            expect(screen.getByText("Companion temporarily unavailable")).toBeInTheDocument();
            expect(screen.getByText(/temporarily unavailable for this area/i)).toBeInTheDocument();
        });
    });

    it("shows coverage percentage in subtitle when no playbook step", async () => {
        vi.mocked(useCompanionSummaryModule.useCompanionSummary).mockReturnValue({
            summary: mockSummary,
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        });

        renderWithProvider(<CompanionBanner surface="receipts" />);

        await waitFor(() => {
            expect(screen.getByText(/88%/)).toBeInTheDocument();
        });
    });

    it("shows playbook step when available", async () => {
        const summaryWithPlaybook: useCompanionSummaryModule.CompanionSummary = {
            ...mockSummary,
            playbook: [
                { label: "Review 5 unmatched receipts", surface: "receipts", severity: "medium", url: "/receipts/", issue_id: 1 },
            ],
        };

        vi.mocked(useCompanionSummaryModule.useCompanionSummary).mockReturnValue({
            summary: summaryWithPlaybook,
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        });

        renderWithProvider(<CompanionBanner surface="receipts" />);

        await waitFor(() => {
            expect(screen.getByText(/Top next step: Review 5 unmatched receipts/)).toBeInTheDocument();
        });
    });
});

describe("Greeting logic", () => {
    it("shows morning greeting before noon", () => {
        const mockDate = new Date("2024-01-15T09:00:00");
        vi.useFakeTimers();
        vi.setSystemTime(mockDate);

        vi.mocked(useCompanionSummaryModule.useCompanionSummary).mockReturnValue({
            summary: mockSummary,
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        });

        renderWithProvider(<CompanionBanner surface="invoices" />);

        expect(screen.getByText(/Good morning/)).toBeInTheDocument();

        vi.useRealTimers();
    });

    it("shows afternoon greeting in afternoon", () => {
        const mockDate = new Date("2024-01-15T14:00:00");
        vi.useFakeTimers();
        vi.setSystemTime(mockDate);

        vi.mocked(useCompanionSummaryModule.useCompanionSummary).mockReturnValue({
            summary: mockSummary,
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        });

        renderWithProvider(<CompanionBanner surface="invoices" />);

        expect(screen.getByText(/Good afternoon/)).toBeInTheDocument();

        vi.useRealTimers();
    });

    it("shows evening greeting after 6pm", () => {
        const mockDate = new Date("2024-01-15T20:00:00");
        vi.useFakeTimers();
        vi.setSystemTime(mockDate);

        vi.mocked(useCompanionSummaryModule.useCompanionSummary).mockReturnValue({
            summary: mockSummary,
            isLoading: false,
            error: null,
            refetch: vi.fn(),
        });

        renderWithProvider(<CompanionBanner surface="invoices" />);

        expect(screen.getByText(/Good evening/)).toBeInTheDocument();

        vi.useRealTimers();
    });
});
