import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  Banknote,
  ChevronRight,
  Clock,
  FileText,
  Filter,
  Gauge,
  Layers,
  ListChecks,
  Loader2,
  Lock,
  MessageSquareText,
  RefreshCw,
  Search,
  Shield,
  Sparkles,
} from "lucide-react";

// shadcn/ui
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Progress } from "@/components/ui/progress";

import CloseAssistantDrawer from "./CloseAssistantDrawer";
import IssuesPanel from "./IssuesPanel";
import PanelShell from "./PanelShell";
import SuggestionsPanel from "./SuggestionsPanel";
import { PanelType } from "./companionCopy";

// recharts (available)
import {
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  Tooltip as ReTooltip,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  BarChart,
  Bar,
} from "recharts";

/**
 * AI Companion Control Tower (Customer-safe UI)
 * ------------------------------------------------
 * - Single calm surface
 * - Right-side panels: AI Suggestions, Issues, Close Assistant
 * - Neutral palette (no orange accents)
 * - Customer-safe copy: “changes to your books”, “AI suggestions”, “review”
 *
 * Wiring:
 * - Summary: GET /api/agentic/companion/summary
 * - Issues: GET /api/agentic/companion/issues?status=open
 * - Suggestions: /api/companion/v2/shadow-events/?status=proposed
 */

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

type FocusMode = "all_clear" | "watchlist" | "fire_drill";

type SurfaceKey = "receipts" | "invoices" | "books" | "banking";

type RadarAxis = {
  key: "cash_reconciliation" | "revenue_invoices" | "expenses_receipts" | "tax_compliance";
  label: string;
  score: number; // 0..100
  open_issues: number;
};

type Coverage = {
  key: SurfaceKey;
  coverage_percent: number; // 0..100
  total_items: number;
  covered_items: number;
};

type PlaybookItem = {
  id: string;
  title: string;
  description?: string;
  severity: "low" | "medium" | "high";
  surface?: SurfaceKey;
  url?: string;
  premium?: boolean;
};

type CloseReadiness = {
  status: "ready" | "not_ready";
  period_label: string;
  progress_percent: number;
  blockers: Array<{ id: string; title: string; surface?: SurfaceKey; url?: string; severity: "medium" | "high" }>;
};

type LlmSubtitle = {
  surface: SurfaceKey;
  subtitle: string;
  source: "ai" | "auto";
};

type FinanceSnapshot = {
  ending_cash: number;
  monthly_burn: number;
  runway_months: number;
  months: Array<{ m: string; rev: number; exp: number }>;
  ar_buckets: Array<{ bucket: string; amount: number }>;
  total_overdue: number;
};

type TaxGuardian = {
  period_key: string;
  net_tax: Array<{ jurisdiction: string; amount: number }>;
  anomaly_counts: { low: number; medium: number; high: number };
};

type Voice = {
  greeting: string;
  focus_mode: FocusMode;
  tone_tagline: string;
  primary_call_to_action: string;
};

type Summary = {
  ai_companion_enabled: boolean;
  generated_at: string;
  voice: Voice;
  radar: RadarAxis[];
  coverage: Coverage[];
  playbook: PlaybookItem[];
  close_readiness: CloseReadiness;
  llm_subtitles: LlmSubtitle[];
  finance_snapshot: FinanceSnapshot;
  tax_guardian: TaxGuardian;
};

// V2 proposals (customer-safe)

type Proposal = {
  id: string;
  surface: SurfaceKey;
  title: string;
  description: string;
  amount?: number;
  risk: "ready" | "review" | "needs_attention";
  created_at: string;
  target_url?: string; // review link
  // backend action ids can be carried here if needed
};

type Issue = {
  id: string;
  surface: SurfaceKey;
  title: string;
  description?: string;
  severity: "low" | "medium" | "high";
  created_at: string;
  target_url?: string;
};

function normalizeSurfaceKey(value?: string | null): SurfaceKey | null {
  if (!value) return null;
  const v = value.toLowerCase();
  if (v === "bank" || v === "banking" || v === "bank_review") return "banking";
  if (v === "books" || v === "book" || v === "books_review" || v === "books-review") return "books";
  if (v === "receipts" || v === "expenses") return "receipts";
  if (v === "invoices" || v === "revenue") return "invoices";
  return null;
}

function surfaceKeyToFilterParam(surface: SurfaceKey) {
  return surface === "banking" ? "bank" : surface;
}

const SURFACE_URLS: Record<SurfaceKey, string> = {
  banking: "/banking/",
  invoices: "/invoices/ai/",
  receipts: "/receipts/",
  books: "/books-review/",
};

function proposalSurfaceFromEvent(event: any): SurfaceKey {
  const explicit = normalizeSurfaceKey(event?.data?.surface || event?.surface || event?.domain);
  if (explicit) return explicit;
  const eventType = String(event?.event_type || "").toLowerCase();
  if (eventType.includes("bank")) return "banking";
  if (eventType.includes("categorization")) return "banking";
  return "books";
}

function proposalRiskFromEvent(event: any): Proposal["risk"] {
  const tier = Number(event?.human_in_the_loop?.tier);
  if (Number.isFinite(tier)) {
    if (tier >= 2) return "needs_attention";
    if (tier === 1) return "review";
    return "ready";
  }
  return event?.status === "proposed" ? "review" : "ready";
}

function proposalTitleFromEvent(event: any): string {
  if (event?.data?.title) return String(event.data.title);
  const eventType = String(event?.event_type || "");
  if (eventType.includes("BankMatch")) return "Match a bank transaction";
  if (eventType.includes("Categorization")) return "Categorize a bank transaction";
  const desc = event?.data?.bank_transaction_description;
  if (desc) return `Review "${desc}"`;
  return "Review suggested change";
}

