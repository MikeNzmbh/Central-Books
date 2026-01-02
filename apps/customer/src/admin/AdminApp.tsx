import React, { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  fetchOverviewMetrics,
  fetchReconciliationMetrics,
  fetchLedgerHealth,
  fetchInvoicesAudit,
  fetchExpensesAudit,
  type OverviewMetrics,
  type ReconciliationMetrics,
  type LedgerHealth,
  type InvoicesAudit,
  type ExpensesAudit,
} from "./api";
import { UsersSection } from "./UsersSection";
import { WorkspacesSection } from "./WorkspacesSection";
import { BankingSection } from "./BankingSection";
import { AuditLogSection } from "./AuditLogSection";
import { SupportSection } from "./SupportSection";
import { ApprovalsSection } from "./ApprovalsSection";
import { OverviewSection } from "./OverviewSection";
import { EmployeesSection } from "./EmployeesSection";
import { Card, SimpleTable, StatusPill, cn } from "./AdminUI";
import { useAuth } from "../contexts/AuthContext";

type Role = "support" | "finance" | "engineer" | "superadmin";

type NavSectionId =
  | "overview"
  | "employees"
  | "users"
  | "support"
  | "approvals"
  | "workspaces"
  | "banking"
  | "reconciliation"
  | "ledger"
  | "invoices"
  | "expenses"
  | "ai-monitoring"
  | "feature-flags"
  | "settings"
  | "logs";

interface NavItem {
  id: NavSectionId;
  label: string;
  description?: string;
}

interface Kpi {
  id: string;
  label: string;
  value: string;
  delta?: string;
  tone?: "good" | "bad" | "neutral" | "warning";
}

interface FeatureFlagRow {
  key: string;
  description: string;
  enabled: boolean;
  guarded?: boolean;
}

const navGroups: { label: string; items: NavItem[] }[] = [
  {
    label: "Main",
    items: [
      { id: "overview", label: "Overview", description: "System health & KPIs" },
      { id: "users", label: "Users", description: "Manage accounts & access" },
      { id: "employees", label: "Employees", description: "Admin access & roles" },
      { id: "support", label: "Support", description: "Tickets & customer issues" },
      { id: "approvals", label: "Approvals", description: "Maker-Checker workflow" },
      { id: "logs", label: "Audit & logs", description: "Recent admin activity" },
    ],
  },
  {
    label: "Accounting",
    items: [
      { id: "workspaces", label: "Workspaces", description: "Tenant books & health" },
      { id: "banking", label: "Banking", description: "Bank feeds & imports" },
      { id: "reconciliation", label: "Reconciliation", description: "Unreconciled items" },
      { id: "ledger", label: "Ledger health", description: "Trial balance & anomalies" },
      { id: "invoices", label: "Invoices", description: "Global sales audit" },
      { id: "expenses", label: "Expenses", description: "Purchases & receipts" },
    ],
  },
  {
    label: "Intelligence & Ops",
    items: [
      { id: "ai-monitoring", label: "AI monitoring", description: "Agent reports & metrics" },
      { id: "feature-flags", label: "Feature flags", description: "Rollouts & experiments" },
      { id: "settings", label: "Settings", description: "Security & config" },
    ],
  },
];

const mockFlags: FeatureFlagRow[] = [
  {
    key: "new_reconciliation_v2",
    description: "Enable reconciliation v2 engine for selected tenants.",
    enabled: true,
    guarded: true,
  },
  {
    key: "ai_companion_shadow",
    description: "Embed read-only AI companion on dashboard.",
    enabled: false,
  },
  {
    key: "pdf_report_shell_v1",
    description: "Use universal PDF/print shell for all reports.",
    enabled: true,
  },
];

const LogoutButton: React.FC = () => {
  const { logout } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    try {
      await logout();
    } catch (error) {
      console.error("Logout failed:", error);
      setIsLoggingOut(false);
    }
  };

  return (
    <button
      onClick={handleLogout}
      disabled={isLoggingOut}
      className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-sm disabled:opacity-50 transition flex items-center justify-center gap-2"
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
        <polyline points="16 17 21 12 16 7" />
        <line x1="21" x2="9" y1="12" y2="12" />
      </svg>
      {isLoggingOut ? "Logging out..." : "Log out"}
    </button>
  );
};

