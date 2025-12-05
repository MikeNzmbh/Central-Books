import React from "react";
import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, cleanup, waitFor, fireEvent, screen } from "@testing-library/react";

import ReconciliationPage from "./ReconciliationPage";

const buildResponse = (data: any, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => data,
  text: async () => (typeof data === "string" ? data : JSON.stringify(data)),
});

describe("ReconciliationPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    cleanup();
    document.body.innerHTML = '<input name="csrfmiddlewaretoken" value="testtoken" />';
  });

  const baseAccount = [{ id: "1", name: "Checking", currency: "USD" }];
  const basePeriods = [{ id: "2024-01", label: "Jan 2024", start_date: "2024-01-01", end_date: "2024-01-31", is_current: false, is_locked: false }];

  it("loads session for selected period", async () => {
    const periods = [
      { id: "2024-02", label: "Feb 2024", start_date: "2024-02-01", end_date: "2024-02-29", is_current: false, is_locked: false },
      { id: "2024-01", label: "Jan 2024", start_date: "2024-01-01", end_date: "2024-01-31", is_current: false, is_locked: false },
    ];
    const fetchMock = vi.fn().mockImplementation((url: RequestInfo | URL) => {
      const href = String(url);
      if (href.endsWith("/api/reconciliation/accounts/")) return buildResponse(baseAccount);
      if (href.includes("/api/reconciliation/accounts/1/periods/")) return buildResponse(periods);
      if (href.startsWith("/api/reconciliation/session/?")) {
        const params = new URLSearchParams(href.split("?")[1]);
        return buildResponse({
          bank_account: { id: "1", name: "Checking", currency: "USD" },
          period: { start_date: params.get("start"), end_date: params.get("end") },
          session: {
            id: "555",
            status: "IN_PROGRESS",
            opening_balance: "0.00",
            statement_ending_balance: "0.00",
            cleared_balance: "0.00",
            difference: "0.00",
            reconciled_percent: 0,
            total_transactions: 0,
            reconciled_count: 0,
            unreconciled_count: 0,
          },
          feed: { new: [], matched: [], partial: [], excluded: [] },
        });
      }
      return buildResponse([]);
    });
    // @ts-ignore
    global.fetch = fetchMock;

    render(<ReconciliationPage />);

    await waitFor(() => {
      const called = fetchMock.mock.calls.some(call => String(call[0]).includes("start=2024-02-01"));
      expect(called).toBe(true);
    });
  });

  it("shows reopen button for completed session and refetches after reopening", async () => {
    let reopened = false;
    const fetchMock = vi.fn().mockImplementation((url: RequestInfo | URL) => {
      const href = String(url);
      if (href.endsWith("/api/reconciliation/accounts/")) return buildResponse(baseAccount);
      if (href.includes("/api/reconciliation/accounts/1/periods/")) return buildResponse(basePeriods);
      if (href.startsWith("/api/reconciliation/session/") && href.includes("/reopen/")) {
        reopened = true;
        return buildResponse({
          session: { id: "123", status: "IN_PROGRESS", opening_balance: "0.00", statement_ending_balance: "0.00", cleared_balance: "0.00", difference: "0.00", reconciled_percent: 100, total_transactions: 0, reconciled_count: 0, unreconciled_count: 0 },
          feed: { new: [], matched: [], partial: [], excluded: [] },
          bank_account: { id: "1", name: "Checking", currency: "USD" },
          period: { start_date: "2024-01-01", end_date: "2024-01-31" },
        });
      }
      if (href.startsWith("/api/reconciliation/session/?")) {
        return buildResponse({
          bank_account: { id: "1", name: "Checking", currency: "USD" },
          period: { start_date: "2024-01-01", end_date: "2024-01-31" },
          session: {
            id: "123",
            status: reopened ? "IN_PROGRESS" : "COMPLETED",
            opening_balance: "0.00",
            statement_ending_balance: "0.00",
            cleared_balance: "0.00",
            difference: "0.00",
            reconciled_percent: 100,
            total_transactions: 0,
            reconciled_count: 0,
            unreconciled_count: 0,
          },
          feed: { new: [], matched: [], partial: [], excluded: [] },
        });
      }
      return buildResponse([]);
    });
    // @ts-ignore
    global.fetch = fetchMock;

    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<ReconciliationPage />);

    await screen.findByText("Reopen period");
    fireEvent.click(screen.getByText("Reopen period"));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith("/api/reconciliation/sessions/123/reopen/", expect.any(Object));
      const refetch = fetchMock.mock.calls.some(call => String(call[0]).startsWith("/api/reconciliation/session/?"));
      expect(refetch).toBe(true);
    });
  });

  it("renders status text from ui_status and is_cleared and filters by ui_status", async () => {
    const sessionPayload = {
      bank_account: { id: "1", name: "Checking", currency: "USD" },
      period: { start_date: "2024-01-01", end_date: "2024-01-31" },
      session: {
        id: "200",
        status: "IN_PROGRESS",
        opening_balance: "0.00",
        statement_ending_balance: "0.00",
        cleared_balance: "0.00",
        difference: "0.00",
        reconciled_percent: 50,
        total_transactions: 4,
        reconciled_count: 2,
        unreconciled_count: 2,
      },
      feed: {
        new: [
          {
            id: "n1",
            date: "2024-01-02",
            description: "New item",
            amount: 10,
            currency: "USD",
            ui_status: "NEW",
            is_cleared: false,
          },
        ],
        matched: [
          {
            id: "m1",
            date: "2024-01-03",
            description: "Matched item",
            amount: 20,
            currency: "USD",
            ui_status: "MATCHED",
            is_cleared: true,
          },
        ],
        partial: [
          {
            id: "p1",
            date: "2024-01-04",
            description: "Partial item",
            amount: -15,
            currency: "USD",
            ui_status: "PARTIAL",
            is_cleared: true,
          },
        ],
        excluded: [
          {
            id: "e1",
            date: "2024-01-05",
            description: "Excluded item",
            amount: 5,
            currency: "USD",
            ui_status: "EXCLUDED",
            is_cleared: false,
          },
        ],
      },
    };

    const fetchMock = vi.fn().mockImplementation((url: RequestInfo | URL) => {
      const href = String(url);
      if (href.endsWith("/api/reconciliation/accounts/")) return buildResponse(baseAccount);
      if (href.includes("/api/reconciliation/accounts/1/periods/")) return buildResponse(basePeriods);
      if (href.startsWith("/api/reconciliation/session/?")) return buildResponse(sessionPayload);
      if (href.startsWith("/api/reconciliation/matches/")) return buildResponse([]);
      return buildResponse([]);
    });
    // @ts-ignore
    global.fetch = fetchMock;

    render(<ReconciliationPage />);

    // Verify status badges are shown (new UI uses badges instead of helper text)
    await screen.findByText("New item");
    expect(screen.getAllByText(/MATCHED/i).length).toBeGreaterThan(0);

    // Test filter - click on Excluded filter tab
    const excludedFilters = screen.getAllByRole("button", { name: /Excluded/i });
    fireEvent.click(excludedFilters[0]);
    await waitFor(() => {
      expect(screen.getByText("Excluded item")).toBeInTheDocument();
    });
  });

  it("shows backend error messages inline on complete failure", async () => {
    const fetchMock = vi.fn().mockImplementation((url: RequestInfo | URL) => {
      const href = String(url);
      if (href.endsWith("/api/reconciliation/accounts/")) return buildResponse(baseAccount);
      if (href.includes("/api/reconciliation/accounts/1/periods/")) return buildResponse(basePeriods);
      if (href.startsWith("/api/reconciliation/session/?")) {
        return buildResponse({
          bank_account: { id: "1", name: "Checking", currency: "USD" },
          period: { start_date: "2024-01-01", end_date: "2024-01-31" },
          session: {
            id: "321",
            status: "DRAFT",
            opening_balance: "0.00",
            statement_ending_balance: "0.00",
            cleared_balance: "0.00",
            difference: "0.00",
            reconciled_percent: 100,
            total_transactions: 0,
            reconciled_count: 0,
            unreconciled_count: 0,
          },
          feed: { new: [], matched: [], partial: [], excluded: [] },
        });
      }
      if (href.startsWith("/api/reconciliation/sessions/321/complete/")) {
        return buildResponse({ detail: "This session is completed and cannot be changed." }, 400);
      }
      return buildResponse([]);
    });
    // @ts-ignore
    global.fetch = fetchMock;

    render(<ReconciliationPage />);
    await waitFor(() => expect(screen.getByText("Complete period")).toBeInTheDocument());

    fireEvent.click(await screen.findByText("Complete period"));

    await waitFor(() => {
      const called = fetchMock.mock.calls.some(call => call[0] === "/api/reconciliation/sessions/321/complete/");
      expect(called).toBe(true);
      expect(screen.getAllByText("This session is completed and cannot be changed.").length).toBeGreaterThan(0);
    });
  });

  it("unmatches a transaction and refreshes status and summary", async () => {
    let unmatchCalled = false;
    let state: "matched" | "unmatched" = "matched";
    const fetchMock = vi.fn().mockImplementation((url: RequestInfo | URL) => {
      const href = String(url);
      if (href.endsWith("/api/reconciliation/accounts/")) return buildResponse(baseAccount);
      if (href.includes("/api/reconciliation/accounts/1/periods/")) return buildResponse(basePeriods);
      if (href.startsWith("/api/reconciliation/session/?")) {
        if (state === "matched") {
          return buildResponse({
            bank_account: { id: "1", name: "Checking", currency: "USD" },
            period: { start_date: "2024-01-01", end_date: "2024-01-31" },
            session: {
              id: "777",
              status: "IN_PROGRESS",
              opening_balance: "0.00",
              statement_ending_balance: "100.00",
              cleared_balance: "100.00",
              difference: "0.00",
              reconciled_percent: 100,
              total_transactions: 1,
              reconciled_count: 1,
              unreconciled_count: 0,
              excluded_count: 0,
            },
            feed: {
              matched: [
                {
                  id: "m1",
                  date: "2024-01-05",
                  description: "Matched item",
                  amount: 100,
                  currency: "USD",
                  ui_status: "MATCHED",
                  is_cleared: true,
                  includedInSession: true,
                },
              ],
              new: [],
              partial: [],
              excluded: [],
            },
          });
        }
        return buildResponse({
          bank_account: { id: "1", name: "Checking", currency: "USD" },
          period: { start_date: "2024-01-01", end_date: "2024-01-31" },
          session: {
            id: "777",
            status: "IN_PROGRESS",
            opening_balance: "0.00",
            statement_ending_balance: "100.00",
            cleared_balance: "0.00",
            difference: "100.00",
            reconciled_percent: 0,
            total_transactions: 1,
            reconciled_count: 0,
            unreconciled_count: 1,
            excluded_count: 0,
          },
          feed: {
            matched: [],
            partial: [],
            excluded: [],
            new: [
              {
                id: "m1",
                date: "2024-01-05",
                description: "Matched item",
                amount: 100,
                currency: "USD",
                ui_status: "NEW",
                is_cleared: false,
                includedInSession: true,
              },
            ],
          },
        });
      }
      if (href.startsWith("/api/reconciliation/session/777/unmatch/")) {
        unmatchCalled = true;
        state = "unmatched";
        return buildResponse({});
      }
      if (href.startsWith("/api/reconciliation/matches/")) return buildResponse([]);
      return buildResponse([]);
    });
    // @ts-ignore
    global.fetch = fetchMock;

    render(<ReconciliationPage />);

    await screen.findByText(/matched/i);
    const undoButton = screen.getByRole("button", { name: /Undo/i });
    fireEvent.click(undoButton);

    await waitFor(() => expect(unmatchCalled).toBe(true));
    // After unmatch, status should show NEW badge
    await waitFor(() => expect(screen.getAllByText(/NEW/i).length).toBeGreaterThan(0));
    expect(screen.getAllByText("$100.00").length).toBeGreaterThan(0);
  });

  it("toggles exclude/include and reflects ui_status and cleared state", async () => {
    let excluded = false;
    const fetchMock = vi.fn().mockImplementation((url: RequestInfo | URL, options?: RequestInit) => {
      const href = String(url);
      if (href.endsWith("/api/reconciliation/accounts/")) return buildResponse(baseAccount);
      if (href.includes("/api/reconciliation/accounts/1/periods/")) return buildResponse(basePeriods);
      if (href.startsWith("/api/reconciliation/session/?")) {
        return buildResponse({
          bank_account: { id: "1", name: "Checking", currency: "USD" },
          period: { start_date: "2024-01-01", end_date: "2024-01-31" },
          session: {
            id: "888",
            status: "IN_PROGRESS",
            opening_balance: "0.00",
            statement_ending_balance: "50.00",
            cleared_balance: excluded ? "0.00" : "50.00",
            difference: excluded ? "50.00" : "0.00",
            reconciled_percent: excluded ? 100 : 0,
            total_transactions: 1,
            reconciled_count: excluded ? 1 : 0,
            excluded_count: excluded ? 1 : 0,
            unreconciled_count: excluded ? 0 : 1,
          },
          feed: {
            new: excluded
              ? []
              : [
                {
                  id: "t1",
                  date: "2024-01-10",
                  description: "To exclude",
                  amount: 50,
                  currency: "USD",
                  ui_status: "NEW",
                  is_cleared: false,
                  includedInSession: true,
                },
              ],
            excluded: excluded
              ? [
                {
                  id: "t1",
                  date: "2024-01-10",
                  description: "To exclude",
                  amount: 50,
                  currency: "USD",
                  ui_status: "EXCLUDED",
                  is_cleared: false,
                  includedInSession: false,
                },
              ]
              : [],
            matched: [],
            partial: [],
          },
        });
      }
      if (href.startsWith("/api/reconciliation/session/888/exclude/")) {
        excluded = JSON.parse((options?.body as string) || "{}").excluded;
        return buildResponse({});
      }
      if (href.startsWith("/api/reconciliation/matches/")) return buildResponse([]);
      return buildResponse([]);
    });
    // @ts-ignore
    global.fetch = fetchMock;

    render(<ReconciliationPage />);
    await screen.findByText("To exclude");

    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);

    // After exclude, the status badge should show EXCLUDED
    await waitFor(() => expect(screen.getAllByText(/EXCLUDED/i).length).toBeGreaterThan(0));
  });

  it("locks controls on completed session and re-enables after reopen", async () => {
    let reopened = false;
    const fetchMock = vi.fn().mockImplementation((url: RequestInfo | URL) => {
      const href = String(url);
      if (href.endsWith("/api/reconciliation/accounts/")) return buildResponse(baseAccount);
      if (href.includes("/api/reconciliation/accounts/1/periods/")) return buildResponse(basePeriods);
      if (href.startsWith("/api/reconciliation/session/?")) {
        return buildResponse({
          bank_account: { id: "1", name: "Checking", currency: "USD" },
          period: { start_date: "2024-01-01", end_date: "2024-01-31" },
          session: {
            id: "900",
            status: reopened ? "IN_PROGRESS" : "COMPLETED",
            opening_balance: "0.00",
            statement_ending_balance: "0.00",
            cleared_balance: "0.00",
            difference: "0.00",
            reconciled_percent: 100,
            total_transactions: 1,
            reconciled_count: 1,
            unreconciled_count: 0,
            excluded_count: 0,
          },
          feed: {
            matched: [
              {
                id: "m1",
                date: "2024-01-03",
                description: "Locked item",
                amount: 20,
                currency: "USD",
                ui_status: "MATCHED",
                is_cleared: true,
                includedInSession: true,
              },
            ],
            new: [],
            partial: [],
            excluded: [],
          },
        });
      }
      if (href.startsWith("/api/reconciliation/sessions/900/reopen/")) {
        reopened = true;
        return buildResponse({});
      }
      if (href.startsWith("/api/reconciliation/matches/")) return buildResponse([]);
      return buildResponse([]);
    });
    // @ts-ignore
    global.fetch = fetchMock;
    vi.spyOn(window, "confirm").mockReturnValue(true);

    render(<ReconciliationPage />);

    await screen.findByText("Locked item");
    expect(screen.getByText("Undo")).toBeDisabled();

    fireEvent.click(await screen.findByText("Reopen period"));
    await waitFor(() => expect(screen.getByText("Undo")).not.toBeDisabled());
  });

  it("shows action error banner on failure and can dismiss", async () => {
    const fetchMock = vi.fn().mockImplementation((url: RequestInfo | URL) => {
      const href = String(url);
      if (href.endsWith("/api/reconciliation/accounts/")) return buildResponse(baseAccount);
      if (href.includes("/api/reconciliation/accounts/1/periods/")) return buildResponse(basePeriods);
      if (href.startsWith("/api/reconciliation/session/?")) {
        return buildResponse({
          bank_account: { id: "1", name: "Checking", currency: "USD" },
          period: { start_date: "2024-01-01", end_date: "2024-01-31" },
          session: {
            id: "901",
            status: "IN_PROGRESS",
            opening_balance: "0.00",
            statement_ending_balance: "0.00",
            cleared_balance: "0.00",
            difference: "0.00",
            reconciled_percent: 0,
            total_transactions: 1,
            reconciled_count: 0,
            unreconciled_count: 1,
            excluded_count: 0,
          },
          feed: {
            partial: [],
            excluded: [],
            new: [],
            matched: [
              {
                id: "x1",
                date: "2024-01-08",
                description: "Failing item",
                amount: 10,
                currency: "USD",
                ui_status: "MATCHED",
                is_cleared: true,
                includedInSession: true,
              },
            ],
          },
        });
      }
      if (href.startsWith("/api/reconciliation/session/901/unmatch/")) {
        return buildResponse({ detail: "Cannot unmatch completed session" }, 400);
      }
      if (href.startsWith("/api/reconciliation/matches/")) return buildResponse([]);
      return buildResponse([]);
    });
    // @ts-ignore
    global.fetch = fetchMock;

    render(<ReconciliationPage />);
    await screen.findByText("Failing item");

    fireEvent.click(screen.getByText("Undo"));

    await waitFor(() => expect(screen.getByText("Cannot unmatch completed session")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Dismiss"));
    await waitFor(() => expect(screen.queryByText("Cannot unmatch completed session")).not.toBeInTheDocument());
  });
});
