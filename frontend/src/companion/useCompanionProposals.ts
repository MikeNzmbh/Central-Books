import { useCallback, useEffect, useMemo, useState } from "react";
import type { ShadowEvent } from "./apiV2";
import { applyProposalV2, listProposalsV2, rejectProposalV2 } from "./apiV2";

export function useCompanionProposals(params?: { workspaceId?: number }) {
  const [events, setEvents] = useState<ShadowEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!params?.workspaceId) {
      setEvents([]);
      setLoading(false);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await listProposalsV2({ workspace_id: params?.workspaceId, limit: 200 });
      setEvents(data);
    } catch (e: any) {
      setError(e?.message || "Failed to load proposals");
    } finally {
      setLoading(false);
    }
  }, [params?.workspaceId]);

  const apply = useCallback(async (id: string) => {
    const res = await applyProposalV2(id, { workspace_id: params?.workspaceId });
    setEvents((prev) => prev.filter((e) => e.id !== id));
    return res;
  }, [params?.workspaceId]);

  const reject = useCallback(async (id: string, reason?: string) => {
    const res = await rejectProposalV2(id, { workspace_id: params?.workspaceId, reason });
    setEvents((prev) => prev.filter((e) => e.id !== id));
    return res;
  }, [params?.workspaceId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const counts = useMemo(() => {
    const byType: Record<string, number> = {};
    for (const e of events) byType[e.event_type] = (byType[e.event_type] || 0) + 1;
    return { total: events.length, byType };
  }, [events]);

  return { events, loading, error, refresh, apply, reject, counts };
}