const RoleBadge: React.FC<{ role: Role }> = ({ role }) => {
  const map: Record<Role, string> = {
    support: "bg-sky-50 text-sky-700 border-sky-200",
    finance: "bg-emerald-50 text-emerald-700 border-emerald-200",
    engineer: "bg-indigo-50 text-indigo-700 border-indigo-200",
    superadmin: "bg-rose-50 text-rose-700 border-rose-200",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
        map[role]
      )}
    >
      {role}
    </span>
  );
};

const KpiCard: React.FC<{ kpi: Kpi }> = ({ kpi }) => {
  const toneMap: Record<NonNullable<Kpi["tone"]>, string> = {
    good: "text-emerald-700",
    bad: "text-rose-700",
    neutral: "text-slate-700",
    warning: "text-amber-700",
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 sm:px-5 sm:py-4 flex flex-col gap-2 shadow-sm min-h-[120px]">
      <div className="flex flex-col gap-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 leading-tight">{kpi.label}</p>
        {kpi.delta && (
          <span className={cn("text-[11px] font-medium leading-tight", kpi.tone && toneMap[kpi.tone])}>{kpi.delta}</span>
        )}
      </div>
      <p className={cn("text-xl sm:text-2xl font-semibold mt-auto", kpi.tone && toneMap[kpi.tone])}>{kpi.value}</p>
    </div>
  );
};




