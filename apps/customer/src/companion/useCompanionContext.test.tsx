import { act, renderHook, waitFor } from "@testing-library/react";
import { vi, describe, it, expect, afterEach } from "vitest";

import { fetchCompanionOverview, markCompanionContextSeen } from "./api";
import { resetCompanionContextCacheForTests, useCompanionContext } from "./useCompanionContext";

vi.mock("./api", () => ({
  fetchCompanionOverview: vi.fn(),
  markCompanionContextSeen: vi.fn(),
}));

describe("useCompanionContext", () => {
  afterEach(() => {
    vi.resetAllMocks();
    resetCompanionContextCacheForTests();
  });

  it("returns calm state when context_all_clear is true", async () => {
    (fetchCompanionOverview as unknown as vi.Mock).mockResolvedValue({
      health_index: { score: 90, created_at: "", breakdown: {}, raw_metrics: {} },
      insights: [],
      actions: [],
      raw_metrics: {},
      next_refresh_at: null,
      llm_narrative: { summary: null, insight_explanations: {}, action_explanations: {}, context_summary: null },
      context: "bank",
      context_all_clear: true,
      context_metrics: {},
      has_new_actions: false,
      new_actions_count: 0,
      context_reasons: ["No unreconciled items."],
      context_severity: "none",
      focus_items: [],
    });

    const { result } = renderHook(() => useCompanionContext("bank"));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.contextAllClear).toBe(true);
    expect(result.current.contextInsights).toHaveLength(0);
    expect(result.current.contextActions).toHaveLength(0);
    expect(result.current.hasNewActions).toBe(false);
    expect(result.current.contextReasons).toHaveLength(1);
    expect(result.current.contextSeverity).toBe("none");
  });

  it("returns actions/insights filtered by context", async () => {
    (fetchCompanionOverview as unknown as vi.Mock).mockResolvedValue({
      health_index: { score: 80, created_at: "", breakdown: {}, raw_metrics: {} },
      insights: [
        { id: 1, context: "bank", domain: "bank", title: "Bank issue", body: "", severity: "info", suggested_actions: [], created_at: "" },
        { id: 2, context: "expenses", domain: "expenses", title: "Expense issue", body: "", severity: "info", suggested_actions: [], created_at: "" },
      ],
      actions: [
        { id: 10, context: "bank", action_type: "bank_match_review", status: "open", confidence: 0.5, summary: "Match bank", payload: {}, created_at: "" },
      ],
      raw_metrics: {},
      next_refresh_at: null,
      llm_narrative: { summary: null, insight_explanations: {}, action_explanations: {}, context_summary: "Bank looks steady." },
      context: "bank",
      context_all_clear: false,
      context_metrics: {},
      has_new_actions: true,
      new_actions_count: 1,
      context_reasons: ["2 bank items need review."],
      context_severity: "medium",
      focus_items: ["Focus on recon"],
    });

    const { result } = renderHook(() => useCompanionContext("bank"));

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.contextInsights).toHaveLength(1);
    expect(result.current.contextActions).toHaveLength(1);
    expect(result.current.contextNarrative).toBe("Bank looks steady.");
    expect(result.current.contextReasons).toHaveLength(1);
    expect(result.current.contextSeverity).toBe("medium");
    expect(result.current.focusItems).toContain("Focus on recon");
    expect(result.current.hasNewActions).toBe(true);
    expect(result.current.newActionsCount).toBe(1);
  });

  it("handles fetch errors gracefully", async () => {
    (fetchCompanionOverview as unknown as vi.Mock).mockRejectedValue(new Error("fail"));

    const { result } = renderHook(() => useCompanionContext("bank"));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    // Should fall back to an empty snapshot without surfacing an error
    expect(result.current.error).toBeNull();
    expect(result.current.contextAllClear).toBe(true);
    expect(result.current.contextActions).toHaveLength(0);
    expect(result.current.contextInsights).toHaveLength(0);
  });

  it("marks context seen and clears new flags", async () => {
    (fetchCompanionOverview as unknown as vi.Mock).mockResolvedValue({
      health_index: { score: 70, created_at: "", breakdown: {}, raw_metrics: {} },
      insights: [],
      actions: [],
      raw_metrics: {},
      next_refresh_at: null,
      llm_narrative: { summary: null, insight_explanations: {}, action_explanations: {}, context_summary: null },
      context: "bank",
      context_all_clear: false,
      context_metrics: {},
      has_new_actions: true,
      new_actions_count: 3,
    });
    (markCompanionContextSeen as unknown as vi.Mock).mockResolvedValue({ ok: true });

    const { result } = renderHook(() => useCompanionContext("bank"));
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasNewActions).toBe(true);
    expect(result.current.newActionsCount).toBe(3);

    await act(async () => {
      await result.current.markContextSeen();
    });
    expect(markCompanionContextSeen).toHaveBeenCalledWith("bank");
    await waitFor(() => expect(result.current.hasNewActions).toBe(false));
    expect(result.current.newActionsCount).toBe(0);
  });
});
