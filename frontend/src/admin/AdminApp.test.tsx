import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { AdminApp } from "./AdminApp";
import { AdminRoutes } from "./AdminRoutes";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "../contexts/AuthContext";

vi.mock("./api", () => {
  const mockMetrics = {
    active_users_30d: 5,
    active_users_30d_change_pct: 10,
    unreconciled_transactions: 2,
    unreconciled_transactions_older_60d: 1,
    unbalanced_journal_entries: 0,
    api_error_rate_1h_pct: 0.1,
    api_p95_response_ms_1h: 120,
    ai_flagged_open_issues: 0,
    failed_invoice_emails_24h: 0,
    workspaces_health: [],
  };
  return {
    fetchOverviewMetrics: vi.fn().mockResolvedValue(mockMetrics),
    fetchBankAccounts: vi.fn().mockResolvedValue({ results: [] }),
    fetchWorkspaces: vi.fn().mockResolvedValue({ results: [] }),
    fetchUsers: vi.fn().mockResolvedValue({ results: [] }),
    fetchAuditLog: vi.fn().mockResolvedValue({ results: [] }),
    fetchSupportTickets: vi.fn().mockResolvedValue({ results: [] }),
    addSupportTicketNote: vi.fn().mockResolvedValue({}),
    createSupportTicket: vi.fn().mockResolvedValue({}),
    fetchFeatureFlags: vi.fn().mockResolvedValue([]),
    fetchReconciliationMetrics: vi.fn().mockResolvedValue({
      total_unreconciled: 0,
      aging: { "0_30_days": 0, "30_60_days": 0, "60_90_days": 0, over_90_days: 0 },
      top_workspaces: [],
    }),
    fetchLedgerHealth: vi.fn().mockResolvedValue({
      summary: { unbalanced_entries: 0, orphan_accounts: 0, suspense_with_balance: 0 },
      unbalanced_entries: [],
      orphan_accounts: [],
      suspense_balances: [],
    }),
    fetchInvoicesAudit: vi.fn().mockResolvedValue({ summary: { total: 0, draft: 0, sent: 0, paid: 0, issues: 0 }, status_distribution: {}, recent_issues: [] }),
    fetchExpensesAudit: vi.fn().mockResolvedValue({
      summary: { total_expenses: 0, total_receipts: 0, uncategorized: 0, pending_receipts: 0 },
      expense_distribution: {},
      receipt_distribution: {},
      top_workspaces: [],
    }),
    fetchApprovals: vi.fn().mockResolvedValue({ results: [], count: 0, summary: { total_pending: 0, total_today: 0, high_risk_pending: 0, avg_response_minutes_24h: null } }),
    createApprovalRequest: vi.fn().mockResolvedValue({ id: "req-1", status: "PENDING" }),
    approveRequest: vi.fn().mockResolvedValue({ id: "req-1", status: "APPROVED" }),
    rejectRequest: vi.fn().mockResolvedValue({ id: "req-1", status: "REJECTED" }),
    breakGlassApproval: vi.fn().mockResolvedValue({ success: true, expires_at: "2024-01-01T00:00:00Z" }),
    updateUser: vi.fn(),
    updateWorkspace: vi.fn(),
    updateFeatureFlag: vi.fn(),
    updateSupportTicket: vi.fn(),
    startImpersonation: vi.fn().mockResolvedValue({ redirect_url: "" }),
    resetPassword: vi.fn().mockResolvedValue({ approval_required: true, approval_request_id: "req-1", approval_status: "PENDING" }),
  };
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("AdminApp", () => {
  it("renders the control center heading", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        authenticated: true,
        user: {
          email: "ops@cernbooks.com",
          internalAdmin: {
            role: "OPS",
            canAccessInternalAdmin: true,
            canManageAdminUsers: false,
            canGrantSuperadmin: false,
            adminPanelAccess: true,
          },
        },
      }),
    });

    vi.stubGlobal("fetch", mockFetch as unknown as typeof fetch);

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/"]}>
          <AdminApp />
        </MemoryRouter>
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByText(/Clover Books · Admin/i)).toBeInTheDocument());
  });

  it("renders admin view for internal routes without customer navigation", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        authenticated: true,
        user: {
          email: "ops@cernbooks.com",
          internalAdmin: {
            role: "OPS",
            canAccessInternalAdmin: true,
            canManageAdminUsers: false,
            canGrantSuperadmin: false,
            adminPanelAccess: true,
          },
        },
      }),
    });

    vi.stubGlobal("fetch", mockFetch as unknown as typeof fetch);

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/internal-admin"]}>
          <AdminRoutes />
        </MemoryRouter>
      </AuthProvider>
    );

    await waitFor(() =>
      expect(screen.getByText(/Clover Books · Admin/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(/Products & Services/i)).not.toBeInTheDocument();
  });

  it("hides Employees nav for non-managers", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        authenticated: true,
        user: {
          email: "support@cernbooks.com",
          internalAdmin: {
            role: "SUPPORT",
            canAccessInternalAdmin: true,
            canManageAdminUsers: false,
            canGrantSuperadmin: false,
            adminPanelAccess: true,
          },
        },
      }),
    });
    vi.stubGlobal("fetch", mockFetch as unknown as typeof fetch);

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/"]}>
          <AdminApp />
        </MemoryRouter>
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByText(/Clover Books · Admin/i)).toBeInTheDocument());
    expect(screen.queryByText(/^Employees$/i)).not.toBeInTheDocument();
  });

  it("shows Not authorized on /employees for non-managers", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        authenticated: true,
        user: {
          email: "support@cernbooks.com",
          internalAdmin: {
            role: "SUPPORT",
            canAccessInternalAdmin: true,
            canManageAdminUsers: false,
            canGrantSuperadmin: false,
            adminPanelAccess: true,
          },
        },
      }),
    });
    vi.stubGlobal("fetch", mockFetch as unknown as typeof fetch);

    render(
      <AuthProvider>
        <MemoryRouter initialEntries={["/employees"]}>
          <AdminApp />
        </MemoryRouter>
      </AuthProvider>
    );

    await waitFor(() => expect(screen.getByText(/Not authorized/i)).toBeInTheDocument());
  });
});
