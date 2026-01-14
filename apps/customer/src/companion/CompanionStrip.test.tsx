import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";

import CompanionStrip from "./CompanionStrip";
import { fetchCompanionOverview, markCompanionContextSeen } from "./api";
import { resetCompanionContextCacheForTests } from "./useCompanionContext";
import * as useCompanionSummaryModule from "./useCompanionSummary";

vi.mock("./api", () => ({
  fetchCompanionOverview: vi.fn(),
  markCompanionContextSeen: vi.fn(),
}));

vi.mock("./useCompanionSummary", () => ({
  useCompanionSummary: vi.fn(),
  clearCompanionSummaryCache: vi.fn(),
}));

// Default mock summary for tests - all high scores for all-clear tests
const mockSummary: useCompanionSummaryModule.CompanionSummary = {
  ai_companion_enabled: true,
  radar: {
    cash_reconciliation: { score: 95, open_issues: 0 },
    revenue_invoices: { score: 95, open_issues: 0 },
    expenses_receipts: { score: 95, open_issues: 0 },
    tax_compliance: { score: 95, open_issues: 0 },
  },
  coverage: {
    receipts: { coverage_percent: 95, total_items: 50, covered_items: 48 },
    invoices: { coverage_percent: 95, total_items: 36, covered_items: 34 },
    banking: { coverage_percent: 95, total_items: 110, covered_items: 105 },
    books: { coverage_percent: 95, total_items: 20, covered_items: 19 },
  },
  close_readiness: { status: "ready", blocking_reasons: [] },
  playbook: [],
  global: { open_issues_total: 0, open_issues_by_severity: { high: 0, medium: 0, low: 0 } },
};

describe("CompanionStrip", () => {
  afterEach(() => {
    vi.resetAllMocks();
    resetCompanionContextCacheForTests();
  });

  it("renders the glow wrapper", async () => {
    vi.mocked(useCompanionSummaryModule.useCompanionSummary).mockReturnValue({
      summary: mockSummary,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    const mockedFetch = fetchCompanionOverview as unknown as Mock;
    mockedFetch.mockResolvedValue({
      health_index: { score: 80, created_at: "2024-08-01T12:00:00Z", breakdown: {}, raw_metrics: {} },
      insights: [],
      actions: [],
      raw_metrics: {},
      next_refresh_at: null,
      llm_narrative: null,
      context: "bank",
      context_all_clear: true,
      context_metrics: {},
      has_new_actions: false,
      new_actions_count: 0,
    });

    render(<CompanionStrip context="bank" />);

    await waitFor(() => expect(screen.getByTestId("companion-strip-glow")).toBeInTheDocument());
    expect(screen.getByTestId("companion-strip-glow")).toHaveClass("companion-glow");
  });

  it("renders with all_clear status when score is high", async () => {
    vi.mocked(useCompanionSummaryModule.useCompanionSummary).mockReturnValue({
      summary: mockSummary,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    const mockedFetch = fetchCompanionOverview as unknown as Mock;
    mockedFetch.mockResolvedValue({
      health_index: { score: 95, created_at: "2024-08-01T12:00:00Z", breakdown: {}, raw_metrics: {} },
      insights: [],
      actions: [],
      raw_metrics: {},
      next_refresh_at: null,
      llm_narrative: null,
      context: "bank",
      context_all_clear: true,
      context_metrics: {},
      has_new_actions: false,
      new_actions_count: 0,
    });

    render(<CompanionStrip context="bank" />);

    await waitFor(() => expect(screen.getByTestId("companion-strip-glow")).toBeInTheDocument());
    // Should show "All clear" for high score (focusMode label)
    await waitFor(() => expect(screen.getByText(/All clear/i)).toBeInTheDocument());
  });

  it("renders fallback when summary has error", async () => {
    vi.mocked(useCompanionSummaryModule.useCompanionSummary).mockReturnValue({
      summary: null,
      isLoading: false,
      error: new Error("fail"),
      refetch: vi.fn(),
    });

    const mockedFetch = fetchCompanionOverview as unknown as Mock;
    mockedFetch.mockRejectedValue(new Error("fail"));

    render(<CompanionStrip context="bank" />);

    await waitFor(() => expect(screen.getByTestId("companion-strip-glow")).toBeInTheDocument());
    // Should show unavailable message
    await waitFor(() => expect(screen.getByText(/temporarily unavailable/i)).toBeInTheDocument());
  });

  it("calls markContextSeen on load", async () => {
    vi.mocked(useCompanionSummaryModule.useCompanionSummary).mockReturnValue({
      summary: mockSummary,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    const mockedFetch = fetchCompanionOverview as unknown as Mock;
    mockedFetch.mockResolvedValue({
      health_index: { score: 75, created_at: "2024-08-01T12:00:00Z", breakdown: {}, raw_metrics: {} },
      insights: [],
      actions: [{ id: 99, context: "bank", action_type: "bank_match_review", status: "open", confidence: 0.6, summary: "Match bank item", short_title: "Bank match", severity: "MEDIUM", payload: {}, created_at: "2024-08-01T12:00:00Z" }],
      raw_metrics: {},
      next_refresh_at: null,
      llm_narrative: { summary: null, insight_explanations: {}, action_explanations: {} },
      context: "bank",
      context_all_clear: false,
      context_metrics: {},
      has_new_actions: true,
      new_actions_count: 1,
    });

    const mockedMarkSeen = markCompanionContextSeen as unknown as Mock;
    mockedMarkSeen.mockResolvedValue({ ok: true });

    render(<CompanionStrip context="bank" />);

    await waitFor(() => expect(screen.getByTestId("companion-strip-glow")).toBeInTheDocument());
    await waitFor(() => expect(mockedMarkSeen).toHaveBeenCalledTimes(1));
  });
});