const ReconciliationSection: React.FC = () => {
  const [data, setData] = useState<ReconciliationMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchReconciliationMetrics()
      .then(setData)
      .catch((e) => setError(e?.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Reconciliation tracking</h2>
          <p className="text-sm text-slate-600 max-w-xl">
            High-friction areas in matching and period completion. This view exists solely for internal staff –
            end users never see this lens.
          </p>
        </div>
      </header>
      {loading ? (
        <Card><p className="text-sm text-slate-600">Loading reconciliation metrics…</p></Card>
      ) : error ? (
        <Card><p className="text-sm text-rose-700">Error: {error}</p></Card>
      ) : data ? (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Total unreconciled</p>
              <p className="text-2xl font-semibold text-slate-900 mt-1">{data.total_unreconciled}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">0-30 days</p>
              <p className="text-2xl font-semibold text-emerald-700 mt-1">{data.aging["0_30_days"]}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">30-60 days</p>
              <p className="text-2xl font-semibold text-amber-700 mt-1">{data.aging["30_60_days"]}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Over 60 days</p>
              <p className="text-2xl font-semibold text-rose-700 mt-1">{data.aging["60_90_days"] + data.aging.over_90_days}</p>
            </div>
          </div>
          <Card title="Top workspaces by unreconciled" subtitle="Workspaces with the most pending items.">
            {data.top_workspaces.length ? (
              <SimpleTable
                headers={["Workspace", "Unreconciled"]}
                rows={data.top_workspaces.map((w) => [
                  <span key="n" className="text-sm text-slate-800">{w.name}</span>,
                  <span key="c" className="text-sm font-semibold text-slate-900">{w.unreconciled_count}</span>,
                ])}
              />
            ) : (
              <p className="text-sm text-slate-600">No unreconciled transactions found.</p>
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
};

const LedgerSection: React.FC = () => {
  const [data, setData] = useState<LedgerHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLedgerHealth()
      .then(setData)
      .catch((e) => setError(e?.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Ledger health</h2>
          <p className="text-sm text-slate-600 max-w-xl">
            Trial balance anomalies, unbalanced entries, orphan accounts, and suspense balances. All purely internal
            diagnostics.
          </p>
        </div>
      </header>
      {loading ? (
        <Card><p className="text-sm text-slate-600">Loading ledger health…</p></Card>
      ) : error ? (
        <Card><p className="text-sm text-rose-700">Error: {error}</p></Card>
      ) : data ? (
        <>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Unbalanced entries</p>
              <p className={cn("text-2xl font-semibold mt-1", data.summary.unbalanced_entries > 0 ? "text-rose-700" : "text-emerald-700")}>
                {data.summary.unbalanced_entries}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Orphan accounts</p>
              <p className={cn("text-2xl font-semibold mt-1", data.summary.orphan_accounts > 0 ? "text-amber-700" : "text-slate-700")}>
                {data.summary.orphan_accounts}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Suspense with balance</p>
              <p className={cn("text-2xl font-semibold mt-1", data.summary.suspense_with_balance > 0 ? "text-amber-700" : "text-slate-700")}>
                {data.summary.suspense_with_balance}
              </p>
            </div>
          </div>
          {data.unbalanced_entries.length > 0 && (
            <Card title="Unbalanced entries" subtitle="Journal entries where debits ≠ credits.">
              <SimpleTable
                headers={["Workspace", "Date", "Description", "Difference"]}
                rows={data.unbalanced_entries.slice(0, 10).map((e) => [
                  <span key="w" className="text-sm text-slate-800">{e.workspace}</span>,
                  <span key="d" className="text-xs text-slate-600">{e.date || "—"}</span>,
                  <span key="desc" className="text-xs text-slate-700 max-w-[200px] truncate">{e.description || "—"}</span>,
                  <span key="diff" className="text-sm font-semibold text-rose-700">${e.difference.toFixed(2)}</span>,
                ])}
              />
            </Card>
          )}
        </>
      ) : null}
    </div>
  );
};

const InvoicesSection: React.FC = () => {
  const [data, setData] = useState<InvoicesAudit | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchInvoicesAudit()
      .then(setData)
      .catch((e) => setError(e?.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Invoices (global audit)</h2>
          <p className="text-sm text-slate-600 max-w-xl">
            Cross-tenant visibility into invoice status, failed sends, and potential duplicate or anomalous documents.
          </p>
        </div>
      </header>
      {loading ? (
        <Card><p className="text-sm text-slate-600">Loading invoices audit…</p></Card>
      ) : error ? (
        <Card><p className="text-sm text-rose-700">Error: {error}</p></Card>
      ) : data ? (
        <>
          <div className="grid gap-3 md:grid-cols-5">
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Total</p>
              <p className="text-2xl font-semibold text-slate-900 mt-1">{data.summary.total}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Draft</p>
              <p className="text-2xl font-semibold text-slate-600 mt-1">{data.summary.draft}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Sent</p>
              <p className="text-2xl font-semibold text-amber-700 mt-1">{data.summary.sent}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Paid</p>
              <p className="text-2xl font-semibold text-emerald-700 mt-1">{data.summary.paid}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Issues</p>
              <p className={cn("text-2xl font-semibold mt-1", data.summary.issues > 0 ? "text-rose-700" : "text-slate-600")}>
                {data.summary.issues}
              </p>
            </div>
          </div>
          {data.recent_issues.length > 0 && (
            <Card title="Recent issues" subtitle="Invoices with failed, rejected, or error status.">
              <SimpleTable
                headers={["Workspace", "Customer", "Status", "Total"]}
                rows={data.recent_issues.slice(0, 10).map((inv) => [
                  <span key="w" className="text-sm text-slate-800">{inv.workspace}</span>,
                  <span key="c" className="text-sm text-slate-700">{inv.customer}</span>,
                  <StatusPill key="s" tone="warning" label={inv.status} />,
                  <span key="t" className="text-sm font-semibold text-slate-900">${inv.total.toFixed(2)}</span>,
                ])}
              />
            </Card>
          )}
        </>
      ) : null}
    </div>
  );
};

const ExpensesSection: React.FC = () => {
  const [data, setData] = useState<ExpensesAudit | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchExpensesAudit()
      .then(setData)
      .catch((e) => setError(e?.message || "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Expenses & receipts</h2>
          <p className="text-sm text-slate-600 max-w-xl">
            Spot mis-categorized spend, receipt anomalies, and FX conversion issues from a single, internal lens.
          </p>
        </div>
      </header>
      {loading ? (
        <Card><p className="text-sm text-slate-600">Loading expenses audit…</p></Card>
      ) : error ? (
        <Card><p className="text-sm text-rose-700">Error: {error}</p></Card>
      ) : data ? (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Total expenses</p>
              <p className="text-2xl font-semibold text-slate-900 mt-1">{data.summary.total_expenses}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Total receipts</p>
              <p className="text-2xl font-semibold text-slate-900 mt-1">{data.summary.total_receipts}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Uncategorized</p>
              <p className={cn("text-2xl font-semibold mt-1", data.summary.uncategorized > 0 ? "text-amber-700" : "text-slate-600")}>
                {data.summary.uncategorized}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Pending receipts</p>
              <p className={cn("text-2xl font-semibold mt-1", data.summary.pending_receipts > 0 ? "text-amber-700" : "text-slate-600")}>
                {data.summary.pending_receipts}
              </p>
            </div>
          </div>
          <Card title="Top workspaces by expense count" subtitle="Workspaces with the most expense entries.">
            {data.top_workspaces.length ? (
              <SimpleTable
                headers={["Workspace", "Count", "Total"]}
                rows={data.top_workspaces.slice(0, 10).map((w) => [
                  <span key="n" className="text-sm text-slate-800">{w.name}</span>,
                  <span key="c" className="text-sm text-slate-700">{w.count}</span>,
                  <span key="t" className="text-sm font-semibold text-slate-900">${w.total.toFixed(2)}</span>,
                ])}
              />
            ) : (
              <p className="text-sm text-slate-600">No expense data found.</p>
            )}
          </Card>
        </>
      ) : null}
    </div>
  );
};


const AiMonitoringSection: React.FC = () => (
  <div className="space-y-4">
    <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">AI monitoring & metrics</h2>
        <p className="text-sm text-slate-600 max-w-xl">
          Direct window into the master monitoring agent: metrics JSON, last run, domain coverage, and alerts.
        </p>
      </div>
      <div className="flex gap-2">
        <button className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-sm">
          View latest JSON
        </button>
        <button className="rounded-full bg-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-900 hover:bg-slate-100 shadow-sm">
          Run analysis now
        </button>
      </div>
    </header>
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1.4fr)]">
      <Card title="Domains covered" subtitle="Seven domains, three runs per day.">
        <ul className="space-y-2 text-sm text-slate-700">
          <li>• Product & Engineering health</li>
          <li>• Ledger & Accounting integrity</li>
          <li>• Banking & Reconciliation hygiene</li>
          <li>• Tax & FX consistency</li>
          <li>• Business & Revenue pacing</li>
          <li>• Marketing & Traffic patterns</li>
          <li>• Support & Feedback signals</li>
        </ul>
      </Card>
      <Card title="Last run" subtitle="11:02 UTC · duration 3.4s">
        <p className="text-sm text-slate-700 mb-2">Snapshot from latest agent run:</p>
        <ul className="space-y-1.5 text-xs text-slate-700">
          <li>• No unbalanced entries across tenants.</li>
          <li>• 2 bank feeds with elevated error_rate_pct &gt; 3%.</li>
          <li>• 3 invoices with tax calculation anomalies within tolerance.</li>
          <li>• Response p95 steady at 186ms.</li>
        </ul>
      </Card>
    </div>
  </div>
);

const FeatureFlagsSection: React.FC<{ role: Role }> = ({ role }) => {
  const canToggleGuarded = role === "superadmin";

  return (
    <div className="space-y-4">
      <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Feature flags</h2>
          <p className="text-sm text-slate-600 max-w-xl">
            Safe rollouts for new modules, engines, and experiments – all toggled from one calm surface.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-emerald-700">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          <span>Live in production</span>
        </div>
      </header>
      <Card title="Flags">
        <SimpleTable
          headers={["Key", "Description", "Guard", "State"]}
          rows={mockFlags.map((flag) => [
            <span key="k" className="text-xs text-slate-800 font-mono">
              {flag.key}
            </span>,
            <span key="d" className="text-xs text-slate-700">
              {flag.description}
            </span>,
            <span key="g" className="text-xs text-slate-600">
              {flag.guarded ? "superadmin" : "default"}
            </span>,
            <label
              key="t"
              className={cn(
                "inline-flex items-center gap-2 text-xs",
                flag.guarded && !canToggleGuarded && "opacity-50 cursor-not-allowed"
              )}
            >
              <div
                className={cn(
                  "flex h-4 w-7 items-center rounded-full border border-slate-300 bg-slate-100 px-[2px] transition",
                  flag.enabled && "border-emerald-400 bg-emerald-50"
                )}
              >
                <div
                  className={cn(
                    "h-3 w-3 rounded-full bg-slate-400 shadow transition-transform",
                    flag.enabled && "translate-x-3 bg-emerald-500"
                  )}
                />
              </div>
              <span className="text-slate-800">{flag.enabled ? "Enabled" : "Disabled"}</span>
            </label>,
          ])}
        />
      </Card>
    </div>
  );
};

const SettingsSection: React.FC = () => (
  <div className="space-y-4">
    <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Admin settings</h2>
        <p className="text-sm text-slate-600 max-w-xl">
          Security posture, SSO, maintenance windows, and environment introspection. Internal-only; changes are
          fully audited.
        </p>
      </div>
      <button className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-sm">
        View audit config
      </button>
    </header>
    <Card title="Environment">
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-y-2 text-sm text-slate-800">
        <div>
          <dt className="text-xs text-slate-500">Environment</dt>
          <dd>production-eu-1</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Deploy SHA</dt>
          <dd className="font-mono text-xs text-slate-800">a7b9e23</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">AI model</dt>
          <dd>gpt-5.1-monitoring</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">Admin SSO</dt>
          <dd>Google Workspace (@cernbooks.com)</dd>
        </div>
      </dl>
    </Card>
  </div>
);

const LogsSection: React.FC = () => (
  <div className="space-y-4">
    <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Audit & logs</h2>
        <p className="text-sm text-slate-600 max-w-xl">
          Append-only trail of admin actions across users, workspaces, and configuration.
        </p>
      </div>
      <button className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-sm">
        Export log
      </button>
    </header>
    <AuditLogSection />
  </div>
);

const TopBar: React.FC<{ currentSection: NavSectionId }> = ({ currentSection }) => {
  const sectionLabel = navGroups
    .flatMap((g) => g.items)
    .find((i) => i.id === currentSection)?.label;

  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="flex items-center justify-between px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700 text-sm font-semibold">
            CB
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Clover Books · Admin</p>
            <p className="text-xs text-slate-700">{sectionLabel ?? "Overview"}</p>
          </div>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-700">
          <div className="hidden sm:flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.25)]" />
            <span>Prod · eu-central-1</span>
          </div>
          <button className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50 shadow-sm">
            View error traces
          </button>
        </div>
      </div>
    </header>
  );
};

const Sidebar: React.FC<{
  current: NavSectionId;
  onSelect: (id: NavSectionId) => void;
  canManageAdminUsers: boolean;
}> = ({ current, onSelect, canManageAdminUsers }) => {
  return (
    <aside className="hidden md:flex md:flex-col md:border-r md:border-slate-200 md:bg-white md:w-64 lg:w-72">
      <div className="px-4 pt-4 pb-3 border-b border-slate-200">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500 mb-1">Navigation</p>
        <p className="text-xs text-slate-600">Internal-only rails. Every action is accountable.</p>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-4">
        {navGroups.map((group) => (
          <div key={group.label}>
            <p className="px-2 text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500 mb-1.5">
              {group.label}
            </p>
            <div className="space-y-0.5">
              {group.items.map((item) => {

                const active = current === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => onSelect(item.id)}
                    className={cn(
                      "w-full rounded-xl px-2.5 py-2 text-left text-xs transition flex flex-col border",
                      active
                        ? "bg-white border-slate-200 text-slate-900 shadow-sm"
                        : "border-transparent text-slate-700 hover:bg-slate-100 hover:border-slate-200"
                    )}
                  >
                    <span className="font-semibold">{item.label}</span>
                    {item.description && (
                      <span className="text-[11px] text-slate-500 mt-0.5">{item.description}</span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
      <div className="border-t border-slate-200 px-4 py-3 space-y-3">
        <LogoutButton />
        <div className="text-[11px] text-slate-600">
          <p>Everything you do here leaves a trail.</p>
          <p className="mt-0.5">Built for internal ops · Clover Books</p>
        </div>
      </div>
    </aside>
  );
};

const roleFromAuth = (opts: { internalAdminRole?: string | null; isStaff?: boolean; isSuperuser?: boolean }): Role => {
  const r = (opts.internalAdminRole || "").toUpperCase();
  if (r === "SUPPORT") return "support";
  if (r === "OPS") return "finance";
  if (r === "ENGINEERING") return "engineer";
  if (r === "SUPERADMIN" || r === "PRIMARY_ADMIN") return "superadmin";
  if (opts.isSuperuser || opts.isStaff) return "superadmin";
  return "support";
};

const roleLevel = (role: Role) => (role === "superadmin" ? 4 : role === "engineer" ? 3 : role === "finance" ? 2 : 1);

export const AdminApp: React.FC = () => {
  const [current, setCurrent] = useState<NavSectionId>("overview");
  const { auth } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const canManageAdminUsers = Boolean(auth.user?.internalAdmin?.canManageAdminUsers);
  const canGrantSuperadmin = Boolean(auth.user?.internalAdmin?.canGrantSuperadmin);
  const role = useMemo(
    () =>
      roleFromAuth({
        internalAdminRole: auth.user?.internalAdmin?.role,
        isSuperuser: Boolean(auth.user?.isSuperuser ?? auth.user?.is_superuser),
      }),
    [auth.user?.internalAdmin?.role, auth.user?.isSuperuser, auth.user?.is_superuser]
  );

  const renderSection = () => {
    switch (current) {
      case "overview":
        return <OverviewSection />;
      case "users":
        return <UsersSection roleLevel={roleLevel(role)} />;
      case "employees":
        return <EmployeesSection canManageAdminUsers={canManageAdminUsers} canGrantSuperadmin={canGrantSuperadmin} />;
      case "support":
        return <SupportSection role={role} />;
      case "approvals":
        return <ApprovalsSection role={{ level: roleLevel(role) }} />;
      case "workspaces":
        return <WorkspacesSection roleLevel={roleLevel(role)} />;
      case "banking":
        return <BankingSection />;
      case "reconciliation":
        return <ReconciliationSection />;
      case "ledger":
        return <LedgerSection />;
      case "invoices":
        return <InvoicesSection />;
      case "expenses":
        return <ExpensesSection />;
      case "ai-monitoring":
        return <AiMonitoringSection />;
      case "feature-flags":
        return <FeatureFlagsSection role={role} />;
      case "settings":
        return <SettingsSection />;
      case "logs":
        return <LogsSection />;
      default:
        return <OverviewSection />;
    }
  };

  useEffect(() => {
    const path = (location.pathname || "/").replace(/^\/+/, "");
    const segment = path.split("/")[0] || "overview";
    const asSection = segment === "" ? "overview" : segment;
    const valid = navGroups.flatMap((g) => g.items).some((i) => i.id === asSection);
    if (valid && asSection !== current) {
      setCurrent(asSection as NavSectionId);
    }
  }, [location.pathname, current]);

  const handleSelect = (id: NavSectionId) => {
    setCurrent(id);
    navigate(id === "overview" ? "/" : `/${id}`);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
      <TopBar currentSection={current} />
      <div className="flex flex-1">
        <Sidebar current={current} onSelect={handleSelect} canManageAdminUsers={canManageAdminUsers} />
        <main className="flex-1 px-4 py-4 sm:px-6 lg:px-8">
          <div className="max-w-6xl mx-auto space-y-6 pb-8">{renderSection()}</div>
        </main>
      </div>
    </div>
  );
};
