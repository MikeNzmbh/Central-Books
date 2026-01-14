import { useCallback, useEffect, useState } from "react";
import type { AISettingsResponse, WorkspaceAISettings } from "./apiV2";
import { fetchAISettingsV2, patchAISettingsV2 } from "./apiV2";

export function useAISettings(opts?: { workspaceId?: number }) {
  const [data, setData] = useState<AISettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchAISettingsV2({ workspace_id: opts?.workspaceId });
      setData(res);
    } catch (e: any) {
      setError(e?.message || "Failed to load AI settings");
    } finally {
      setLoading(false);
    }
  }, [opts?.workspaceId]);

  const patch = useCallback(async (patchBody: Partial<WorkspaceAISettings>) => {
    const res = await patchAISettingsV2(patchBody, { workspace_id: opts?.workspaceId });
    setData(res);
    return res;
  }, [opts?.workspaceId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { data, loading, error, refresh, patch };
}
