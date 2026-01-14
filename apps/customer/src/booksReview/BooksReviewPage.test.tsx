import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { screen, waitFor, fireEvent, within } from "@testing-library/react";
import { renderWithRouter } from "../test/testUtils";
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
      if (href.endsWith("/api/agentic/books-review/runs")) {
        return Promise.resolve(new Response(JSON.stringify(runsPayload)));
      }
      if (href.includes("/api/agentic/books-review/run/1")) {
        return Promise.resolve(new Response(JSON.stringify(runDetailPayload)));
      }
      if (href.includes("/api/agentic/books-review/run") && !href.includes("/run/")) {
        return Promise.resolve(new Response(JSON.stringify({ run_id: 1, status: "COMPLETED" })));
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders runs and shows risk badge", async () => {
    renderWithRouter(<BooksReviewPage />);

    await waitFor(() => expect(screen.getByText(/Previous analysis archives/i)).toBeInTheDocument());
    const historyTable = screen.getByRole("table");
    const historyScope = within(historyTable);
    expect(historyScope.getByText(/High Risk/i)).toBeInTheDocument();
  });

  it("shows run list with correct data", async () => {
    renderWithRouter(<BooksReviewPage />);

    // Wait for runs to load
    await waitFor(() => expect(screen.getByText(/Previous analysis archives/i)).toBeInTheDocument());

    // Verify run data is displayed
    const historyTable = screen.getByRole("table");
    const historyScope = within(historyTable);
    expect(historyScope.getByText("2025-01-01")).toBeInTheDocument();
    expect(historyScope.getByText("2025-01-31")).toBeInTheDocument();
    expect(historyScope.getByText(/High Risk/i)).toBeInTheDocument();

    // Verify history row is clickable
    const runRow = historyScope.getByText("2025-01-01").closest("tr");
    expect(runRow).not.toBeNull();
  });

  it("renders companion insights when llm data is present", async () => {
    renderWithRouter(<BooksReviewPage />);

    await waitFor(() => expect(screen.getByText(/Previous analysis archives/i)).toBeInTheDocument());

    // Wait for the rows to load (Wait for specific date to ensure rows are present)
    const historyTable = screen.getByRole("table");
    const historyScope = within(historyTable);
    await waitFor(() => expect(historyScope.getByText("2025-01-01")).toBeInTheDocument());

    const runRow = historyScope.getByText("2025-01-01").closest("tr");
    expect(runRow).not.toBeNull();
    fireEvent.click(runRow as HTMLElement);

    await waitFor(() => expect(screen.getByText(/Run #1/)).toBeInTheDocument());
    expect(screen.getByText(/Neural Analysis/i)).toBeInTheDocument();
    expect(screen.getByText(/Ledger looks healthy overall./i)).toBeInTheDocument();
    expect(screen.getByText(/Unusual spike/i)).toBeInTheDocument();
  });
});
