import React, { useEffect, useMemo, useState } from "react";
import {
  fetchAISettings,
  fetchAuditLog,
  fetchAuthMe,
  fetchIntegrityReports,
  fetchOverviewMetrics,
  fetchUsers,
  fetchWorkspaces,
  login,
  updateAISettings,
  type AdminUser,
  type AISettings,
  type IntegrityReport,
  type OverviewMetrics,
  type Paginated,
  type Workspace,
  type AuditEntry,
} from "./api/client";
import { buildApiUrl } from "./api/base";

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard" },
  { id: "users", label: "Users" },
  { id: "workspaces", label: "Workspaces" },
  { id: "ai-settings", label: "AI Settings" },
  { id: "audit", label: "Integrity & Audit" },
] as const;

type ViewId = (typeof NAV_ITEMS)[number]["id"];

type AuthState =
  | { status: "loading" }
  | { status: "unauthenticated"; error?: string }
  | { status: "unauthorized"; email?: string }
  | { status: "ready"; email: string; role?: string };

const getInitialView = (): ViewId => {
  const hash = window.location.hash.replace("#", "");
  const match = NAV_ITEMS.find((item) => item.id === hash);
  return match?.id || "dashboard";
};

const formatNumber = (value: number | string | undefined | null) => {
  if (value === undefined || value === null) return "-";
  const numeric = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(numeric)) return String(value);
  return new Intl.NumberFormat().format(numeric);
};

const formatDate = (value?: string | null) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

const aiModeLabel = (mode: string) => {
  switch (mode) {
    case "shadow_only":
      return "Preview only";
    case "suggest_only":
      return "Suggest only";
    case "drafts":
      return "Drafts";
    case "autopilot_limited":
      return "Limited autopilot";
    default:
      return mode;
  }
};

