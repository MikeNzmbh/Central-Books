import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import BooksReviewPage from "./BooksReviewPage";

const runsPayload = {
  runs: [
    {
      id: 1,
      created_at: "2025-01-01T00:00:00Z",
      status: "COMPLETED",
      period_start: "2025-01-01",
      period_end: "2025-01-31",
      metrics: { journals_high_risk: 1, journals_total: 3 },
      overall_risk_score: "80.0",
      trace_id: "trace-abc",
    },
  ],
};

const runDetailPayload = {
  id: 1,
  created_at: "2025-01-01T00:00:00Z",
  created_by: 2,
  status: "COMPLETED",
  period_start: "2025-01-01",
  period_end: "2025-01-31",
  metrics: { journals_high_risk: 1, journals_total: 3, accounts_touched: 5 },
  overall_risk_score: "80.0",
  trace_id: "trace-abc",
  findings: [
    { code: "LARGE_ENTRY", severity: "high", message: "Large journal entry 1", references: { journal_entry_id: 1 } },
  ],
  llm_explanations: ["Ledger looks healthy overall."],
  llm_ranked_issues: [
    {
      severity: "high",
      title: "Unusual spike",
      message: "Travel costs jumped 3x",
      related_journal_ids: [1],
      related_accounts: ["5010"],
    },
  ],
  llm_suggested_checks: ["Review account 5010 for October"],
};

describe("BooksReviewPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn((url: RequestInfo | URL) => {
      const href = url.toString();
      if (href.includes("/runs")) {
        return Promise.resolve(new Response(JSON.stringify(runsPayload)));
      }
      if (href.includes("/run/1")) {
        return Promise.resolve(new Response(JSON.stringify(runDetailPayload)));
      }
      if (href.includes("/run") && href.includes("http")) { // catch-all for POST
        return Promise.resolve(new Response(JSON.stringify({ run_id: 1, status: "COMPLETED" })));
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders runs and shows risk badge", async () => {
    render(<BooksReviewPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Previous reviews/i)).toBeInTheDocument());
    expect(screen.getByText(/High risk/)).toBeInTheDocument();
  });

  it("shows run list with correct data", async () => {
    render(<BooksReviewPage defaultCurrency="USD" />);

    // Wait for runs to load
    await waitFor(() => expect(screen.getByText(/Previous reviews/i)).toBeInTheDocument());

    // Verify run data is displayed
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
    expect(screen.getByText(/High risk/)).toBeInTheDocument();

    // Verify View button exists
    const viewButtons = screen.getAllByText(/View/i);
    expect(viewButtons.length).toBeGreaterThan(0);
  });

  it("renders companion insights when llm data is present", async () => {
    render(<BooksReviewPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Previous reviews/i)).toBeInTheDocument());

    // Wait for the rows to load (Wait for specific ID to ensure rows are present)
    await waitFor(() => expect(screen.getByText("#1")).toBeInTheDocument());

    const viewBtns = screen.getAllByRole("button", { name: "View" });
    fireEvent.click(viewBtns[0]);

    await waitFor(() => expect(screen.getByText(/Run #1/)).toBeInTheDocument());
    expect(screen.getByText(/AI Companion insights/i)).toBeInTheDocument();
    expect(screen.getByText(/Ledger looks healthy overall./i)).toBeInTheDocument();
    expect(screen.getByText(/Unusual spike/i)).toBeInTheDocument();
  });
});
