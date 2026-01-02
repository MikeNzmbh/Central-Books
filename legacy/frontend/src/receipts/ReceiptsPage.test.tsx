import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import ReceiptsPage from "./ReceiptsPage";

const runsPayload = {
  runs: [
    { id: 1, created_at: "2025-01-01T00:00:00Z", status: "COMPLETED", total_documents: 2, success_count: 2, warning_count: 0, error_count: 0 },
  ],
};

// Payload with more than 5 runs for pagination testing
const manyRunsPayload = {
  runs: [
    { id: 1, created_at: "2025-01-01T00:00:00Z", status: "COMPLETED", total_documents: 2, success_count: 2, warning_count: 0, error_count: 0 },
    { id: 2, created_at: "2025-01-02T00:00:00Z", status: "COMPLETED", total_documents: 1, success_count: 1, warning_count: 0, error_count: 0 },
    { id: 3, created_at: "2025-01-03T00:00:00Z", status: "COMPLETED", total_documents: 3, success_count: 3, warning_count: 0, error_count: 0 },
    { id: 4, created_at: "2025-01-04T00:00:00Z", status: "COMPLETED", total_documents: 1, success_count: 1, warning_count: 0, error_count: 0 },
    { id: 5, created_at: "2025-01-05T00:00:00Z", status: "COMPLETED", total_documents: 2, success_count: 2, warning_count: 0, error_count: 0 },
    { id: 6, created_at: "2025-01-06T00:00:00Z", status: "COMPLETED", total_documents: 1, success_count: 1, warning_count: 0, error_count: 0 },
    { id: 7, created_at: "2025-01-07T00:00:00Z", status: "COMPLETED", total_documents: 4, success_count: 4, warning_count: 0, error_count: 0 },
  ],
};

const runDetailPayload = {
  id: 1,
  created_at: "2025-01-01T00:00:00Z",
  status: "COMPLETED",
  total_documents: 2,
  success_count: 2,
  warning_count: 0,
  error_count: 0,
  trace_id: "trace-123",
  llm_explanations: ["Focus on Vendor"],
  llm_ranked_documents: [{ document_id: 10, priority: "high", reason: "High amount" }],
  llm_suggested_classifications: [
    { document_id: 10, suggested_account_code: "6100", confidence: 0.8, reason: "Software vendor" },
  ],
  llm_suggested_followups: ["Confirm vendor details"],
  documents: [
    {
      id: 10,
      status: "PROCESSED",
      storage_key: "receipts/1/doc.pdf",
      original_filename: "doc.pdf",
      extracted_payload: {
        vendor: "Vendor",
        date: "2025-01-02",
        total: "31.50",
        currency: "CAD",
        user_hints: { date_hint: "2025-01-03", currency_hint: "CAD" },
      },
      proposed_journal_payload: {
        date: "2025-01-02",
        description: "Receipt - Vendor",
        lines: [
          { account_id: 1, debit: "31.50", credit: "0", description: "Expense" },
          { account_id: 2, debit: "0", credit: "31.50", description: "Cash" },
        ],
      },
      audit_flags: [{ code: "CURRENCY_MISMATCH", severity: "medium", message: "Mismatch" }],
      audit_score: "75.0",
      audit_explanations: ["Currency differs from defaults"],
      posted_journal_entry_id: null,
    },
  ],
};

