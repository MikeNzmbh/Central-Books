import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi, type Mock } from "vitest";

import CompanionStrip from "./CompanionStrip";
import { fetchCompanionOverview } from "./api";
import { resetCompanionContextCacheForTests } from "./useCompanionContext";

vi.mock("./api", () => ({
  fetchCompanionOverview: vi.fn(),
}));

describe("CompanionStrip", () => {
  afterEach(() => {
    vi.resetAllMocks();
    resetCompanionContextCacheForTests();
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
          payload: {},
          created_at: "2024-08-01T12:00:00Z",
        },
      ],
      raw_metrics: {},
      next_refresh_at: null,
      llm_narrative: { summary: null, insight_explanations: {}, action_explanations: {} },
    });

    render(<CompanionStrip context="invoices" />);

    await waitFor(() => expect(screen.getByText(/Companion suggests/i)).toBeInTheDocument());
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
    });

    render(<CompanionStrip context="expenses" />);

    await waitFor(() => expect(screen.getByText(/nothing needs attention/i)).toBeInTheDocument());
  });

  it("handles API errors quietly", async () => {
    const mockedFetch = fetchCompanionOverview as unknown as Mock;
    mockedFetch.mockRejectedValue(new Error("fail"));

    render(<CompanionStrip context="bank" />);

    await waitFor(() => expect(screen.getByText(/Companion temporarily unavailable/i)).toBeInTheDocument());
  });
});
