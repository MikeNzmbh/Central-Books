import React, { useEffect, useMemo, useState } from "react";
import { fetchOverviewMetrics, type OverviewMetrics } from "./api";
import { UsersSection } from "./UsersSection";
import { WorkspacesSection } from "./WorkspacesSection";
import { BankingSection } from "./BankingSection";
import { AuditLogSection } from "./AuditLogSection";
import { SupportSection } from "./SupportSection";
import { FeatureFlagsSection } from "./FeatureFlagsSection";
import { Card, SimpleTable, StatusPill, cn } from "./AdminUI";

type Role = "support" | "finance" | "engineer" | "superadmin";

type NavSectionId =
  | "overview"
  | "users"
  | "support"
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
      { id: "support", label: "Support", description: "Tickets & customer issues" },
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
    <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 sm:px-5 sm:py-4 flex flex-col gap-2 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{kpi.label}</p>
        {kpi.delta && (
          <span className={cn("text-[11px] font-medium", kpi.tone && toneMap[kpi.tone])}>{kpi.delta}</span>
        )}
      </div>
      <p className={cn("text-xl sm:text-2xl font-semibold", kpi.tone && toneMap[kpi.tone])}>{kpi.value}</p>
    </div>
  );
};

const OverviewSection: React.FC<{ role: Role }> = ({ role }) => {
  const [metrics, setMetrics] = useState<OverviewMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetchOverviewMetrics()
      .then((data) => {
        if (!active) return;
        setMetrics(data);
        setError(null);
      })
      .catch((err) => {
        if (!active) return;
        setError(err?.message || "Unable to load metrics");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const kpis: Kpi[] = useMemo(() => {
    if (!metrics) return [];
    return [
      {
        id: "active-users",
        label: "Active users (30d)",
        value: String(metrics.active_users_30d ?? 0),
        delta: metrics.active_users_30d_change_pct
          ? `${metrics.active_users_30d_change_pct.toFixed(1)}% vs prev.`
          : undefined,
        tone: "good",
      },
      {
        id: "unreconciled",
        label: "Unreconciled transactions",
        value: String(metrics.unreconciled_transactions ?? 0),
        delta:
          metrics.unreconciled_transactions_older_60d !== undefined
            ? `+${metrics.unreconciled_transactions_older_60d} older than 60d`
            : undefined,
        tone: (metrics.unreconciled_transactions ?? 0) > 0 ? "bad" : "good",
      },
      {
        id: "unbalanced-je",
        label: "Unbalanced journal entries",
        value: String(metrics.unbalanced_journal_entries ?? 0),
        tone: (metrics.unbalanced_journal_entries ?? 0) === 0 ? "good" : "warning",
      },
      {
        id: "error-rate",
        label: "API error rate (1h)",
        value: `${metrics.api_error_rate_1h_pct ?? 0}%`,
        delta:
          metrics.api_p95_response_ms_1h !== undefined
            ? `p95 ${metrics.api_p95_response_ms_1h}ms`
            : undefined,
        tone: (metrics.api_error_rate_1h_pct ?? 0) > 1 ? "warning" : "neutral",
      },
      {
        id: "ai-open-issues",
        label: "AI-flagged open issues",
        value: String(metrics.ai_flagged_open_issues ?? 0),
        tone: (metrics.ai_flagged_open_issues ?? 0) > 0 ? "warning" : "good",
      },
      {
        id: "failed-invoices",
        label: "Failed invoice emails (24h)",
        value: String(metrics.failed_invoice_emails_24h ?? 0),
        tone: (metrics.failed_invoice_emails_24h ?? 0) > 0 ? "warning" : "good",
      },
    ];
  }, [metrics]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Internal admin</p>
          <h1 className="text-2xl sm:text-3xl font-semibold text-slate-900 mt-1">CERN Books control center</h1>
          <p className="text-sm text-slate-600 max-w-2xl mt-1.5">
            High-level view across tenants, ledgers, banking, and AI monitors. This panel is visible only to
            internal staff; all actions are fully audited.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-2 text-xs text-emerald-700">
            <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.25)]" />
            <span>Core systems healthy</span>
          </div>
          <RoleBadge role={role} />
        </div>
      </div>

      {loading ? (
        <Card>
          <p className="text-sm text-slate-600">Loading metrics…</p>
        </Card>
      ) : error ? (
        <Card>
          <p className="text-sm text-rose-700">Unable to load metrics: {error}</p>
        </Card>
      ) : (
        <>
          <div className="grid gap-3 sm:gap-4 md:grid-cols-3 xl:grid-cols-6">
            {kpis.map((kpi) => (
              <KpiCard key={kpi.id} kpi={kpi} />
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1.4fr)]">
            <Card
              title="Workspace health"
              subtitle="Tenants with reconciliation or ledger risks surface here first."
            >
              {metrics?.workspaces_health?.length ? (
                <SimpleTable
                  headers={["Workspace", "Owner", "Plan", "Unreconciled", "Ledger"]}
                  rows={metrics.workspaces_health.map((w) => [
                    <div key={w.id} className="flex flex-col">
                      <span className="text-sm font-semibold text-slate-900">{w.name}</span>
                    </div>,
                    <span key="owner" className="text-xs text-slate-700">
                      {w.owner_email}
                    </span>,
                    <span key="plan" className="text-xs text-slate-700">
                      {w.plan || "—"}
                    </span>,
                    <span key="unrec" className="text-xs text-slate-800">
                      {w.unreconciled_count ?? "—"}
                    </span>,
                    <div key="ledger" className="flex items-center gap-2">
                      <StatusPill
                        tone={w.ledger_status === "balanced" ? "good" : "warning"}
                        label={w.ledger_status === "balanced" ? "Balanced" : "Attention"}
                      />
                    </div>,
                  ])}
                />
              ) : (
                <p className="text-sm text-slate-600">No workspace health data yet.</p>
              )}
            </Card>

            <Card
              title="AI monitoring – latest issues"
              subtitle="Summaries from the master monitoring agent across all domains."
            >
              <div className="space-y-3 max-h-[280px] overflow-y-auto pr-1">
                <p className="text-sm text-slate-600">No recent AI issues.</p>
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
};

const ReconciliationSection: React.FC = () => {
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
        <div className="flex items-center gap-2 text-xs text-amber-700">
          <span className="h-2 w-2 rounded-full bg-amber-400" />
          <span>3 accounts with stalled periods</span>
        </div>
      </header>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1.6fr)]">
        <Card title="Risk buckets" subtitle="Breakdown by age of unreconciled bank lines.">
          <ul className="space-y-2 text-sm">
            <li className="flex items-center justify-between text-slate-700">
              <span>&lt; 30 days</span>
              <span className="font-semibold text-slate-900">151</span>
            </li>
            <li className="flex items-center justify-between text-slate-700">
              <span>30–60 days</span>
              <span className="font-semibold text-amber-700">47</span>
            </li>
            <li className="flex items-center justify-between text-slate-700">
              <span>60–90 days</span>
              <span className="font-semibold text-amber-700">21</span>
            </li>
            <li className="flex items-center justify-between text-slate-700">
              <span>90+ days</span>
              <span className="font-semibold text-rose-700">12</span>
            </li>
          </ul>
        </Card>

        <Card
          title="Accounts with stalled reconciliation"
          subtitle="Accounts where last completed period was > 60 days ago."
        >
          <SimpleTable
            headers={["Workspace", "Account", "Last completed", "Unreconciled", "Diff"]}
            rows={[
              [
                <span key="ws1" className="text-xs text-slate-800">
                  Nomad Design Co.
                </span>,
                <span key="acc1" className="text-xs text-slate-700">
                  BMO Chequing
                </span>,
                <span key="date1" className="text-xs text-slate-500">
                  Jul 31, 2025
                </span>,
                <span key="unrec1" className="text-xs text-slate-800">
                  112
                </span>,
                <span key="diff1" className="text-xs text-rose-700">
                  +$23.50
                </span>,
              ],
            ]}
          />
        </Card>
      </div>
    </div>
  );
};

const LedgerSection: React.FC = () => (
  <div className="space-y-4">
    <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Ledger health</h2>
        <p className="text-sm text-slate-600 max-w-xl">
          Double-entry invariants across all tenants: trial balance, future-dated entries, orphans, and suspense
          balances.
        </p>
      </div>
      <button className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-sm">
        Run integrity audit
      </button>
    </header>
    <Card title="Quick scan">
      <SimpleTable
        headers={["Workspace", "Unbalanced JE", "Future-dated", "Orphans", "Suspense", "Status"]}
        rows={[
          [
            <span key="ws1" className="text-xs text-slate-800">
              CERN Books Labs Inc.
            </span>,
            <span key="u1" className="text-xs text-slate-800">
              0
            </span>,
            <span key="f1" className="text-xs text-slate-800">
              0
            </span>,
            <span key="o1" className="text-xs text-slate-800">
              0
            </span>,
            <span key="s1" className="text-xs text-slate-800">
              $0.00
            </span>,
            <StatusPill key="status1" tone="good" label="Clean" />,
          ],
          [
            <span key="ws2" className="text-xs text-slate-800">
              Nomad Design Co.
            </span>,
            <span key="u2" className="text-xs text-amber-700">
              0
            </span>,
            <span key="f2" className="text-xs text-amber-700">
              2
            </span>,
            <span key="o2" className="text-xs text-slate-800">
              0
            </span>,
            <span key="s2" className="text-xs text-slate-800">
              $145.90
            </span>,
            <StatusPill key="status2" tone="warning" label="Review" />,
          ],
        ]}
      />
    </Card>
  </div>
);

const InvoicesSection: React.FC = () => (
  <div className="space-y-4">
    <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Invoices (global audit)</h2>
        <p className="text-sm text-slate-600 max-w-xl">
          Cross-tenant visibility into invoice status, failed sends, and potential duplicate or anomalous documents.
        </p>
      </div>
      <div className="flex gap-2">
        <button className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-sm">
          Failed emails
        </button>
        <button className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-sm">
          Tax mismatches
        </button>
      </div>
    </header>
    <Card title="Recent invoices with issues">
      <SimpleTable
        headers={["Workspace", "Invoice", "Customer", "Status", "Issue", "Actions"]}
        rows={[
          [
            <span key="ws" className="text-xs text-slate-800">
              Northwind Studio
            </span>,
            <span key="inv" className="text-xs text-slate-700">
              INV-1042
            </span>,
            <span key="cust" className="text-xs text-slate-700">
              Acme Films
            </span>,
            <StatusPill key="status" tone="warning" label="Overdue" />,
            <span key="issue" className="text-xs text-amber-700">
              Email bounced – invalid domain
            </span>,
            <button
              key="act"
              className="text-[11px] text-sky-700 underline underline-offset-2 hover:text-sky-800"
            >
              View invoice
            </button>,
          ],
        ]}
      />
    </Card>
  </div>
);

const ExpensesSection: React.FC = () => (
  <div className="space-y-4">
    <header className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
      <div>
        <h2 className="text-lg font-semibold text-slate-900">Expenses & receipts</h2>
        <p className="text-sm text-slate-600 max-w-xl">
          Spot mis-categorized spend, receipt anomalies, and FX conversion issues from a single, internal lens.
        </p>
      </div>
      <button className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 shadow-sm">
        View FX anomalies
      </button>
    </header>
    <Card title="Recent flagged expenses">
      <SimpleTable
        headers={["Workspace", "Vendor", "Amount", "Category", "Issue"]}
        rows={[
          [
            <span key="ws" className="text-xs text-slate-800">
              Nomad Design Co.
            </span>,
            <span key="vend" className="text-xs text-slate-700">
              AirCanada
            </span>,
            <span key="amt" className="text-xs text-slate-800">
              $2,450.00
            </span>,
            <span key="cat" className="text-xs text-slate-700">
              Travel – Flights
            </span>,
            <span key="issue" className="text-xs text-amber-700">
              Dated 2026-01-01 – future-dated
            </span>,
          ],
        ]}
      />
    </Card>
  </div>
);

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
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">CERN Books · Admin</p>
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
}> = ({ current, onSelect }) => {
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
      <div className="border-t border-slate-200 px-4 py-3 text-[11px] text-slate-600">
        <p>Everything you do here leaves a trail.</p>
        <p className="mt-0.5">Built for internal ops · CERN Books</p>
      </div>
    </aside>
  );
};

export const AdminApp: React.FC<{ initialRole?: Role }> = ({ initialRole = "superadmin" }) => {
  const [current, setCurrent] = useState<NavSectionId>("overview");
  const [role] = useState<Role>(initialRole);

  const renderSection = () => {
    switch (current) {
      case "overview":
        return <OverviewSection role={role} />;
      case "users":
        return <UsersSection />;
      case "support":
        return <SupportSection role={role} />;
      case "workspaces":
        return <WorkspacesSection />;
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
        return <OverviewSection role={role} />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
      <TopBar currentSection={current} />
      <div className="flex flex-1">
        <Sidebar current={current} onSelect={setCurrent} />
        <main className="flex-1 px-4 py-4 sm:px-6 lg:px-8">
          <div className="max-w-6xl mx-auto space-y-6 pb-8">{renderSection()}</div>
        </main>
      </div>
    </div>
  );
};
