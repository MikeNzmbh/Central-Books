import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import InvoicesPage from "./InvoicesPage";

const runsPayload = {
  runs: [
    {
      id: 1,
      created_at: "2025-01-01T00:00:00Z",
      status: "COMPLETED",
      total_documents: 1,
      success_count: 1,
      warning_count: 0,
      error_count: 0,
    },
  ],
};

const runDetailPayload = {
  id: 1,
  created_at: "2025-01-01T00:00:00Z",
  status: "COMPLETED",
  total_documents: 1,
  success_count: 1,
  warning_count: 0,
  error_count: 0,
  trace_id: "inv-trace-1",
  llm_explanations: ["Focus on overdue invoice"],
  llm_ranked_documents: [{ document_id: 99, priority: "high", reason: "Overdue and high amount" }],
  llm_suggested_classifications: [{ document_id: 99, suggested_account_code: "6200", confidence: 0.7, reason: "Software" }],
  llm_suggested_followups: ["Confirm due date"],
  documents: [
    {
      id: 99,
      status: "PROCESSED",
      storage_key: "invoices/1/doc.pdf",
      original_filename: "doc.pdf",
      extracted_payload: { vendor: "Vendor", invoice_number: "INV-1" },
      proposed_journal_payload: { lines: [] },
      audit_flags: [{ code: "UNUSUAL_AMOUNT", severity: "high", message: "Big amount" }],
      audit_score: "85.0",
      audit_explanations: ["High amount detected"],
      posted_journal_entry_id: null,
    },
  ],
};

describe("InvoicesPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn((url: RequestInfo | URL) => {
      const href = String(url);
      if (href.endsWith("/api/agentic/invoices/runs")) {
        return Promise.resolve(new Response(JSON.stringify(runsPayload)));
      }
      if (href.includes("/api/agentic/invoices/run/1")) {
        return Promise.resolve(new Response(JSON.stringify(runDetailPayload)));
      }
      if (href.includes("/api/agentic/invoices/99/approve")) {
        return Promise.resolve(new Response(JSON.stringify({ journal_entry_id: 77, status: "POSTED" })));
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders upload section and runs list", async () => {
    render(<InvoicesPage defaultCurrency="USD" />);

    // Wait for page to render
    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());

    // Verify upload section via specific h2 heading
    expect(screen.getByRole("heading", { name: /Upload invoices/i })).toBeInTheDocument();
    expect(screen.getByText(/Default currency/i)).toBeInTheDocument();

    // Verify run data is displayed
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
  });

  it("shows run list with correct data", async () => {
    render(<InvoicesPage defaultCurrency="USD" />);

    // Wait for runs to load
    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());

    // Verify run data is displayed
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument(); // total_documents
    expect(screen.getByText("0")).toBeInTheDocument(); // error_count

    // Verify View button exists
    const viewButtons = screen.getAllByText(/View/i);
    expect(viewButtons.length).toBeGreaterThan(0);
  });

  it("renders AI companion insights when present", async () => {
    render(<InvoicesPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());

    // Wait for the rows to load
    await waitFor(() => expect(screen.getByText("#1")).toBeInTheDocument());

    const viewBtns = screen.getAllByRole("button", { name: "View" });
    fireEvent.click(viewBtns[0]);

    await waitFor(() => expect(screen.getByText(/Run #1/)).toBeInTheDocument());
    expect(screen.getByText(/AI Companion insights/i)).toBeInTheDocument();
    expect(screen.getByText(/Focus on overdue invoice/i)).toBeInTheDocument();
    expect(screen.getByText(/Top documents to review/i)).toBeInTheDocument();
  });
});