describe("ReceiptsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn((url: RequestInfo | URL, options?: RequestInit) => {
      const href = String(url);
      if (href.endsWith("/api/agentic/receipts/runs")) {
        return Promise.resolve(new Response(JSON.stringify(runsPayload)));
      }
      if (href.includes("/api/agentic/receipts/run/1")) {
        return Promise.resolve(new Response(JSON.stringify(runDetailPayload)));
      }
      if (href.includes("/api/agentic/receipts/10/approve")) {
        return Promise.resolve(new Response(JSON.stringify({ journal_entry_id: 99, status: "POSTED" })));
      }
      if (href.endsWith("/api/agentic/receipts/run") && options?.method === "POST") {
        return Promise.resolve(new Response(JSON.stringify({ run_id: 1, status: "COMPLETED" })));
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders upload section and runs list", async () => {
    render(<ReceiptsPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());

    expect(screen.getByRole("heading", { name: /Upload receipts/i })).toBeInTheDocument();
    expect(screen.getByText(/Default currency/i)).toBeInTheDocument();

    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
  });

  it("shows run list with correct data", async () => {
    render(<ReceiptsPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());

    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument(); // total_documents
    expect(screen.getByText("0")).toBeInTheDocument(); // error_count

    const viewButtons = screen.getAllByText(/View/i);
    expect(viewButtons.length).toBeGreaterThan(0);
  });

  it("shows risk badges, audit flags, and console link on run detail", async () => {
    render(<ReceiptsPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("#1")).toBeInTheDocument());

    const viewBtns = screen.getAllByRole("button", { name: "View" });
    fireEvent.click(viewBtns[0]);

    await waitFor(() => expect(screen.getByText(/Run #1/)).toBeInTheDocument());
    expect(screen.getByText(/High risk/i)).toBeInTheDocument();
    expect(screen.getByText(/Currency mismatch/i)).toBeInTheDocument();
    const consoleLink = screen.getByText(/View in console/i) as HTMLAnchorElement;
    expect(consoleLink).toBeInTheDocument();
    expect(consoleLink.href).toContain("trace-123");
  });

  it("renders AI companion insights when present", async () => {
    render(<ReceiptsPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("#1")).toBeInTheDocument());

    const viewBtns = screen.getAllByRole("button", { name: "View" });
    fireEvent.click(viewBtns[0]);

    await waitFor(() => expect(screen.getByText(/Run #1/)).toBeInTheDocument());
    expect(screen.getByText(/AI Companion insights/i)).toBeInTheDocument();
    expect(screen.getByText(/Focus on Vendor/i)).toBeInTheDocument();
    expect(screen.getByText(/Top documents to review/i)).toBeInTheDocument();
  });

  it("shows journal lines preview in readable format", async () => {
    render(<ReceiptsPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());
    fireEvent.click(screen.getAllByRole("button", { name: "View" })[0]);

    await waitFor(() => expect(screen.getByText(/Run #1/)).toBeInTheDocument());

    // Check for Journal Preview section
    expect(screen.getByText(/Journal Preview/i)).toBeInTheDocument();
    // Check for table headers (may appear multiple times, use getAllByText)
    expect(screen.getAllByText(/Account/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Debit/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Credit/i).length).toBeGreaterThan(0);
  });

  it("allows editing AI-filled fields and sends overrides on approve", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<ReceiptsPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());
    fireEvent.click(screen.getAllByRole("button", { name: "View" })[0]);

    await waitFor(() => expect(screen.getByText(/Receipt Details/i)).toBeInTheDocument());

    const vendorInput = screen.getByDisplayValue("Vendor") as HTMLInputElement;
    fireEvent.change(vendorInput, { target: { value: "New Vendor" } });

    const approveBtn = screen.getByRole("button", { name: /Approve & Post/i });
    fireEvent.click(approveBtn);

    await waitFor(() => {
      const approveCall = fetchSpy.mock.calls.find(([url]) => String(url).includes("/api/agentic/receipts/10/approve"));
      expect(approveCall).toBeTruthy();
      const body = approveCall?.[1]?.body as string;
      expect(body).toContain("New Vendor");
      expect(body).toContain("overrides");
    });
  });

  it("has collapsible raw JSON debug view", async () => {
    render(<ReceiptsPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());
    fireEvent.click(screen.getAllByRole("button", { name: "View" })[0]);

    await waitFor(() => expect(screen.getByText(/Run #1/)).toBeInTheDocument());

    // Check for "Show raw JSON" toggle
    const toggles = screen.getAllByText(/Show raw JSON/i);
    expect(toggles.length).toBeGreaterThan(0);
  });
});

describe("ReceiptsPage Pagination", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn((url: RequestInfo | URL) => {
      const href = String(url);
      if (href.endsWith("/api/agentic/receipts/runs")) {
        return Promise.resolve(new Response(JSON.stringify(manyRunsPayload)));
      }
      return Promise.resolve(new Response("{}", { status: 200 }));
    }) as unknown as typeof fetch;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows only 5 runs per page when there are more than 5", async () => {
    render(<ReceiptsPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());

    // Should see runs 1-5 on page 1
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("#2")).toBeInTheDocument();
    expect(screen.getByText("#3")).toBeInTheDocument();
    expect(screen.getByText("#4")).toBeInTheDocument();
    expect(screen.getByText("#5")).toBeInTheDocument();

    // Should NOT see run 6 or 7 on page 1
    expect(screen.queryByText("#6")).not.toBeInTheDocument();
    expect(screen.queryByText("#7")).not.toBeInTheDocument();
  });

  it("shows pagination controls when there are more than 5 runs", async () => {
    render(<ReceiptsPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());

    // Check for pagination info
    expect(screen.getByText(/Page 1 of 2/i)).toBeInTheDocument();
    expect(screen.getByText(/7 total runs/i)).toBeInTheDocument();

    // Check for Previous/Next buttons
    expect(screen.getByRole("button", { name: /Previous/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Next/i })).toBeInTheDocument();
  });

  it("navigates to next page when clicking Next", async () => {
    render(<ReceiptsPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());

    // Verify we're on page 1
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.queryByText("#6")).not.toBeInTheDocument();

    // Click Next
    fireEvent.click(screen.getByRole("button", { name: /Next/i }));

    // Should now be on page 2
    await waitFor(() => expect(screen.getByText(/Page 2 of 2/i)).toBeInTheDocument());
    expect(screen.getByText("#6")).toBeInTheDocument();
    expect(screen.getByText("#7")).toBeInTheDocument();

    // Should NOT see runs 1-5
    expect(screen.queryByText("#1")).not.toBeInTheDocument();
    expect(screen.queryByText("#2")).not.toBeInTheDocument();
  });

  it("navigates back to previous page when clicking Previous", async () => {
    render(<ReceiptsPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());

    // Go to page 2
    fireEvent.click(screen.getByRole("button", { name: /Next/i }));
    await waitFor(() => expect(screen.getByText(/Page 2 of 2/i)).toBeInTheDocument());

    // Go back to page 1
    fireEvent.click(screen.getByRole("button", { name: /Previous/i }));
    await waitFor(() => expect(screen.getByText(/Page 1 of 2/i)).toBeInTheDocument());

    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.queryByText("#6")).not.toBeInTheDocument();
  });

  it("disables Previous button on first page", async () => {
    render(<ReceiptsPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());

    const prevBtn = screen.getByRole("button", { name: /Previous/i });
    expect(prevBtn).toBeDisabled();
  });

  it("disables Next button on last page", async () => {
    render(<ReceiptsPage defaultCurrency="USD" />);

    await waitFor(() => expect(screen.getByText(/Recent runs/i)).toBeInTheDocument());

    // Go to last page
    fireEvent.click(screen.getByRole("button", { name: /Next/i }));
    await waitFor(() => expect(screen.getByText(/Page 2 of 2/i)).toBeInTheDocument());

    const nextBtn = screen.getByRole("button", { name: /Next/i });
    expect(nextBtn).toBeDisabled();
  });
});
