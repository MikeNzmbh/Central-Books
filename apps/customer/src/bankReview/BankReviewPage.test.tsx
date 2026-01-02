import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import BankReviewPage from "./BankReviewPage";

const runsPayload = {
  runs: [
    {
      id: 1,
      created_at: "2025-01-01T00:00:00Z",
      status: "COMPLETED",
      period_start: "2025-01-01",
      period_end: "2025-01-31",
      metrics: { transactions_unreconciled: 1, transactions_total: 2 },
      overall_risk_score: "80.0",
      trace_id: "trace-bank",
    },
  ],
};

const runDetailPayload = {
  id: 1,
  created_at: "2025-01-01T00:00:00Z",
  status: "COMPLETED",
  period_start: "2025-01-01",
  period_end: "2025-01-31",
  metrics: { transactions_unreconciled: 1, transactions_total: 2, transactions_high_risk: 1 },
  overall_risk_score: "80.0",
  trace_id: "trace-bank",
  transactions: [
    {
      id: 10,
      status: "UNMATCHED",
      raw_payload: { date: "2025-01-01", description: "Deposit", amount: "100" },
      matched_journal_ids: [],
      audit_flags: [{ code: "UNMATCHED_TRANSACTION", severity: "high", message: "No ledger match found." }],
      audit_score: "90.0",
      audit_explanations: ["Companion reflection attempted fuzzy matching on unmatched lines."],
    },
  ],
  llm_explanations: ["Focus on unmatched withdrawals first."],
  llm_ranked_transactions: [{ transaction_id: 10, priority: "high", reason: "Large unmatched withdrawal" }],
  llm_suggested_followups: ["Confirm support for transaction 10"],
};

describe("BankReviewPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn((url: RequestInfo | URL) => {
      const href = String(url);
      if (href.endsWith("/api/agentic/bank-review/runs")) {
        return Promise.resolve(new Response(JSON.stringify(runsPayload)));
      }
      if (href.includes("/api/agentic/bank-review/run/1")) {
        return Promise.resolve(new Response(JSON.stringify(runDetailPayload)));
      }
      if (href.endsWith("/api/agentic/bank-review/run") && href.includes("http")) {
        return Promise.resolve(new Response(JSON.stringify({ run_id: 1, status: "COMPLETED" })));
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders runs and risk badge", async () => {
    render(<BankReviewPage />);
    await waitFor(() => expect(screen.getByText(/Previous runs/i)).toBeInTheDocument());
    expect(screen.getByText(/High risk/)).toBeInTheDocument();
  });

  it("shows run list with correct data", async () => {
    render(<BankReviewPage />);

    // Wait for runs to load
    await waitFor(() => expect(screen.getByText(/Previous runs/i)).toBeInTheDocument());

    // Verify run data is displayed
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
    expect(screen.getByText(/High risk/)).toBeInTheDocument();

    // Verify View button exists
    const viewButtons = screen.getAllByText(/View/i);
    expect(viewButtons.length).toBeGreaterThan(0);
  });

  it("renders AI companion insights when present", async () => {
    render(<BankReviewPage />);

    await waitFor(() => expect(screen.getByText(/Previous runs/i)).toBeInTheDocument());

    // Wait for the rows to load
    await waitFor(() => expect(screen.getByText("#1")).toBeInTheDocument());

    const viewBtns = screen.getAllByRole("button", { name: "View" });
    fireEvent.click(viewBtns[0]);

    await waitFor(() => expect(screen.getByText(/Run #1/)).toBeInTheDocument());
    expect(screen.getByText(/AI Companion insights/i)).toBeInTheDocument();
    expect(screen.getByText(/Focus on unmatched withdrawals first./i)).toBeInTheDocument();
    expect(screen.getByText(/Top transactions to review/i)).toBeInTheDocument();
  });
});
