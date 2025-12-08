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

  it("renders all-clear state when context_all_clear flag is true", async () => {
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
    // The banner shows "in great shape" for all-clear state
    await waitFor(() => expect(screen.getByText(/in great shape/i)).toBeInTheDocument());

    // Verify glow wrapper is present
    const glowElement = screen.getByTestId("companion-strip-glow");
    expect(glowElement).toBeInTheDocument();
    expect(glowElement).toHaveClass("companion-glow");
  });

  it("shows suggestions when insights/actions present", async () => {
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
      ],
      raw_metrics: {},
      next_refresh_at: null,
      llm_narrative: { summary: null, insight_explanations: {}, action_explanations: {} },
      context: "invoices",
      context_all_clear: false,
      context_metrics: {},
      has_new_actions: true,
      new_actions_count: 1,
      context_reasons: ["1 overdue invoice to follow up."],
      context_severity: "MEDIUM",
      focus_items: ["Follow up overdue invoices"],
    });

    render(<CompanionStrip context="invoices" />);

    // Wait for the banner to render - check for common elements
    await waitFor(() => expect(screen.getByTestId("companion-strip-glow")).toBeInTheDocument());

    // Glow wrapper should be present
    expect(screen.getByTestId("companion-strip-glow")).toHaveClass("companion-glow");
  });

  it("renders all-clear when no items", async () => {
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

    // The banner shows "in great shape" for all-clear
    await waitFor(() => expect(screen.getByText(/in great shape/i)).toBeInTheDocument());
  });

  it("handles API errors gracefully", async () => {
    const mockedFetch = fetchCompanionOverview as unknown as Mock;
    mockedFetch.mockRejectedValue(new Error("fail"));

    render(<CompanionStrip context="bank" />);

    // Should still render the glow wrapper even in error state
    await waitFor(() => expect(screen.getByTestId("companion-strip-glow")).toBeInTheDocument());
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

    await waitFor(() => expect(screen.getByTestId("companion-strip-glow")).toBeInTheDocument());
    await waitFor(() => expect(mockedMarkSeen).toHaveBeenCalledTimes(1));
  });
});
