import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import CompanionControlTowerPage from "./CompanionControlTowerPage";

const summaryPayload = {
  ai_companion_enabled: true,
  surfaces: {
    receipts: {
      recent_runs: [{ id: 1, created_at: "2025-01-01T00:00:00Z", risk_level: "medium", documents_total: 10, high_risk_count: 2 }],
      totals_last_30_days: { runs: 2, documents_total: 20, high_risk_documents: 3, errors: 1 },
    },
    invoices: {
      recent_runs: [{ id: 2, created_at: "2025-01-02T00:00:00Z", risk_level: "low", documents_total: 5, high_risk_count: 0 }],
      totals_last_30_days: { runs: 1, documents_total: 5, high_risk_documents: 0, errors: 0 },
    },
    books_review: {
      recent_runs: [{ id: 3, created_at: "2025-01-03T00:00:00Z", period_start: "2025-01-01", period_end: "2025-01-31", risk_level: "high" }],
      totals_last_30_days: { runs: 1, high_risk_count: 1, agent_retries: 2 },
    },
    bank_review: {
      recent_runs: [{ id: 4, created_at: "2025-01-04T00:00:00Z", risk_level: "medium", transactions_total: 8, high_risk_count: 1, unreconciled: 2 }],
      totals_last_30_days: { runs: 1, transactions_total: 8, transactions_high_risk: 1, unreconciled: 2 },
    },
  },
  global: {
    last_books_review: {
      run_id: 3,
      period_start: "2025-01-01",
      period_end: "2025-01-31",
      overall_risk_score: "80.0",
      risk_level: "high",
      trace_id: "trace-123",
    },
    high_risk_items_30d: { receipts: 3, invoices: 0, bank_transactions: 1 },
    agent_retries_30d: 4,
  },
};

describe("CompanionControlTowerPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn(() => Promise.resolve(new Response(JSON.stringify(summaryPayload)))) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders control tower cards and surfaces", async () => {
    render(
      <MemoryRouter>
        <CompanionControlTowerPage />
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText(/Companion Control Tower/i)).toBeInTheDocument());
    expect(screen.getByText(/Health Pulse/i)).toBeInTheDocument();
    expect(screen.getByText(/Today's Focus/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Receipts/i).length).toBeGreaterThan(0);
  });

  it("shows disabled banner when ai_companion_enabled is false", async () => {
    (globalThis.fetch as any) = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify({ ...summaryPayload, ai_companion_enabled: false })))
    );
    render(
      <MemoryRouter>
        <CompanionControlTowerPage />
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText(/Companion is disabled/i)).toBeInTheDocument());
  });
});
