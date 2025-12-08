import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import BankAuditHealthCheckPage from "./BankReviewPage";

// Mock data matching the new Bank Audit & Health Check API response
const summaryPayload = {
  banks: [
    {
      id: "1",
      name: "Scotia Business Checking",
      last4: "4923",
      currency: "CAD",
      status: "medium",
      unreconciledCount: 76,
      unreconciledAmount: "$15,827.09",
      totalTransactions: 150,
      balance: "$15,827.09",
      lastSynced: "2 hours ago",
    },
  ],
  flaggedTransactions: {
    "1": [
      {
        id: "tx1",
        date: "2025-01-01",
        description: "Unknown Deposit",
        amount: "$1,000.00",
        currency: "CAD",
        flags: ["UNMATCHED"],
        insight: "This transaction has no matching invoice or expense.",
      },
    ],
  },
  insights: {
    "1": [
      {
        id: "insight1",
        type: "anomaly",
        title: "Large unmatched deposit",
        description: "Review this transaction for proper categorization.",
      },
    ],
  },
  previousAudits: [],
  companionEnabled: true,
};

const emptyPayload = {
  banks: [],
  flaggedTransactions: {},
  insights: {},
  previousAudits: [],
  companionEnabled: false,
};

describe("BankAuditHealthCheckPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify(summaryPayload)))
    ) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the bank audit page title", async () => {
    render(<BankAuditHealthCheckPage />);
    await waitFor(() =>
      expect(screen.getByText(/Bank Audit/i)).toBeInTheDocument()
    );
  });

  it("shows loading state initially", () => {
    render(<BankAuditHealthCheckPage />);
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("shows empty state when no banks", async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify(emptyPayload)))
    ) as unknown as typeof fetch;

    render(<BankAuditHealthCheckPage />);
    await waitFor(() =>
      expect(screen.getByText(/No bank accounts/i)).toBeInTheDocument()
    );
  });

  it("handles API errors gracefully", async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.reject(new Error("Network error"))
    ) as unknown as typeof fetch;

    render(<BankAuditHealthCheckPage />);
    await waitFor(() =>
      expect(screen.getByText(/error/i)).toBeInTheDocument()
    );
  });
});
