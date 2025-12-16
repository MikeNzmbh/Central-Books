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
    fetchFeatureFlags: vi.fn().mockResolvedValue([]),
    updateUser: vi.fn(),
    updateWorkspace: vi.fn(),
    updateFeatureFlag: vi.fn(),
    updateSupportTicket: vi.fn(),
    startImpersonation: vi.fn().mockResolvedValue({ redirect_url: "" }),
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
        user: { email: "ops@cernbooks.com", is_staff: true },
      }),
    });

    vi.stubGlobal("fetch", mockFetch as unknown as typeof fetch);

    render(
      <AuthProvider>
        <AdminApp />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByText(/Clover Books control center/i)).toBeInTheDocument());
  });

  it("renders admin view for internal routes without customer navigation", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        authenticated: true,
        user: { email: "ops@cernbooks.com", is_staff: true },
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
      expect(screen.getByText(/Clover Books control center/i)).toBeInTheDocument()
    );
    expect(screen.queryByText(/Products & Services/i)).not.toBeInTheDocument();
  });
});