const App: React.FC = () => {
  const [auth, setAuth] = useState<AuthState>({ status: "loading" });
  const [activeView, setActiveView] = useState<ViewId>(getInitialView);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<number | null>(null);

  useEffect(() => {
    const handleHashChange = () => setActiveView(getInitialView());
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  useEffect(() => {
    const loadAuth = async () => {
      try {
        const response = await fetchAuthMe();
        if (!response.authenticated || !response.user) {
          setAuth({ status: "unauthenticated" });
          return;
        }
        const canAccess = response.user.internalAdmin?.canAccessInternalAdmin || response.user.isStaff;
        if (!canAccess) {
          setAuth({ status: "unauthorized", email: response.user.email });
          return;
        }
        setAuth({
          status: "ready",
          email: response.user.email,
          role: response.user.internalAdmin?.role || undefined,
        });
      } catch (error: any) {
        setAuth({ status: "unauthenticated", error: error?.message || "Sign in required" });
      }
    };

    loadAuth();
  }, []);

  useEffect(() => {
    if (auth.status !== "ready") return;
    fetchWorkspaces()
      .then((data) => {
        const list = (data as Paginated<Workspace>).results || [];
        setWorkspaces(list);
        if (list.length && selectedWorkspaceId === null) {
          setSelectedWorkspaceId(list[0].id);
        }
      })
      .catch(() => {
        setWorkspaces([]);
      });
  }, [auth.status]);

  const setView = (view: ViewId) => {
    window.location.hash = view;
    setActiveView(view);
  };

  if (auth.status === "loading") {
    return (
      <div className="screen center">
        <div className="loader" />
        <p>Loading admin workspace...</p>
      </div>
    );
  }

  if (auth.status === "unauthenticated") {
    return <LoginPanel error={auth.error} onSuccess={() => window.location.reload()} />;
  }

  if (auth.status === "unauthorized") {
    return (
      <div className="screen center">
        <div className="panel">
          <h1>Access restricted</h1>
          <p>This account is not cleared for internal access.</p>
          <p className="muted">Signed in as {auth.email}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-badge">CB</div>
          <div>
            <div className="brand-title">Clover Books</div>
            <div className="brand-subtitle">Admin Console</div>
          </div>
        </div>
        <nav className="nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${activeView === item.id ? "active" : ""}`}
              onClick={() => setView(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="pill">Signed in</div>
          <div className="muted">{auth.email}</div>
          {auth.role && <div className="role">Role: {auth.role}</div>}
        </div>
      </aside>
      <main className="main">
        <header className="topbar">
          <div>
            <h2>{NAV_ITEMS.find((item) => item.id === activeView)?.label}</h2>
            <p className="muted">Internal tools for staff-only workflows.</p>
          </div>
          <div className="topbar-meta">
            <div className="status">Live</div>
          </div>
        </header>
        <section className="content">
          {activeView === "dashboard" && <DashboardView />}
          {activeView === "users" && <UsersView />}
          {activeView === "workspaces" && <WorkspacesView workspaces={workspaces} />}
          {activeView === "ai-settings" && (
            <AISettingsView
              workspaces={workspaces}
              selectedWorkspaceId={selectedWorkspaceId}
              onSelectWorkspace={setSelectedWorkspaceId}
            />
          )}
          {activeView === "audit" && (
            <AuditView
              workspaces={workspaces}
              selectedWorkspaceId={selectedWorkspaceId}
              onSelectWorkspace={setSelectedWorkspaceId}
            />
          )}
        </section>
      </main>
    </div>
  );
};

const LoginPanel: React.FC<{ error?: string; onSuccess: () => void }> = ({ error, onSuccess }) => {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(error || null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setMessage(null);
    try {
      await login(username, password);
      onSuccess();
    } catch (err: any) {
      setMessage(err?.message || "Unable to sign in");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="screen center">
      <div className="panel login">
        <h1>Admin sign in</h1>
        <p className="muted">Use your staff credentials to continue.</p>
        {message && <div className="alert">{message}</div>}
        <form onSubmit={submit} className="form">
          <label>
            Email or username
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="you@company.com"
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="••••••••"
              required
            />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>
        <div className="login-footer">
          <span className="muted">Need single sign-on?</span>
          <a className="link" href={buildApiUrl("/accounts/google/login/?process=login")}>
            Use Google
          </a>
        </div>
      </div>
    </div>
  );
};

const DashboardView: React.FC = () => {
  const [metrics, setMetrics] = useState<OverviewMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchOverviewMetrics()
      .then((data) => setMetrics(data))
      .catch(() => setMetrics(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="panel">Loading metrics...</div>;
  }

  if (!metrics) {
    return <div className="panel">Metrics are unavailable right now.</div>;
  }

  return (
    <div className="grid">
      <MetricCard
        title="Active users (30d)"
        value={formatNumber(metrics.active_users_30d)}
        note="Adoption pulse"
      />
      <MetricCard
        title="Unreconciled transactions"
        value={formatNumber(metrics.unreconciled_transactions)}
        note="Customer backlog"
      />
      <MetricCard
        title="AI flagged issues"
        value={formatNumber(metrics.ai_flagged_open_issues)}
        note="Needs review"
      />
      <MetricCard
        title="Invoice emails (24h)"
        value={formatNumber(metrics.failed_invoice_emails_24h)}
        note="Delivery checks"
      />
      <MetricCard
        title="API p95 (1h)"
        value={`${formatNumber(metrics.api_p95_response_ms_1h)} ms`}
        note="Service latency"
      />
    </div>
  );
};

const UsersView: React.FC = () => {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUsers()
      .then((data) => setUsers((data as Paginated<AdminUser>).results || []))
      .catch(() => setUsers([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="panel">Loading users...</div>;

  return (
    <div className="panel">
      <h3>Users</h3>
      <p className="muted">Read-only list of people with access.</p>
      <div className="table">
        <div className="table-row header">
          <span>Email</span>
          <span>Role</span>
          <span>Workspaces</span>
          <span>Last active</span>
        </div>
        {users.length === 0 && <div className="empty">No users found.</div>}
        {users.map((user) => (
          <div key={user.id} className="table-row">
            <span>{user.email}</span>
            <span>{user.admin_role || "-"}</span>
            <span>{formatNumber(user.workspace_count)}</span>
            <span>{formatDate(user.last_login)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const WorkspacesView: React.FC<{ workspaces: Workspace[] }> = ({ workspaces }) => {
  return (
    <div className="panel">
      <h3>Workspaces</h3>
      <p className="muted">Current customer workspaces and status.</p>
      <div className="table">
        <div className="table-row header">
          <span>Name</span>
          <span>Owner</span>
          <span>Plan</span>
          <span>Status</span>
        </div>
        {workspaces.length === 0 && <div className="empty">No workspaces available.</div>}
        {workspaces.map((workspace) => (
          <div key={workspace.id} className="table-row">
            <span>{workspace.name}</span>
            <span>{workspace.owner_email || "-"}</span>
            <span>{workspace.plan || "-"}</span>
            <span>{workspace.status || "active"}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const AISettingsView: React.FC<{
  workspaces: Workspace[];
  selectedWorkspaceId: number | null;
  onSelectWorkspace: (id: number | null) => void;
}> = ({ workspaces, selectedWorkspaceId, onSelectWorkspace }) => {
  const [settings, setSettings] = useState<AISettings | null>(null);
  const [globalEnabled, setGlobalEnabled] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const workspaceOptions = useMemo(() => workspaces, [workspaces]);

  useEffect(() => {
    if (!selectedWorkspaceId) return;
    setLoading(true);
    fetchAISettings(selectedWorkspaceId)
      .then((data) => {
        setSettings(data.settings);
        setGlobalEnabled(data.global_ai_enabled);
        setMessage(null);
      })
      .catch((err: any) => {
        setMessage(err?.message || "Unable to load settings");
      })
      .finally(() => setLoading(false));
  }, [selectedWorkspaceId]);

  const updateField = (field: keyof AISettings, value: AISettings[keyof AISettings]) => {
    if (!settings) return;
    setSettings({ ...settings, [field]: value } as AISettings);
  };

  const save = async () => {
    if (!settings || !selectedWorkspaceId) return;
    setLoading(true);
    try {
      const updated = await updateAISettings(selectedWorkspaceId, settings);
      setSettings(updated.settings);
      setGlobalEnabled(updated.global_ai_enabled);
      setMessage("Settings saved.");
    } catch (err: any) {
      setMessage(err?.message || "Unable to save settings");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel">
      <h3>AI settings</h3>
      <p className="muted">Manage assistive controls for each workspace.</p>
      <div className="form-grid">
        <label>
          Workspace
          <select
            value={selectedWorkspaceId ?? ""}
            onChange={(event) => onSelectWorkspace(Number(event.target.value) || null)}
          >
            {workspaceOptions.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Global enable
          <div className="pill">{globalEnabled ? "Enabled" : "Disabled"}</div>
        </label>
      </div>

      {loading && <div className="notice">Loading settings...</div>}
      {message && <div className="alert">{message}</div>}

      {settings && (
        <div className="form">
          <div className="form-grid">
            <label>
              AI enabled
              <select
                value={settings.ai_enabled ? "yes" : "no"}
                onChange={(event) => updateField("ai_enabled", event.target.value === "yes")}
              >
                <option value="yes">Enabled</option>
                <option value="no">Disabled</option>
              </select>
            </label>
            <label>
              Emergency stop
              <select
                value={settings.kill_switch ? "yes" : "no"}
                onChange={(event) => updateField("kill_switch", event.target.value === "yes")}
              >
                <option value="no">Off</option>
                <option value="yes">On</option>
              </select>
            </label>
            <label>
              Mode
              <select
                value={settings.ai_mode}
                onChange={(event) => updateField("ai_mode", event.target.value)}
              >
                <option value="shadow_only">Preview only</option>
                <option value="suggest_only">Suggest only</option>
                <option value="drafts">Drafts</option>
                <option value="autopilot_limited">Limited autopilot</option>
              </select>
            </label>
            <label>
              Velocity limit / min
              <input
                type="number"
                value={settings.velocity_limit_per_minute}
                onChange={(event) => updateField("velocity_limit_per_minute", Number(event.target.value))}
              />
            </label>
            <label>
              Value breaker threshold
              <input
                value={settings.value_breaker_threshold}
                onChange={(event) => updateField("value_breaker_threshold", event.target.value)}
              />
            </label>
            <label>
              Anomaly stddev threshold
              <input
                value={settings.anomaly_stddev_threshold}
                onChange={(event) => updateField("anomaly_stddev_threshold", event.target.value)}
              />
            </label>
            <label>
              Trust downgrade rate
              <input
                value={settings.trust_downgrade_rejection_rate}
                onChange={(event) => updateField("trust_downgrade_rejection_rate", event.target.value)}
              />
            </label>
          </div>
          <button onClick={save} disabled={loading}>
            {loading ? "Saving..." : "Save changes"}
          </button>
        </div>
      )}
    </div>
  );
};

const AuditView: React.FC<{
  workspaces: Workspace[];
  selectedWorkspaceId: number | null;
  onSelectWorkspace: (id: number | null) => void;
}> = ({ workspaces, selectedWorkspaceId, onSelectWorkspace }) => {
  const [reports, setReports] = useState<IntegrityReport[]>([]);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!selectedWorkspaceId) return;
    setLoading(true);
    Promise.all([
      fetchIntegrityReports(selectedWorkspaceId),
      fetchAuditLog({ page_size: 25 }),
    ])
      .then(([reportData, auditData]) => {
        setReports(reportData);
        setAuditLog((auditData as Paginated<AuditEntry>).results || []);
      })
      .catch(() => {
        setReports([]);
        setAuditLog([]);
      })
      .finally(() => setLoading(false));
  }, [selectedWorkspaceId]);

  return (
    <div className="stack">
      <div className="panel">
        <div className="panel-header">
          <div>
            <h3>Integrity reports</h3>
            <p className="muted">Snapshot summaries for selected workspace.</p>
          </div>
          <select
            value={selectedWorkspaceId ?? ""}
            onChange={(event) => onSelectWorkspace(Number(event.target.value) || null)}
          >
            {workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </option>
            ))}
          </select>
        </div>
        {loading && <div className="notice">Loading reports...</div>}
        {reports.length === 0 && !loading && <div className="empty">No reports available.</div>}
        {reports.map((report) => (
          <div key={report.id} className="report">
            <div>
              <div className="report-title">
                {report.period_start} to {report.period_end}
              </div>
              <div className="muted">{report.summary}</div>
            </div>
            <div className="report-meta">{formatDate(report.created_at)}</div>
          </div>
        ))}
      </div>

      <div className="panel">
        <h3>Audit trail</h3>
        <p className="muted">Recent admin actions and changes.</p>
        <div className="table">
          <div className="table-row header">
            <span>Action</span>
            <span>Role</span>
            <span>Target</span>
            <span>Timestamp</span>
          </div>
          {auditLog.length === 0 && <div className="empty">No audit entries yet.</div>}
          {auditLog.map((entry) => (
            <div key={entry.id} className="table-row">
              <span>{entry.action}</span>
              <span>{entry.actor_role || "-"}</span>
              <span>{entry.object_type}</span>
              <span>{formatDate(entry.timestamp)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const MetricCard: React.FC<{ title: string; value: string; note: string }> = ({
  title,
  value,
  note,
}) => (
  <div className="card">
    <div className="card-title">{title}</div>
    <div className="card-value">{value}</div>
    <div className="muted">{note}</div>
  </div>
);

export default App;
