import React, { useEffect, useMemo, useState } from "react";
import { Card, SimpleTable, StatusPill } from "./AdminUI";
import {
  fetchAutonomyQueues,
  fetchAutonomyStatus,
  runAutonomyMaterialize,
  runAutonomyTick,
  updateAutonomyPolicy,
  type AutonomyQueuesResponse,
  type AutonomyStatus,
} from "./api";

const MODE_OPTIONS = ["shadow_only", "suggest_only", "drafts", "autopilot_limited"];

export const AutonomySection: React.FC = () => {
  const [tenantId, setTenantId] = useState("1");
  const [status, setStatus] = useState<AutonomyStatus | null>(null);
  const [queues, setQueues] = useState<AutonomyQueuesResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState("suggest_only");
  const [saving, setSaving] = useState(false);

  const tenantNumber = useMemo(() => {
    const parsed = Number(tenantId);
    return Number.isFinite(parsed) ? parsed : null;
  }, [tenantId]);

  const refresh = async () => {
    if (!tenantNumber) return;
    setLoading(true);
    try {
      const [statusResp, queuesResp] = await Promise.all([
        fetchAutonomyStatus(tenantNumber),
        fetchAutonomyQueues(tenantNumber),
      ]);
      setStatus(statusResp);
      setQueues(queuesResp);
      if (statusResp?.mode) setMode(statusResp.mode);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tenantNumber]);

  const handleTick = async () => {
    if (!tenantNumber) return;
    setLoading(true);
    await runAutonomyTick(tenantNumber);
    await refresh();
  };

  const handleMaterialize = async () => {
    if (!tenantNumber) return;
    setLoading(true);
    await runAutonomyMaterialize(tenantNumber);
    await refresh();
  };

  const handleSaveMode = async () => {
    if (!tenantNumber) return;
    setSaving(true);
    await updateAutonomyPolicy(tenantNumber, mode);
    setSaving(false);
    await refresh();
  };

  const jobRows = (queues?.data?.job_by_agent || []).map((row) => [
    row.agent,
    row.queued,
    row.running,
    row.blocked,
  ]);
  const snapshotFreshness = queues ? (queues.stale ? "Stale" : "Fresh") : "Unknown";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Autonomy Engine</h2>
          <p className="text-sm text-slate-600">
            Inspect queue health, breakers, and per-tenant policies.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            value={tenantId}
            onChange={(e) => setTenantId(e.target.value)}
            placeholder="Tenant ID"
            className="h-9 rounded-xl border border-slate-200 px-3 text-sm"
          />
          <button
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm"
            onClick={refresh}
            disabled={loading || !tenantNumber}
          >
            Refresh
          </button>
          <button
            className="rounded-xl border border-slate-200 bg-slate-900 px-3 py-2 text-xs font-semibold text-white shadow-sm"
            onClick={handleTick}
            disabled={loading || !tenantNumber}
          >
            Run tick
          </button>
          <button
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 shadow-sm"
            onClick={handleMaterialize}
            disabled={loading || !tenantNumber}
          >
            Materialize
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card
          title="Status"
          subtitle={`Tenant ${tenantNumber ?? "—"} · Engine ${status?.engine_version || "v1"}`}
          footer={
            status ? (
              <StatusPill
                tone={status.breakers.ok ? "good" : "warning"}
                label={status.breakers.ok ? "Breakers ok" : "Breaker tripped"}
              />
            ) : null
          }
        >
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="text-slate-500">Mode</div>
              <div className="font-semibold text-slate-800">{status?.mode || "unknown"}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="text-slate-500">Breakers (24h)</div>
              <div className="font-semibold text-slate-800">{status?.breakers.recent ?? 0}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="text-slate-500">Last tick</div>
              <div className="font-semibold text-slate-800">{status?.last_tick_at || "—"}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="text-slate-500">Last materialized</div>
              <div className="font-semibold text-slate-800">{status?.last_materialized_at || "—"}</div>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value)}
              className="h-9 rounded-xl border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700"
            >
              {MODE_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
            <button
              className="rounded-xl border border-slate-200 bg-slate-900 px-3 py-2 text-xs font-semibold text-white shadow-sm"
              onClick={handleSaveMode}
              disabled={saving || !tenantNumber}
            >
              {saving ? "Saving..." : "Update mode"}
            </button>
          </div>
        </Card>

        <Card title="Queue snapshot" subtitle={queues?.source ? `Source: ${queues.source}` : "Latest snapshot"}>
          <div className="grid grid-cols-3 gap-3 text-xs">
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="text-slate-500">Queued</div>
              <div className="font-semibold text-slate-800">{queues?.data?.job_totals?.queued ?? 0}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="text-slate-500">Running</div>
              <div className="font-semibold text-slate-800">{queues?.data?.job_totals?.running ?? 0}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="text-slate-500">Blocked</div>
              <div className="font-semibold text-slate-800">{queues?.data?.job_totals?.blocked ?? 0}</div>
            </div>
          </div>
          <div className="mt-4 text-xs text-slate-500">
            Snapshot: {queues?.data?.generated_at || "—"} · {snapshotFreshness}
          </div>
        </Card>
      </div>

      <Card title="By agent" subtitle="Queued / Running / Blocked">
        {jobRows.length === 0 ? (
          <div className="text-sm text-slate-500">No agent activity yet.</div>
        ) : (
          <SimpleTable headers={["Agent", "Queued", "Running", "Blocked"]} rows={jobRows} />
        )}
      </Card>

      <Card title="Top blockers" subtitle="Most recent failed or blocked jobs">
        <div className="space-y-2">
          {(queues?.data?.top_blockers || []).length === 0 ? (
            <div className="text-sm text-slate-500">No blockers reported.</div>
          ) : (
            (queues?.data?.top_blockers || []).map((blocker, index) => (
              <div
                key={`${blocker.kind}-${index}`}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold">{blocker.kind}</span>
                  <span className="text-slate-500">{blocker.status}</span>
                </div>
                <div className="mt-1 text-slate-500">{blocker.reason}</div>
              </div>
            ))
          )}
        </div>
      </Card>
    </div>
  );
};
