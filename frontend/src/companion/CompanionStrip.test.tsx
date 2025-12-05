import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";

import CompanionStrip from "./CompanionStrip";
import { fetchCompanionOverview, markCompanionContextSeen } from "./api";
import { resetCompanionContextCacheForTests } from "./useCompanionContext";

vi.mock("./api", () => ({
  fetchCompanionOverview: vi.fn(),
  markCompanionContextSeen: vi.fn(),
}));

describe("CompanionStrip", () => {
  afterEach(() => {
    vi.resetAllMocks();
    resetCompanionContextCacheForTests();
  });

  it("renders calm mode when context_all_clear flag is true", async () => {
    const mockedFetch = fetchCompanionOverview as unknown as Mock;
    mockedFetch.mockResolvedValue({
      health_index: {
        score: 80,
        created_at: "2024-08-01T12:00:00Z",
        breakdown: {},
        raw_metrics: {},
      },
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
      context_reasons: ["No unreconciled items."],
      context_severity: "INFO",
      focus_items: [],
    });

    render(<CompanionStrip context="bank" />);
    await waitFor(() => expect(screen.getByText(/Everything looks good here/i)).toBeInTheDocument());
    expect(screen.getByText(/found nothing urgent/i)).toBeInTheDocument();
    expect(screen.getByText(/Info/i)).toBeInTheDocument();
    expect(screen.getByText(/No unreconciled items/i)).toBeInTheDocument();

    // Verify glow wrapper is present in calm state
    const glowElement = screen.getByTestId("companion-strip-glow");
    expect(glowElement).toBeInTheDocument();
    expect(glowElement).toHaveClass("companion-glow");
  });

  it("filters insights and actions by context", async () => {
    const mockedFetch = fetchCompanionOverview as unknown as Mock;
    mockedFetch.mockResolvedValue({
      health_index: {
        score: 72,
        created_at: "2024-08-01T12:00:00Z",
        breakdown: {},
        raw_metrics: {},
      },
      insights: [
        {
          id: 1,
          context: "invoices",
          domain: "invoices",
          title: "Overdue invoice to follow up",
          body: "Invoice is overdue",
          severity: "warning",
          suggested_actions: [],
          created_at: "2024-08-01T12:00:00Z",
        },
        {
          id: 2,
          context: "bank",
          domain: "reconciliation",
          title: "Bank match alert",
          body: "Match bank items",
          severity: "info",
          suggested_actions: [],
          created_at: "2024-08-01T12:00:00Z",
        },
      ],
      actions: [
        {
          id: 10,
          context: "invoices",
          action_type: "send_invoice_reminder",
          status: "open",
          confidence: 0.5,
          summary: "Send reminder for INV-100",
          short_title: "Invoice reminder",
          severity: "MEDIUM",
          payload: { invoice_id: 100 },
          created_at: "2024-08-01T12:00:00Z",
        },
        {
          id: 11,
          context: "bank",
          action_type: "bank_match_review",
          status: "open",
          confidence: 0.7,
          summary: "Match bank txn",
          short_title: "Bank match",
          severity: "HIGH",
          payload: {},
          created_at: "2024-08-01T12:00:00Z",
        },
      ],
      raw_metrics: {},
      next_refresh_at: null,
      llm_narrative: { summary: null, insight_explanations: {}, action_explanations: {} },
      context: "invoices",
      context_all_clear: false,
      context_metrics: {},
      has_new_actions: true,
      new_actions_count: 2,
      context_reasons: ["2 overdue invoices to follow up."],
      context_severity: "MEDIUM",
      focus_items: ["Follow up overdue invoices"],
    });

    render(<CompanionStrip context="invoices" />);

    await waitFor(() => expect(screen.getByText(/Companion suggests/i)).toBeInTheDocument());

    // Verify glow wrapper is present in active state
    expect(screen.getByTestId("companion-strip-glow")).toHaveClass("companion-glow");
    expect(screen.getByText(/Follow up overdue invoices/i)).toBeInTheDocument();

    expect(screen.getByText(/Overdue invoice/)).toBeInTheDocument();
    expect(screen.getByText(/Send reminder for INV-100/)).toBeInTheDocument();
    expect(screen.queryByText(/Bank match alert/)).not.toBeInTheDocument();
  });

  it("renders calm message when no items", async () => {
    const mockedFetch = fetchCompanionOverview as unknown as Mock;
    mockedFetch.mockResolvedValue({
      health_index: {
        score: 90,
        created_at: "2024-08-01T12:00:00Z",
        breakdown: {},
        raw_metrics: {},
      },
      insights: [],
      actions: [],
      raw_metrics: {},
      next_refresh_at: null,
      llm_narrative: { summary: null, insight_explanations: {}, action_explanations: {} },
      context: "expenses",
      context_all_clear: true,
      context_metrics: {},
      has_new_actions: false,
      new_actions_count: 0,
    });

    render(<CompanionStrip context="expenses" />);

    await waitFor(() => expect(screen.getByText(/Everything looks good here/i)).toBeInTheDocument());
  });

  it("handles API errors quietly", async () => {
    const mockedFetch = fetchCompanionOverview as unknown as Mock;
    mockedFetch.mockRejectedValue(new Error("fail"));

    render(<CompanionStrip context="bank" />);

    await waitFor(() => expect(screen.getByText(/Companion temporarily unavailable/i)).toBeInTheDocument());

    // Verify glow wrapper is present even in error state
    expect(screen.getByTestId("companion-strip-glow")).toHaveClass("companion-glow");
  });

  it("marks context seen once on load", async () => {
    const mockedFetch = fetchCompanionOverview as unknown as Mock;
    mockedFetch.mockResolvedValue({
      health_index: {
        score: 75,
        created_at: "2024-08-01T12:00:00Z",
        breakdown: {},
        raw_metrics: {},
      },
      insights: [],
      actions: [
        {
          id: 99,
          context: "bank",
          action_type: "bank_match_review",
          status: "open",
          confidence: 0.6,
          summary: "Match bank item",
          short_title: "Bank match",
          severity: "MEDIUM",
          payload: {},
          created_at: "2024-08-01T12:00:00Z",
        },
      ],
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

    await waitFor(() => expect(screen.getByText(/Companion suggests/i)).toBeInTheDocument());
    await waitFor(() => expect(mockedMarkSeen).toHaveBeenCalledTimes(1));
  });
});
