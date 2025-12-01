import React, { useEffect, useMemo, useState } from "react";
import { fetchFeatureFlags, updateFeatureFlag, type FeatureFlag } from "./api";
import { Card, SimpleTable, StatusPill } from "./AdminUI";

type Role = "support" | "finance" | "engineer" | "superadmin";

export const FeatureFlagsSection: React.FC<{ role?: Role }> = ({ role = "superadmin" }) => {
  const [flags, setFlags] = useState<FeatureFlag[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const canEdit = role === "engineer" || role === "superadmin";

  const loadFlags = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchFeatureFlags();
      setFlags(data);
    } catch (err: any) {
      setError(err?.message || "Unable to load feature flags");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadFlags();
  }, []);

  const handleToggle = async (flag: FeatureFlag, enabled: boolean) => {
    if (!canEdit) return;
    setFlags((list) => list.map((f) => (f.id === flag.id ? { ...f, is_enabled: enabled } : f)));
    try {
      const updated = await updateFeatureFlag(flag.id, { is_enabled: enabled });
      setFlags((list) => list.map((f) => (f.id === flag.id ? updated : f)));
    } catch (err: any) {
      setError(err?.message || "Unable to update flag");
    }
  };

  const handleRolloutChange = async (flag: FeatureFlag, value: number) => {
    if (!canEdit) return;
    const nextValue = Math.min(100, Math.max(0, value));
    setFlags((list) => list.map((f) => (f.id === flag.id ? { ...f, rollout_percent: nextValue } : f)));
    try {
      const updated = await updateFeatureFlag(flag.id, { rollout_percent: nextValue });
      setFlags((list) => list.map((f) => (f.id === flag.id ? updated : f)));
    } catch (err: any) {
      setError(err?.message || "Unable to update flag");
    }
  };

  const rows = useMemo(
    () =>
      flags.map((f) => [
        <span key={`key-${f.id}`} className="text-xs font-semibold text-slate-900">
          {f.key}
        </span>,
        <span key={`label-${f.id}`} className="text-xs text-slate-800">
          {f.label}
        </span>,
        <span key={`description-${f.id}`} className="text-xs text-slate-600">
          {f.description}
        </span>,
        <div key={`enabled-${f.id}`} className="flex items-center gap-2">
          <StatusPill tone={f.is_enabled ? "good" : "neutral"} label={f.is_enabled ? "On" : "Off"} />
          <input
            type="checkbox"
            checked={f.is_enabled}
            disabled={!canEdit}
            onChange={(e) => handleToggle(f, e.target.checked)}
          />
        </div>,
        <input
          key={`rollout-${f.id}`}
          type="number"
          min={0}
          max={100}
          value={f.rollout_percent}
          disabled={!canEdit}
          onChange={(e) => handleRolloutChange(f, Number(e.target.value))}
          className="w-20 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50 disabled:opacity-50"
        />,
      ]),
    [flags, canEdit]
  );

  return (
    <Card title="Feature flags" subtitle="Toggle rollouts and guardrails for experiments.">
      {loading ? (
        <p className="text-sm text-slate-600">Loading flags…</p>
      ) : error ? (
        <p className="text-sm text-rose-700">{error}</p>
      ) : (
        <SimpleTable
          headers={["Key", "Label", "Description", "Enabled", "Rollout %"]}
          rows={rows}
        />
      )}
      {!canEdit && (
        <p className="mt-3 text-xs text-slate-500">
          View-only: engineering or superadmin required to edit feature flags.
        </p>
      )}
    </Card>
  );
};
