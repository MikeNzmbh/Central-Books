import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, afterEach, type Mock } from "vitest";

import CompanionPanel from "./CompanionPanel";
import { applyCompanionAction, dismissCompanionAction, fetchCompanionOverview } from "./api";

vi.mock("./api", () => ({
  fetchCompanionOverview: vi.fn(),
  applyCompanionAction: vi.fn(),
  dismissCompanionAction: vi.fn(),
  getPrimaryButtonLabel: vi.fn((action: any) => {
    // Simple mock implementation based on action_type
    if (action.action_type === "bank_match_review") return "Match";
    if (action.action_type === "overdue_invoice_reminders") return "Review";
    if (action.action_type === "uncategorized_transactions_cleanup") return "Fix now";
    if (action.action_type === "reconciliation_period_to_close") return "Close period";
    return "Review";
  }),
  ACTION_BEHAVIOR_MAP: {
    bank_match_review: "autofix",
    overdue_invoice_reminders: "review",
    uncategorized_expense_review: "review",
    old_unreconciled_investigate: "review",
    suspense_balance_review: "review",
    inactive_customers_followup: "review",
    spike_expense_category_review: "review",
    send_invoice_reminder: "autofix",
    categorize_expenses_batch: "autofix",
    uncategorized_transactions_cleanup: "autofix",
    reconciliation_period_to_close: "close",
  },
}));

describe("CompanionPanel", () => {
  afterEach(() => {
    vi.resetAllMocks();
  });

  it("renders health score, insights, and actions with explanations", async () => {
    const mockResponse = {
      health_index: {
        score: 82,
        created_at: "2024-08-01T12:00:00Z",
        breakdown: {
          reconciliation: 75,
          invoices: 80,
        },
        raw_metrics: {
          unreconciled_count: 3,
        },
      },
      insights: [
        {
          id: 1,
          context: "reconciliation",
          domain: "reconciliation",
          title: "Tighten reconciliation",
          body: "You have unreconciled transactions waiting.",
          severity: "warning",
          suggested_actions: [{ label: "Open banking" }],
          created_at: "2024-08-01T12:00:00Z",
        },
      ],
      raw_metrics: {
        unreconciled_count: 3,
      },
      next_refresh_at: "2024-08-02T12:00:00Z",
      llm_narrative: {
        summary: "Books look steady; clear reconciliations soon.",
        insight_explanations: { "1": "These items are aging past 60 days." },
        action_explanations: { "10": "Apply this match to clear reconciliation." },
        context_summary: "Reconciliation needs attention.",
        focus_items: ["Resolve 3 unreconciled items"],
      },
      actions: [
        {
          id: 10,
          context: "reconciliation",
          action_type: "bank_match_review",
          status: "open",
          confidence: 0.97,
          summary: "Likely match between bank txn and invoice",
          short_title: "Bank match",
          severity: "HIGH",
          payload: {
            bank_transaction_id: 99,
            journal_entry_id: 42,
            amount: "250.00",
            date: "2024-07-31",
            currency: "USD",
          },
          created_at: "2024-08-01T12:00:00Z",
        },
      ],
      context_reasons: ["3 transactions to reconcile."],
      context_all_clear: false,
      context_severity: "HIGH",
    };

    const mockedFetch = fetchCompanionOverview as unknown as Mock;
    mockedFetch.mockResolvedValue(mockResponse);

    render(<CompanionPanel />);

    await waitFor(() => expect(screen.getByText(/Health 82\/100/)).toBeInTheDocument());

    // Verify glow wrapper is always present with correct class
    const glowElement = screen.getByTestId("companion-glow");
    expect(glowElement).toBeInTheDocument();
    expect(glowElement).toHaveClass("companion-glow");

    expect(screen.getByText("Tighten reconciliation")).toBeInTheDocument();
    expect(screen.getByText(/Resolve 3 unreconciled items/i)).toBeInTheDocument();
    expect(screen.getByText(/aging past 60 days/i)).toBeInTheDocument();
    expect(screen.getByText(/Likely match between bank txn/i)).toBeInTheDocument();
    expect(screen.getByText(/Apply this match/i)).toBeInTheDocument();
  });

  it("falls back to calm message when no summary and no critical insights", async () => {
    const mockedFetch = fetchCompanionOverview as unknown as Mock;
    mockedFetch.mockResolvedValue({
      health_index: {
        score: 90,
        created_at: "2024-08-01T12:00:00Z",
        breakdown: {},
        raw_metrics: {},
      },
      insights: [],
      raw_metrics: {},
      next_refresh_at: null,
      llm_narrative: {
        summary: null,
        insight_explanations: {},
        action_explanations: {},
      },
      actions: [],
      context_all_clear: true,
      context_reasons: ["No overdue invoices.", "No uncategorized expenses."],
      context_severity: "INFO",
    });

    render(<CompanionPanel />);

    await waitFor(() => expect(screen.getByText(/everything looks fine/i)).toBeInTheDocument());

    // Verify glow wrapper is present even in calm state
    expect(screen.getByTestId("companion-glow")).toBeInTheDocument();
    expect(screen.getByTestId("companion-glow")).toHaveClass("companion-glow");
    expect(screen.getByText(/No overdue invoices/i)).toBeInTheDocument();
  });

  it("shows suggested actions and allows apply/dismiss", async () => {
    const mockResponse = {
      health_index: {
        score: 70,
        created_at: "2024-08-01T12:00:00Z",
        breakdown: { reconciliation: 60 },
        raw_metrics: {},
      },
      insights: [],
      raw_metrics: {},
      next_refresh_at: null,
      llm_narrative: {
        summary: null,
        insight_explanations: {},
        action_explanations: {},
      },
      actions: [
        {
          id: 5,
          context: "reconciliation",
          action_type: "bank_match_review",
          status: "open",
          confidence: 0.9,
          summary: "Match bank txn 5 to JE 10",
          short_title: "Bank match",
          severity: "MEDIUM",
          payload: { bank_transaction_id: 5, journal_entry_id: 10, amount: "100.00", date: "2024-08-01" },
          created_at: "2024-08-01T12:00:00Z",
        },
      ],
    };

    (fetchCompanionOverview as unknown as Mock).mockResolvedValue(mockResponse);
    (applyCompanionAction as unknown as Mock).mockResolvedValue({});
    (dismissCompanionAction as unknown as Mock).mockResolvedValue({});

    render(<CompanionPanel />);

    // Wait for and verify the Match button appears (bank_match_review action)
    await waitFor(() => expect(screen.getByText("Match")).toBeInTheDocument());

    // Verify the Dismiss button also appears
    expect(screen.getByText("Dismiss")).toBeInTheDocument();

    // Click Match
    fireEvent.click(screen.getByText("Match"));
    // Verify applyCompanionAction was called with the action ID
    await waitFor(() => expect(applyCompanionAction).toHaveBeenCalledWith(5));
  });

  it("keeps glow wrapper visible in error state", async () => {
    const mockedFetch = fetchCompanionOverview as unknown as Mock;
    mockedFetch.mockRejectedValue(new Error("Request failed"));

    render(<CompanionPanel />);

    await waitFor(() => expect(screen.getByText(/Companion temporarily unavailable/i)).toBeInTheDocument());
    const glowElement = screen.getByTestId("companion-glow");
    expect(glowElement).toBeInTheDocument();
    expect(glowElement).toHaveClass("companion-glow");
  });
});
