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

  it("renders the books review page", async () => {
    render(<BooksReviewPage />);

    // Wait for page to load - check for title
    await waitFor(() => expect(screen.getByText(/Books Review/i)).toBeInTheDocument());
  });

  it("shows run history section", async () => {
    render(<BooksReviewPage />);

    // Wait for runs to load - check for "Run History" heading
    await waitFor(() => expect(screen.getByText(/Run History/i)).toBeInTheDocument());
  });

  it("shows risk assessment when run is selected", async () => {
    render(<BooksReviewPage />);

    await waitFor(() => expect(screen.getByText(/Run History/i)).toBeInTheDocument());

    // Risk badge should be visible (may appear multiple times)
    expect(screen.getAllByText(/High Risk/i).length).toBeGreaterThan(0);
  });

  it("renders neural analysis when llm data is present", async () => {
    render(<BooksReviewPage />);

    // Wait for content to load
    await waitFor(() => expect(screen.getByText(/Neural Analysis/i)).toBeInTheDocument());

    // Check for LLM explanations
    expect(screen.getByText(/Ledger looks healthy overall/i)).toBeInTheDocument();
    expect(screen.getByText(/Unusual spike/i)).toBeInTheDocument();
  });
});