function proposalDescriptionFromEvent(event: any): string {
  if (event?.rationale) return String(event.rationale);
  const eventType = String(event?.event_type || "");
  const desc = event?.data?.bank_transaction_description || event?.data?.journal_entry_description;
  if (!desc) return "Review the suggested change before applying.";
  if (eventType.includes("BankMatch")) return `AI suggests matching "${desc}" to an existing entry.`;
  if (eventType.includes("Categorization")) return `AI suggests categorizing "${desc}" based on similar activity.`;
  return `Review the suggested change for "${desc}".`;
}

function proposalAmountFromEvent(event: any): number | undefined {
  const raw = event?.data?.bank_transaction_amount ?? event?.data?.amount ?? event?.data?.total;
  const num = Number(raw);
  return Number.isFinite(num) ? num : undefined;
}

// API Functions
async function fetchSummaryApi(): Promise<Summary> {
  const res = await fetch("/api/agentic/companion/summary", { credentials: "same-origin" });
  if (!res.ok) throw new Error("Failed to load summary");
  const data = await res.json();

  // Transform backend response to our types with null safety
  const voice = data.voice || {};
  const radar = data.radar || {};
  const coverage = data.coverage || {};
  const playbook = data.playbook || [];
  const closeReadiness = data.close_readiness || {};
  const llmSubtitles = data.llm_subtitles || {};
  const financeSnapshot = data.finance_snapshot || {};
  const taxBlock = data.tax || data.tax_guardian || {};
  const taxJurisdictions = Array.isArray(taxBlock.jurisdictions) ? taxBlock.jurisdictions : [];
  const taxNetEntries = taxJurisdictions.length
    ? taxJurisdictions.map((j: any) => ({
        jurisdiction: j.code || j.jurisdiction || "Tax",
        amount: j.net_tax ?? j.amount ?? 0,
      }))
    : taxBlock.net_tax != null
      ? [{ jurisdiction: "Net tax", amount: Number(taxBlock.net_tax) || 0 }]
      : [];

  const cashHealth = financeSnapshot.cash_health || {};
  const revenueExpense = financeSnapshot.revenue_expense || {};
  const arHealth = financeSnapshot.ar_health || {};

  const fallbackMonths = Array.isArray(revenueExpense.months)
    ? revenueExpense.months.map((m: string, i: number) => ({
        m,
        rev: revenueExpense.revenue?.[i] ?? 0,
        exp: revenueExpense.expense?.[i] ?? 0,
      }))
    : [];

  const fallbackArBuckets = arHealth.buckets
    ? Object.entries(arHealth.buckets).map(([bucket, amount]) => ({ bucket, amount: Number(amount) || 0 }))
    : [];

  return {
    ai_companion_enabled: data.ai_companion_enabled ?? true,
    generated_at: data.generated_at || new Date().toISOString(),
    voice: {
      greeting: voice.greeting || "Hello",
      focus_mode: voice.focus_mode || "watchlist",
      tone_tagline: voice.tone_tagline || "Your books need attention.",
      primary_call_to_action: voice.primary_call_to_action || "Review open items.",
    },
    radar: [
      { key: "cash_reconciliation" as const, label: "Cash", score: radar.cash_reconciliation?.score ?? 100, open_issues: radar.cash_reconciliation?.open_issues ?? 0 },
      { key: "revenue_invoices" as const, label: "Revenue", score: radar.revenue_invoices?.score ?? 100, open_issues: radar.revenue_invoices?.open_issues ?? 0 },
      { key: "expenses_receipts" as const, label: "Expenses", score: radar.expenses_receipts?.score ?? 100, open_issues: radar.expenses_receipts?.open_issues ?? 0 },
      { key: "tax_compliance" as const, label: "Tax", score: radar.tax_compliance?.score ?? 100, open_issues: radar.tax_compliance?.open_issues ?? 0 },
    ],
    coverage: [
      { key: "receipts" as SurfaceKey, coverage_percent: coverage.receipts?.coverage_percent ?? 0, total_items: coverage.receipts?.total_items ?? 0, covered_items: coverage.receipts?.covered_items ?? 0 },
      { key: "invoices" as SurfaceKey, coverage_percent: coverage.invoices?.coverage_percent ?? 0, total_items: coverage.invoices?.total_items ?? 0, covered_items: coverage.invoices?.covered_items ?? 0 },
      { key: "banking" as SurfaceKey, coverage_percent: coverage.banking?.coverage_percent ?? coverage.bank?.coverage_percent ?? 0, total_items: coverage.banking?.total_items ?? coverage.bank?.total_items ?? 0, covered_items: coverage.banking?.covered_items ?? coverage.bank?.covered_items ?? 0 },
      { key: "books" as SurfaceKey, coverage_percent: coverage.books?.coverage_percent ?? 0, total_items: coverage.books?.total_items ?? 0, covered_items: coverage.books?.covered_items ?? 0 },
    ],
    playbook: playbook.map((p: any, i: number) => ({
      id: `p${i}`,
      title: p.label || p.title || "Action item",
      description: p.description || "",
      severity: (p.severity || "medium") as "low" | "medium" | "high",
      surface: normalizeSurfaceKey(p.surface) || undefined,
      url: p.url,
      premium: p.requires_premium ?? false,
    })),
    close_readiness: {
      status: closeReadiness.status === "ready" ? "ready" : "not_ready",
      period_label: closeReadiness.period_label || "Current Period",
      progress_percent: closeReadiness.progress_percent ?? (closeReadiness.status === "ready" ? 100 : 50),
      blockers: (closeReadiness.blocking_items || closeReadiness.blocking_reasons || []).map((b: any, i: number) => ({
        id: `b${i}`,
        title: typeof b === "string" ? b : (b.reason || b.title || "Blocker"),
        surface: normalizeSurfaceKey(b.surface) || undefined,
        severity: (b.severity || "high") as "medium" | "high",
        url: b.url,
      })),
    },
    llm_subtitles: [
      { surface: "banking" as SurfaceKey, subtitle: llmSubtitles.bank || llmSubtitles.banking || "", source: "ai" as const },
      { surface: "receipts" as SurfaceKey, subtitle: llmSubtitles.receipts || "", source: "ai" as const },
      { surface: "invoices" as SurfaceKey, subtitle: llmSubtitles.invoices || "", source: "ai" as const },
      { surface: "books" as SurfaceKey, subtitle: llmSubtitles.books || "", source: "ai" as const },
    ].filter(s => s.subtitle) as LlmSubtitle[],
    finance_snapshot: {
      ending_cash: financeSnapshot.ending_cash ?? cashHealth.ending_cash ?? 0,
      monthly_burn: financeSnapshot.monthly_burn ?? cashHealth.monthly_burn ?? 0,
      runway_months: financeSnapshot.runway_months ?? cashHealth.runway_months ?? 0,
      months: financeSnapshot.months || fallbackMonths,
      ar_buckets: financeSnapshot.ar_buckets || fallbackArBuckets,
      total_overdue: financeSnapshot.total_overdue ?? arHealth.total_overdue ?? 0,
    },
    tax_guardian: {
      period_key: taxBlock.period_key || "Current Period",
      net_tax: taxNetEntries,
      anomaly_counts: {
        low: taxBlock.anomaly_counts?.low ?? 0,
        medium: taxBlock.anomaly_counts?.medium ?? 0,
        high: taxBlock.anomaly_counts?.high ?? 0,
      },
    },
  };
}

async function fetchProposalsApi(): Promise<Proposal[]> {
  try {
    const res = await fetch("/api/companion/v2/shadow-events/?status=proposed&limit=50", {
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return [];
    const data = await res.json();
    const items = Array.isArray(data) ? data : (data?.events || data?.items || []);
    if (!Array.isArray(items)) return [];
    return items.map((event: any) => {
      const surface = proposalSurfaceFromEvent(event);
      return {
        id: event.id,
        surface,
        title: proposalTitleFromEvent(event),
        description: proposalDescriptionFromEvent(event),
        amount: proposalAmountFromEvent(event),
        risk: proposalRiskFromEvent(event),
        created_at: event.created_at || new Date().toISOString(),
        target_url: event?.data?.target_url || SURFACE_URLS[surface],
      };
    });
  } catch {
    return [];
  }
}

async function fetchIssuesApi(): Promise<Issue[]> {
  try {
    const res = await fetch("/api/agentic/companion/issues?status=open", { credentials: "same-origin" });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.issues || []).map((i: any) => ({
      id: String(i.id),
      surface: normalizeSurfaceKey(i.surface) || "banking",
      title: i.title,
      description: i.recommended_action || i.estimated_impact || "",
      severity: i.severity,
      created_at: i.created_at,
      target_url: i.target_url,
    }));
  } catch {
    return [];
  }
}

// ---------------------------
// Helpers
// ---------------------------
function formatMoney(x: number | undefined | null) {
  if (x == null || Number.isNaN(x)) return "$0";
  const abs = Math.abs(x);
  if (abs >= 1_000_000) return `$${(x / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `$${(x / 1_000).toFixed(1)}K`;
  return `$${x.toFixed(0)}`;
}

function focusTone(mode: FocusMode) {
  if (mode === "all_clear") return { label: "All clear", className: "bg-zinc-900 text-white" };
  if (mode === "fire_drill") return { label: "Action needed", className: "bg-zinc-950 text-white" };
  return { label: "Watchlist", className: "bg-zinc-100 text-zinc-900 border border-zinc-200" };
}

function severityChip(sev: "low" | "medium" | "high") {
  if (sev === "high") return { label: "Needs attention", cls: "bg-zinc-950 text-white" };
  if (sev === "medium") return { label: "Review recommended", cls: "bg-zinc-100 text-zinc-900 border border-zinc-200" };
  return { label: "Ready", cls: "bg-zinc-50 text-zinc-700 border border-zinc-200" };
}

function surfaceMeta(key: SurfaceKey) {
  const map: Record<SurfaceKey, { label: string; icon: any }> = {
    receipts: { label: "Receipts", icon: FileText },
    invoices: { label: "Invoices", icon: Layers },
    books: { label: "Books Review", icon: ListChecks },
    banking: { label: "Banking", icon: Banknote },
  };
  return map[key];
}

// ---------------------------
// Query-param panel routing
// ---------------------------
function usePanelRouting() {
  const [searchParams, setSearchParams] = useSearchParams();

  const panelParam = (searchParams.get("panel") || "").toLowerCase();
  const panel = panelParam === "suggestions" || panelParam === "issues" || panelParam === "close"
    ? (panelParam as PanelType)
    : null;

  const surfaceParam = (searchParams.get("surface") || "").toLowerCase();
  const surfaceKey = normalizeSurfaceKey(surfaceParam);
  const surfaceLabel = surfaceKey ? surfaceMeta(surfaceKey).label : null;
  const surfaceFilter = surfaceKey ? surfaceKeyToFilterParam(surfaceKey) : null;

  const open = (p: PanelType, surface?: SurfaceKey) => {
    const next = new URLSearchParams(searchParams);
    next.set("panel", p);
    if (surface) {
      next.set("surface", surfaceKeyToFilterParam(surface));
    } else {
      next.delete("surface");
    }
    setSearchParams(next, { replace: false });
  };

  const close = () => {
    const next = new URLSearchParams(searchParams);
    next.delete("panel");
    next.delete("surface");
    setSearchParams(next, { replace: false });
  };

  return { panel, surfaceFilter, surfaceLabel, open, close };
}

// ---------------------------
// Main Page
// ---------------------------
export default function AICompanionControlTower() {
  const { panel, surfaceFilter, surfaceLabel, open, close } = usePanelRouting();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [safeMode, setSafeMode] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      const [summaryResult, proposalsResult, issuesResult] = await Promise.allSettled([
        fetchSummaryApi(),
        fetchProposalsApi(),
        fetchIssuesApi(),
      ]);
      if (!alive) return;
      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
      } else {
        console.error("Failed to load summary", summaryResult.reason);
        setSummary(null);
      }
      setProposals(proposalsResult.status === "fulfilled" ? proposalsResult.value : []);
      setIssues(issuesResult.status === "fulfilled" ? issuesResult.value : []);
      setLoading(false);
    })();
    return () => {
      alive = false;
    };
  }, []);

  const radarData = useMemo(() => {
    if (!summary) return [];
    return summary.radar.map((r) => ({ axis: r.label, score: r.score }));
  }, [summary]);

  const focus = summary ? focusTone(summary.voice.focus_mode) : focusTone("watchlist");

  const openCounts = useMemo(() => {
    if (!summary) return { totalIssues: 0, totalSuggestions: 0 };
    const totalIssues = summary.radar.reduce((acc, r) => acc + (r.open_issues || 0), 0);
    const totalSuggestions = proposals.length;
    return { totalIssues, totalSuggestions };
  }, [summary, proposals]);

  const refresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      const [summaryResult, proposalsResult, issuesResult] = await Promise.allSettled([
        fetchSummaryApi(),
        fetchProposalsApi(),
        fetchIssuesApi(),
      ]);
      if (summaryResult.status === "fulfilled") {
        setSummary(summaryResult.value);
      }
      if (proposalsResult.status === "fulfilled") {
        setProposals(proposalsResult.value);
      }
      if (issuesResult.status === "fulfilled") {
        setIssues(issuesResult.value);
      }
    } catch (e) {
      console.error("Failed to refresh companion data", e);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div
      className={cx(
        "min-h-screen bg-white text-zinc-950",
        // JetBrains Mono-ish feel without being overly mono
        "[font-family:ui-sans-serif,system-ui,-apple-system,Segoe_UI,Roboto,Helvetica,Arial,\"Apple_Color_Emoji\",\"Segoe_UI_Emoji\"]"
      )}
    >
      <TopHeader
        summary={summary}
        loading={loading}
        refreshing={refreshing}
        onRefresh={refresh}
        onOpenSuggestions={() => open("suggestions")}
        onOpenIssues={() => open("issues")}
        onOpenClose={() => open("close")}
        counts={openCounts}
        safeMode={safeMode}
        setSafeMode={setSafeMode}
      />

      {summary && !summary.ai_companion_enabled ? (
        <div className="mx-auto max-w-7xl px-4 pt-4">
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Companion is disabled. Enable AI Companion to see suggestions and insights.
          </div>
        </div>
      ) : null}

      <div className="mx-auto max-w-7xl px-4 pb-12 pt-8">
        {loading || !summary ? (
          <SkeletonBoard />
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.15fr_0.85fr]">
            {/* Left column */}
            <div className="space-y-6">
              <HeroVoice summary={summary} focus={focus} />

              <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                <HealthPulseCard summary={summary} radarData={radarData} onOpenIssues={() => open("issues")} />
                <CloseReadinessCard summary={summary} onOpenClose={() => open("close")} />
              </div>

              <TodayFocusCard items={summary.playbook} onOpenSuggestions={() => open("suggestions")} />

              <SurfacesGrid
                summary={summary}
                proposals={proposals}
                issues={issues}
                onOpenSuggestions={(surface) => open("suggestions", surface)}
                onOpenIssues={(surface) => open("issues", surface)}
              />
            </div>

            {/* Right column */}
            <div className="space-y-6">
              <FinanceSnapshotCard finance={summary.finance_snapshot} />
              <TaxGuardianCard tax={summary.tax_guardian} />
              <TrustSafetyCard safeMode={safeMode} />
            </div>
          </div>
        )}
      </div>

      <PanelShell panel={panel} onClose={close} surface={surfaceLabel}>
        {panel === "suggestions" && (
          <SuggestionsPanel
            proposals={proposals}
            surface={surfaceFilter}
            onApplied={(id) => setProposals((prev) => prev.filter((p) => p.id !== id))}
            onDismissed={(id) => setProposals((prev) => prev.filter((p) => p.id !== id))}
            loading={loading}
          />
        )}
        {panel === "issues" && <IssuesPanel issues={issues} surface={surfaceFilter} loading={loading} />}
        {panel === "close" && <CloseAssistantDrawer summary={summary} loading={loading} />}
      </PanelShell>

      <Footer />
    </div>
  );
}

// ---------------------------
// Header / Hero
// ---------------------------
function TopHeader({
  summary,
  loading,
  refreshing,
  onRefresh,
  onOpenSuggestions,
  onOpenIssues,
  onOpenClose,
  counts,
  safeMode,
  setSafeMode,
}: {
  summary: Summary | null;
  loading: boolean;
  refreshing: boolean;
  onRefresh: () => void;
  onOpenSuggestions: () => void;
  onOpenIssues: () => void;
  onOpenClose: () => void;
  counts: { totalIssues: number; totalSuggestions: number };
  safeMode: boolean;
  setSafeMode: (v: boolean) => void;
}) {
  return (
    <div className="sticky top-0 z-40 border-b border-zinc-200 bg-white/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-2xl border border-zinc-200 bg-white shadow-sm">
            <Sparkles className="h-4 w-4 text-zinc-900" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold tracking-tight">Companion Control Tower</div>
            <div className="text-[11px] text-zinc-500">AI Companion • Safe suggestions • Clear actions</div>
          </div>
        </div>

        <div className="hidden items-center gap-2 md:flex">
          <Badge variant="outline" className="rounded-full border-zinc-200 bg-white text-zinc-700">
            {loading ? "…" : `${counts.totalSuggestions} suggestions`}
          </Badge>
          <Badge variant="outline" className="rounded-full border-zinc-200 bg-white text-zinc-700">
            {loading ? "…" : `${counts.totalIssues} issues`}
          </Badge>

          <div className="flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-2 shadow-sm">
            <Shield className="h-4 w-4 text-zinc-700" />
            <div className="text-xs text-zinc-700">Safe mode</div>
            <Switch checked={safeMode} onCheckedChange={setSafeMode} />
          </div>

          <Button
            onClick={onRefresh}
            variant="outline"
            className="rounded-full border-zinc-200 bg-white"
            disabled={refreshing}
          >
            {refreshing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
            Refresh
          </Button>

          <Button onClick={onOpenSuggestions} className="rounded-full bg-zinc-950 text-white hover:bg-zinc-900">
            AI Suggestions
            <ArrowRight className="ml-2 h-4 w-4" />
          </Button>
        </div>

        <div className="flex items-center gap-2 md:hidden">
          <Button onClick={onOpenSuggestions} size="sm" className="rounded-full bg-zinc-950 text-white hover:bg-zinc-900">
            Suggestions
          </Button>
        </div>
      </div>

      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            onClick={onOpenIssues}
            variant="outline"
            className="rounded-full border-zinc-200 bg-white"
            size="sm"
          >
            <AlertTriangle className="mr-2 h-4 w-4" />
            Open issues
          </Button>
          <Button
            onClick={onOpenClose}
            variant="outline"
            className="rounded-full border-zinc-200 bg-white"
            size="sm"
          >
            <Lock className="mr-2 h-4 w-4" />
            Close assistant
          </Button>
        </div>

        <div className="text-[11px] text-zinc-500">
          {summary ? `Updated ${new Date(summary.generated_at).toLocaleString()}` : ""}
        </div>
      </div>
    </div>
  );
}

function HeroVoice({ summary, focus }: { summary: Summary; focus: { label: string; className: string } }) {
  return (
    <Card className="overflow-hidden border-zinc-200 bg-white shadow-sm">
      <CardContent className="p-6">
        <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2">
              <div className="text-xl font-semibold tracking-tight">{summary.voice.greeting}</div>
              <span className={cx("rounded-full px-3 py-1 text-xs", focus.className)}>{focus.label}</span>
            </div>
            <div className="mt-2 text-sm text-zinc-600">{summary.voice.tone_tagline}</div>
            <div className="mt-4 rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
              <div className="text-xs font-semibold text-zinc-700">Today's best next step</div>
              <div className="mt-1 text-sm text-zinc-900">{summary.voice.primary_call_to_action}</div>
            </div>
          </div>

          <div className="w-full md:max-w-[360px]">
            <QuickSearchCard />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function QuickSearchCard() {
  const [q, setQ] = useState("");
  return (
    <div className="rounded-3xl border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="text-sm font-semibold">Ask Companion</div>
        <Badge variant="outline" className="rounded-full border-zinc-200 bg-white text-zinc-600">
          customer-safe
        </Badge>
      </div>
      <div className="mt-3 relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Example: why is cash lower this month?"
          className="h-11 rounded-2xl border-zinc-200 bg-white pl-10"
        />
      </div>
      <div className="mt-3 text-[11px] text-zinc-500">
        Tip: ask questions like a business owner — we’ll translate it into safe checks.
      </div>
      <div className="mt-4 flex gap-2">
        <Button className="flex-1 rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900" disabled={!q.trim()}>
          <MessageSquareText className="mr-2 h-4 w-4" />
          Ask
        </Button>
        <Button variant="outline" className="rounded-2xl border-zinc-200 bg-white">
          <Filter className="mr-2 h-4 w-4" />
          Filters
        </Button>
      </div>
    </div>
  );
}

// ---------------------------
// Cards
// ---------------------------
function HealthPulseCard({ summary, radarData, onOpenIssues }: { summary: Summary; radarData: any[]; onOpenIssues: () => void }) {
  const overall = Math.round(summary.radar.reduce((acc, r) => acc + r.score, 0) / summary.radar.length);
  const open = summary.radar.reduce((acc, r) => acc + r.open_issues, 0);

  return (
    <Card className="border-zinc-200 bg-white shadow-sm">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">Health Pulse</CardTitle>
            <CardDescription>Four domains, one glance.</CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Badge className="rounded-full bg-zinc-950 text-white">{overall}/100</Badge>
            <Button onClick={onOpenIssues} variant="outline" className="rounded-full border-zinc-200 bg-white" size="sm">
              {open} open
              <ChevronRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="h-[220px] rounded-3xl border border-zinc-200 bg-zinc-50 p-3">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} outerRadius="75%">
              <PolarGrid />
              <PolarAngleAxis dataKey="axis" tick={{ fontSize: 11 }} />
              <ReTooltip />
              <Radar dataKey="score" stroke="currentColor" fill="currentColor" fillOpacity={0.12} className="text-zinc-900" />
            </RadarChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3">
          {summary.radar.map((r) => (
            <div key={r.key} className="rounded-3xl border border-zinc-200 bg-white p-4">
              <div className="flex items-center justify-between">
                <div className="text-xs font-semibold text-zinc-700">{r.label}</div>
                <Badge variant="outline" className="rounded-full border-zinc-200 bg-white text-zinc-700">
                  {r.open_issues} open
                </Badge>
              </div>
              <div className="mt-2 text-lg font-semibold text-zinc-950">{r.score}</div>
              <div className="mt-2">
                <Progress value={r.score} />
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function CloseReadinessCard({ summary, onOpenClose }: { summary: Summary; onOpenClose: () => void }) {
  const cr = summary.close_readiness;
  const statusLabel = cr.status === "ready" ? "Ready" : "Not ready";

  return (
    <Card className="border-zinc-200 bg-white shadow-sm">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">Close Readiness</CardTitle>
            <CardDescription>{cr.period_label}</CardDescription>
          </div>
          <Badge className={cx("rounded-full", cr.status === "ready" ? "bg-zinc-950 text-white" : "bg-zinc-100 text-zinc-900 border border-zinc-200")}>{statusLabel}</Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
          <div className="flex items-center justify-between">
            <div className="text-xs font-semibold text-zinc-700">Progress</div>
            <div className="text-xs text-zinc-600">{cr.progress_percent}%</div>
          </div>
          <div className="mt-2">
            <Progress value={cr.progress_percent} />
          </div>

          <div className="mt-4 space-y-2">
            {cr.blockers.slice(0, 3).map((b) => (
              <div key={b.id} className="flex items-start justify-between gap-3 rounded-2xl border border-zinc-200 bg-white px-3 py-2">
                <div>
                  <div className="text-sm font-semibold text-zinc-950">{b.title}</div>
                  <div className="mt-0.5 text-xs text-zinc-500">{b.surface ? surfaceMeta(b.surface).label : ""}</div>
                </div>
                <span className={cx("rounded-full px-3 py-1 text-[11px]", severityChip(b.severity).cls)}>{severityChip(b.severity).label}</span>
              </div>
            ))}
          </div>

          <div className="mt-4 flex gap-2">
            <Button onClick={onOpenClose} className="flex-1 rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900">
              <Lock className="mr-2 h-4 w-4" />
              Open Close Assistant
            </Button>
            <Button variant="outline" className="rounded-2xl border-zinc-200 bg-white">
              <Clock className="mr-2 h-4 w-4" />
              Schedule
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function TodayFocusCard({ items, onOpenSuggestions }: { items: PlaybookItem[]; onOpenSuggestions: () => void }) {
  const top = items.slice(0, 5);

  return (
    <Card className="border-zinc-200 bg-white shadow-sm">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">Today's Focus</CardTitle>
            <CardDescription>Prioritized steps — grounded and safe.</CardDescription>
          </div>
          <Button onClick={onOpenSuggestions} variant="outline" className="rounded-full border-zinc-200 bg-white" size="sm">
            Review suggestions
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        <div className="space-y-3">
          {top.map((p) => {
            const chip = severityChip(p.severity);
            const s = p.surface ? surfaceMeta(p.surface) : null;
            return (
              <div key={p.id} className="rounded-3xl border border-zinc-200 bg-white p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className={cx("rounded-full px-3 py-1 text-[11px]", chip.cls)}>{chip.label}</span>
                      {s ? (
                        <Badge variant="outline" className="rounded-full border-zinc-200 bg-white text-zinc-700">
                          <s.icon className="mr-1 h-3.5 w-3.5" />
                          {s.label}
                        </Badge>
                      ) : null}
                      {p.premium ? (
                        <Badge className="rounded-full bg-zinc-950 text-white">Premium</Badge>
                      ) : null}
                    </div>
                    <div className="text-sm font-semibold text-zinc-950">{p.title}</div>
                    {p.description ? <div className="text-xs text-zinc-500">{p.description}</div> : null}
                  </div>
                  <Button variant="outline" className="rounded-2xl border-zinc-200 bg-white" size="sm">
                    Open
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function SurfacesGrid({
  summary,
  proposals,
  issues,
  onOpenSuggestions,
  onOpenIssues,
}: {
  summary: Summary;
  proposals: Proposal[];
  issues: Issue[];
  onOpenSuggestions: (surface?: SurfaceKey) => void;
  onOpenIssues: (surface?: SurfaceKey) => void;
}) {
  const coverageBy = new Map(summary.coverage.map((c) => [c.key, c]));
  const subtitleBy = new Map(summary.llm_subtitles.map((s) => [s.surface, s]));

  const surfaceCards: SurfaceKey[] = ["banking", "invoices", "receipts", "books"];

  const counts = (key: SurfaceKey) => {
    const sug = proposals.filter((p) => p.surface === key).length;
    const iss = issues.filter((i) => i.surface === key).length;
    return { sug, iss };
  };

  return (
    <Card className="border-zinc-200 bg-white shadow-sm">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">Surfaces</CardTitle>
            <CardDescription>Each domain shows coverage, insights, and what needs review.</CardDescription>
          </div>
          <div className="flex gap-2">
            <Button onClick={onOpenIssues} variant="outline" className="rounded-full border-zinc-200 bg-white" size="sm">
              Issues
            </Button>
            <Button onClick={onOpenSuggestions} variant="outline" className="rounded-full border-zinc-200 bg-white" size="sm">
              Suggestions
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {surfaceCards.map((k) => {
            const meta = surfaceMeta(k);
            const cov = coverageBy.get(k);
            const sub = subtitleBy.get(k);
            const c = counts(k);

            return (
              <button
                key={k}
                onClick={() => (c.sug ? onOpenSuggestions(k) : onOpenIssues(k))}
                className="group rounded-3xl border border-zinc-200 bg-white p-5 text-left shadow-sm transition hover:bg-zinc-50"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <div className="grid h-10 w-10 place-items-center rounded-2xl border border-zinc-200 bg-white">
                      <meta.icon className="h-4 w-4 text-zinc-900" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-zinc-950">{meta.label}</div>
                      <div className="mt-1 text-xs text-zinc-500">
                        {sub ? (
                          <span>
                            {sub.subtitle} <span className="ml-1 rounded-full border border-zinc-200 bg-white px-2 py-0.5 text-[10px] text-zinc-600">{sub.source === "ai" ? "AI" : "Auto"}</span>
                          </span>
                        ) : (
                          "No new notes."
                        )}
                      </div>
                    </div>
                  </div>
                  <ChevronRight className="h-4 w-4 text-zinc-400 transition group-hover:translate-x-0.5" />
                </div>

                <div className="mt-4 grid grid-cols-3 gap-3">
                  <StatPill label="Coverage" value={cov ? `${cov.coverage_percent}%` : "—"} />
                  <StatPill label="Suggestions" value={`${c.sug}`} />
                  <StatPill label="Issues" value={`${c.iss}`} />
                </div>

                <div className="mt-4">
                  <div className="flex items-center justify-between text-[11px] text-zinc-500">
                    <span>Progress</span>
                    <span>{cov ? `${cov.covered_items}/${cov.total_items}` : ""}</span>
                  </div>
                  <div className="mt-2">
                    <Progress value={cov?.coverage_percent || 0} />
                  </div>
                </div>

                <div className="mt-4 flex gap-2">
                  <Button
                    className="flex-1 rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      onOpenSuggestions(k);
                    }}
                    disabled={!c.sug}
                  >
                    Review suggestions
                  </Button>
                  <TooltipProvider>
                    <Tooltip delayDuration={120}>
                      <TooltipTrigger asChild>
                        <span>
                          <Button
                            variant="outline"
                            className="rounded-2xl border-zinc-200 bg-white"
                            onClick={(e) => {
                              e.preventDefault();
                              e.stopPropagation();
                              onOpenIssues(k);
                            }}
                          >
                            View issues
                          </Button>
                        </span>
                      </TooltipTrigger>
                      <TooltipContent className="rounded-2xl border-zinc-200 bg-white text-zinc-900 shadow-xl">
                        <div className="text-xs">Open issues and recommended checks.</div>
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              </button>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function StatPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-zinc-50 px-3 py-2">
      <div className="text-[11px] text-zinc-500">{label}</div>
      <div className="mt-1 text-sm font-semibold text-zinc-900">{value}</div>
    </div>
  );
}

function FinanceSnapshotCard({ finance }: { finance: FinanceSnapshot }) {
  return (
    <Card className="border-zinc-200 bg-white shadow-sm">
      <CardHeader>
        <CardTitle className="text-base">Finance Snapshot</CardTitle>
        <CardDescription>Cash, runway, and overdue health.</CardDescription>
      </CardHeader>
      <CardContent className="pt-0 space-y-4">
        <div className="grid grid-cols-3 gap-3">
          <MiniMetric label="Ending cash" value={formatMoney(finance.ending_cash)} />
          <MiniMetric label="Monthly burn" value={formatMoney(finance.monthly_burn)} />
          <MiniMetric label="Runway" value={`${finance.runway_months.toFixed(1)} mo`} />
        </div>

        <div className="h-[160px] rounded-3xl border border-zinc-200 bg-zinc-50 p-3">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={finance.months} margin={{ left: 8, right: 8, top: 5, bottom: 0 }}>
              <XAxis dataKey="m" tick={{ fontSize: 11 }} />
              <YAxis hide />
              <ReTooltip />
              <Area type="monotone" dataKey="rev" stroke="currentColor" fill="currentColor" fillOpacity={0.10} className="text-zinc-950" />
              <Area type="monotone" dataKey="exp" stroke="currentColor" fill="currentColor" fillOpacity={0.05} className="text-zinc-400" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-3xl border border-zinc-200 bg-white p-4">
          <div className="flex items-center justify-between">
            <div className="text-sm font-semibold">Accounts receivable</div>
            <Badge variant="outline" className="rounded-full border-zinc-200 bg-white text-zinc-700">
              overdue {formatMoney(finance.total_overdue)}
            </Badge>
          </div>
          <div className="mt-3 h-[140px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={finance.ar_buckets} margin={{ left: 8, right: 8, top: 5, bottom: 0 }}>
                <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                <YAxis hide />
                <ReTooltip />
                <Bar dataKey="amount" fill="currentColor" className="text-zinc-900" radius={[10, 10, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 text-[11px] text-zinc-500">Use “Invoices” to send reminders and reduce overdue balance.</div>
        </div>
      </CardContent>
    </Card>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
      <div className="text-[11px] text-zinc-500">{label}</div>
      <div className="mt-1 text-base font-semibold text-zinc-950">{value}</div>
    </div>
  );
}

function TaxGuardianCard({ tax }: { tax: TaxGuardian }) {
  const totalAnoms = tax.anomaly_counts.low + tax.anomaly_counts.medium + tax.anomaly_counts.high;
  return (
    <Card className="border-zinc-200 bg-white shadow-sm">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">Tax Guardian</CardTitle>
            <CardDescription>Period {tax.period_key}</CardDescription>
          </div>
          <Badge className="rounded-full bg-zinc-950 text-white">{totalAnoms} flags</Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-3">
        <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
          <div className="text-xs font-semibold text-zinc-700">Net tax (by jurisdiction)</div>
          <div className="mt-3 space-y-2">
            {tax.net_tax.map((x) => (
              <div key={x.jurisdiction} className="flex items-center justify-between rounded-2xl border border-zinc-200 bg-white px-3 py-2">
                <div className="text-sm font-semibold text-zinc-950">{x.jurisdiction}</div>
                <div className="text-sm text-zinc-800">{formatMoney(x.amount)}</div>
              </div>
            ))}
          </div>
          <Separator className="my-4 bg-zinc-200" />
          <div className="grid grid-cols-3 gap-2">
            <TinyChip label="Low" value={`${tax.anomaly_counts.low}`} />
            <TinyChip label="Medium" value={`${tax.anomaly_counts.medium}`} />
            <TinyChip label="High" value={`${tax.anomaly_counts.high}`} />
          </div>
        </div>

        <Button className="w-full rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900">
          <Gauge className="mr-2 h-4 w-4" />
          Open Tax Guardian
        </Button>
      </CardContent>
    </Card>
  );
}

function TinyChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-zinc-200 bg-white px-3 py-2">
      <div className="text-[11px] text-zinc-500">{label}</div>
      <div className="mt-0.5 text-sm font-semibold text-zinc-950">{value}</div>
    </div>
  );
}

function TrustSafetyCard({ safeMode }: { safeMode: boolean }) {
  return (
    <Card className="border-zinc-200 bg-white shadow-sm">
      <CardHeader>
        <CardTitle className="text-base">Trust & Safety</CardTitle>
        <CardDescription>AI proposes. Deterministic checks validate.</CardDescription>
      </CardHeader>
      <CardContent className="pt-0 space-y-3">
        <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
          <div className="flex items-start gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-2xl border border-zinc-200 bg-white">
              <Shield className="h-4 w-4 text-zinc-900" />
            </div>
            <div>
              <div className="text-sm font-semibold text-zinc-950">Safe by design</div>
              <div className="mt-1 text-xs text-zinc-500">
                Suggestions never auto-change your books unless you approve them.
              </div>
            </div>
          </div>

          <Separator className="my-4 bg-zinc-200" />

          <div className="space-y-2">
            <Row label="Safe mode" value={safeMode ? "On" : "Off"} />
            <Row label="High-value changes" value="Always confirm" />
            <Row label="Tax calculations" value="Deterministic" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-2xl border border-zinc-200 bg-white px-3 py-2">
      <div className="text-xs text-zinc-600">{label}</div>
      <div className="text-xs font-semibold text-zinc-900">{value}</div>
    </div>
  );
}

// ---------------------------
// Skeleton
// ---------------------------
function SkeletonBoard() {
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.15fr_0.85fr]">
      <div className="space-y-6">
        <Card className="border-zinc-200 bg-white shadow-sm">
          <CardContent className="p-6">
            <div className="h-5 w-48 animate-pulse rounded bg-zinc-100" />
            <div className="mt-3 h-4 w-[70%] animate-pulse rounded bg-zinc-100" />
            <div className="mt-5 h-24 w-full animate-pulse rounded-3xl bg-zinc-100" />
          </CardContent>
        </Card>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <Card className="border-zinc-200 bg-white shadow-sm"><CardContent className="p-6"><div className="h-48 animate-pulse rounded-3xl bg-zinc-100" /></CardContent></Card>
          <Card className="border-zinc-200 bg-white shadow-sm"><CardContent className="p-6"><div className="h-48 animate-pulse rounded-3xl bg-zinc-100" /></CardContent></Card>
        </div>
        <Card className="border-zinc-200 bg-white shadow-sm"><CardContent className="p-6"><div className="h-64 animate-pulse rounded-3xl bg-zinc-100" /></CardContent></Card>
      </div>
      <div className="space-y-6">
        <Card className="border-zinc-200 bg-white shadow-sm"><CardContent className="p-6"><div className="h-72 animate-pulse rounded-3xl bg-zinc-100" /></CardContent></Card>
        <Card className="border-zinc-200 bg-white shadow-sm"><CardContent className="p-6"><div className="h-56 animate-pulse rounded-3xl bg-zinc-100" /></CardContent></Card>
        <Card className="border-zinc-200 bg-white shadow-sm"><CardContent className="p-6"><div className="h-48 animate-pulse rounded-3xl bg-zinc-100" /></CardContent></Card>
      </div>
    </div>
  );
}

function Footer() {
  return (
    <div className="border-t border-zinc-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-8 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-2xl border border-zinc-200 bg-white">
            <Sparkles className="h-4 w-4 text-zinc-900" />
          </div>
          <div className="text-sm font-semibold">Clover Books</div>
          <div className="text-xs text-zinc-500">AI Companion • Control Tower</div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-zinc-500">
          <span className="rounded-full border border-zinc-200 bg-white px-3 py-1">Customer-safe language</span>
          <span className="rounded-full border border-zinc-200 bg-white px-3 py-1">Panels, not pages</span>
          <span className="rounded-full border border-zinc-200 bg-white px-3 py-1">Calm spacing</span>
        </div>
      </div>
    </div>
  );
}
