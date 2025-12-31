import React, { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  Banknote,
  CheckCircle2,
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
  X,
} from "lucide-react";

import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Badge,
  Separator,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Textarea,
  Switch,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
  Progress,
} from "../components/ui";

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

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

type FocusMode = "all_clear" | "watchlist" | "fire_drill";
type SurfaceKey = "receipts" | "invoices" | "books" | "banking";

type RadarAxis = {
  key: "cash_reconciliation" | "revenue_invoices" | "expenses_receipts" | "tax_compliance";
  label: string;
  score: number;
  open_issues: number;
};

type Coverage = {
  key: SurfaceKey;
  coverage_percent: number;
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

type Proposal = {
  id: string;
  surface: SurfaceKey;
  title: string;
  description: string;
  amount?: number;
  risk: "ready" | "review" | "needs_attention";
  created_at: string;
  target_url?: string;
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

// API Functions
async function fetchSummaryApi(): Promise<Summary> {
  const res = await fetch("/api/agentic/companion/summary", { credentials: "same-origin" });
  if (!res.ok) throw new Error("Failed to load summary");
  const data = await res.json();

  // Transform backend response to our types with comprehensive null safety
  const voice = data.voice || {};
  const radar = data.radar || {};
  const coverage = data.coverage || {};
  const playbook = data.playbook || [];
  const closeReadiness = data.close_readiness || {};
  const llmSubtitles = data.llm_subtitles || {};
  const financeSnapshot = data.finance_snapshot || {};
  const taxBlock = data.tax || {};

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
      surface: p.surface,
      url: p.url,
      premium: p.requires_premium ?? false,
    })),
    close_readiness: {
      status: closeReadiness.status === "ready" ? "ready" : "not_ready",
      period_label: closeReadiness.period_label || "December 2025",
      progress_percent: closeReadiness.progress_percent ?? (closeReadiness.status === "ready" ? 100 : 50),
      blockers: (closeReadiness.blocking_items || closeReadiness.blocking_reasons || []).map((b: any, i: number) => ({
        id: `b${i}`,
        title: typeof b === "string" ? b : (b.reason || b.title || "Blocker"),
        surface: b.surface,
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
      ending_cash: financeSnapshot.ending_cash ?? 0,
      monthly_burn: financeSnapshot.monthly_burn ?? 0,
      runway_months: financeSnapshot.runway_months ?? 0,
      months: financeSnapshot.months || [],
      ar_buckets: financeSnapshot.ar_buckets || [],
      total_overdue: financeSnapshot.total_overdue ?? 0,
    },
    tax_guardian: {
      period_key: taxBlock.period_key || "Current Period",
      net_tax: taxBlock.net_tax || [],
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
    const res = await fetch("/api/companion/v2/proposals/?limit=50", { credentials: "same-origin" });
    if (!res.ok) return [];
    const data = await res.json();
    return (data || []).map((p: any) => ({
      id: p.id,
      surface: p.data?.surface || "banking",
      title: p.data?.title || p.event_type,
      description: p.rationale || "",
      amount: p.data?.amount,
      risk: p.status === "proposed" ? "review" : "ready",
      created_at: p.created_at,
      target_url: p.data?.target_url,
    }));
  } catch { return []; }
}

async function fetchIssuesApi(): Promise<Issue[]> {
  try {
    const res = await fetch("/api/agentic/companion/issues?status=open", { credentials: "same-origin" });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.issues || []).map((i: any) => ({
      id: String(i.id),
      surface: i.surface,
      title: i.title,
      description: i.recommended_action,
      severity: i.severity,
      created_at: i.created_at,
      target_url: i.target_url,
    }));
  } catch { return []; }
}

// Helpers
function formatMoney(x: number | undefined | null) {
  if (x == null || isNaN(x)) return "$0";
  const abs = Math.abs(x);
  if (abs >= 1_000_000) return `$${(x / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `$${(x / 1_000).toFixed(1)}K`;
  return `$${x.toFixed(0)}`;
}

function focusTone(mode: FocusMode) {
  if (mode === "all_clear") return { label: "All clear", className: "bg-emerald-50 text-emerald-700 border border-emerald-200" };
  if (mode === "fire_drill") return { label: "Action needed", className: "bg-rose-50 text-rose-700 border border-rose-200" };
  return { label: "Watchlist", className: "bg-amber-50 text-amber-700 border border-amber-200" };
}

function severityChip(sev: "low" | "medium" | "high") {
  if (sev === "high") return { label: "Needs attention", cls: "bg-rose-50 text-rose-700 border border-rose-200" };
  if (sev === "medium") return { label: "Review recommended", cls: "bg-amber-50 text-amber-700 border border-amber-200" };
  return { label: "Ready", cls: "bg-emerald-50 text-emerald-700 border border-emerald-200" };
}

function riskChip(risk: Proposal["risk"]) {
  if (risk === "needs_attention") return { label: "Needs attention", cls: "bg-rose-50 text-rose-700 border border-rose-200" };
  if (risk === "review") return { label: "Review", cls: "bg-amber-50 text-amber-700 border border-amber-200" };
  return { label: "Ready", cls: "bg-emerald-50 text-emerald-700 border border-emerald-200" };
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

// Query-param panel routing
function usePanelRouting() {
  const [panel, setPanel] = useState<null | "suggestions" | "issues" | "close">(null);

  useEffect(() => {
    const sync = () => {
      const u = new URL(window.location.href);
      const p = (u.searchParams.get("panel") || "").toLowerCase();
      setPanel(p === "suggestions" || p === "issues" || p === "close" ? (p as any) : null);
    };
    sync();
    window.addEventListener("popstate", sync);
    return () => window.removeEventListener("popstate", sync);
  }, []);

  const open = (p: "suggestions" | "issues" | "close") => {
    const u = new URL(window.location.href);
    u.searchParams.set("panel", p);
    window.history.pushState({}, "", u);
    setPanel(p);
  };

  const close = () => {
    const u = new URL(window.location.href);
    u.searchParams.delete("panel");
    window.history.pushState({}, "", u);
    setPanel(null);
  };

  return { panel, open, close };
}

// Main Component
export default function AICompanionControlTower() {
  const { panel, open, close } = usePanelRouting();
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
      try {
        const [s, p, i] = await Promise.all([fetchSummaryApi(), fetchProposalsApi(), fetchIssuesApi()]);
        if (!alive) return;
        setSummary(s);
        setProposals(p);
        setIssues(i);
      } catch (e) {
        console.error("Failed to load companion data", e);
      }
      setLoading(false);
    })();
    return () => { alive = false; };
  }, []);

  const radarData = useMemo(() => summary?.radar.map((r) => ({ axis: r.label, score: r.score })) || [], [summary]);
  const focus = summary ? focusTone(summary.voice.focus_mode) : focusTone("watchlist");
  const openCounts = useMemo(() => ({
    totalIssues: summary?.radar.reduce((acc, r) => acc + r.open_issues, 0) || 0,
    totalSuggestions: proposals.length,
  }), [summary, proposals]);

  const refresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      const s = await fetchSummaryApi();
      setSummary(s);
    } catch { }
    setRefreshing(false);
  };

  if (loading || !summary) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-zinc-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white text-zinc-950">
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

      <div className="mx-auto max-w-7xl px-4 pb-12 pt-8">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.15fr_0.85fr]">
          <div className="space-y-6">
            <HeroVoice summary={summary} focus={focus} />
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              <HealthPulseCard summary={summary} radarData={radarData} onOpenIssues={() => open("issues")} />
              <CloseReadinessCard summary={summary} onOpenClose={() => open("close")} />
            </div>
            <TodayFocusCard items={summary.playbook} onOpenSuggestions={() => open("suggestions")} />
            <SurfacesGrid summary={summary} proposals={proposals} issues={issues} onOpenSuggestions={() => open("suggestions")} onOpenIssues={() => open("issues")} />
          </div>
          <div className="space-y-6">
            <FinanceSnapshotCard finance={summary.finance_snapshot} />
            <TaxGuardianCard tax={summary.tax_guardian} />
            <TrustSafetyCard safeMode={safeMode} />
          </div>
        </div>
      </div>

      <PanelShell open={!!panel} onClose={close} title={panel === "suggestions" ? "AI Suggestions" : panel === "issues" ? "Open Issues" : "Close Assistant"}>
        <AnimatePresence mode="wait">
          {panel === "suggestions" && <SuggestionsPanel key="suggestions" proposals={proposals} onApplied={(id) => setProposals((p) => p.filter((x) => x.id !== id))} onDismissed={(id) => setProposals((p) => p.filter((x) => x.id !== id))} />}
          {panel === "issues" && <IssuesPanel key="issues" issues={issues} />}
          {panel === "close" && <CloseAssistantDrawer key="close" summary={summary} />}
        </AnimatePresence>
      </PanelShell>
    </div>
  );
}

// Sub-components (abbreviated for file size)
function TopHeader({ summary, loading, refreshing, onRefresh, onOpenSuggestions, onOpenIssues, onOpenClose, counts, safeMode, setSafeMode }: any) {
  return (
    <div className="sticky top-0 z-40 border-b border-zinc-200 bg-white/80 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-2xl border border-zinc-200 bg-white shadow-sm">
            <Sparkles className="h-4 w-4 text-zinc-900" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold tracking-tight">AI Companion</div>
            <div className="text-[11px] text-zinc-500">Control Tower • Safe suggestions</div>
          </div>
        </div>
        <div className="hidden items-center gap-2 md:flex">
          <Badge variant="outline" className="rounded-full">{loading ? "…" : `${counts.totalSuggestions} suggestions`}</Badge>
          <Badge variant="outline" className="rounded-full">{loading ? "…" : `${counts.totalIssues} issues`}</Badge>
          <div className="flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-3 py-2 shadow-sm">
            <Shield className="h-4 w-4 text-zinc-700" />
            <div className="text-xs text-zinc-700">Safe mode</div>
            <Switch checked={safeMode} onCheckedChange={setSafeMode} />
          </div>
          <Button onClick={onRefresh} variant="outline" className="rounded-full" disabled={refreshing}>
            {refreshing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}Refresh
          </Button>
          <Button onClick={onOpenSuggestions} className="rounded-full bg-zinc-950 text-white hover:bg-zinc-900">AI Suggestions<ArrowRight className="ml-2 h-4 w-4" /></Button>
        </div>
      </div>
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 pb-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={onOpenIssues} variant="outline" className="rounded-full" size="sm"><AlertTriangle className="mr-2 h-4 w-4" />Open issues</Button>
          <Button onClick={onOpenClose} variant="outline" className="rounded-full" size="sm"><Lock className="mr-2 h-4 w-4" />Close assistant</Button>
        </div>
        <div className="text-[11px] text-zinc-500">{summary ? `Updated ${new Date(summary.generated_at).toLocaleString()}` : ""}</div>
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
        </div>
      </CardContent>
    </Card>
  );
}

function HealthPulseCard({ summary, radarData, onOpenIssues }: { summary: Summary; radarData: any[]; onOpenIssues: () => void }) {
  const overall = Math.round(summary.radar.reduce((acc, r) => acc + r.score, 0) / (summary.radar.length || 1));
  const open = summary.radar.reduce((acc, r) => acc + r.open_issues, 0);

  return (
    <Card className="border-zinc-200 bg-white shadow-sm">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div><CardTitle className="text-base">Health Pulse</CardTitle><CardDescription>Four domains, one glance.</CardDescription></div>
          <div className="flex items-center gap-2">
            <Badge className="rounded-full bg-zinc-950 text-white">{overall}/100</Badge>
            <Button onClick={onOpenIssues} variant="outline" className="rounded-full" size="sm">{open} open<ChevronRight className="ml-1 h-4 w-4" /></Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="h-[200px] rounded-3xl border border-zinc-200 bg-zinc-50 p-3">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} outerRadius="75%">
              <PolarGrid />
              <PolarAngleAxis dataKey="axis" tick={{ fontSize: 11 }} />
              <Radar dataKey="score" stroke="currentColor" fill="currentColor" fillOpacity={0.12} className="text-zinc-900" />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

function CloseReadinessCard({ summary, onOpenClose }: { summary: Summary; onOpenClose: () => void }) {
  const cr = summary.close_readiness;
  return (
    <Card className="border-zinc-200 bg-white shadow-sm">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div><CardTitle className="text-base">Close Readiness</CardTitle><CardDescription>{cr.period_label}</CardDescription></div>
          <Badge className={cx("rounded-full", cr.status === "ready" ? "bg-zinc-950 text-white" : "bg-zinc-100 text-zinc-900 border")}>{cr.status === "ready" ? "Ready" : "Not ready"}</Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
          <div className="flex items-center justify-between"><div className="text-xs font-semibold text-zinc-700">Progress</div><div className="text-xs text-zinc-600">{cr.progress_percent}%</div></div>
          <div className="mt-2"><Progress value={cr.progress_percent} /></div>
          {cr.blockers.length > 0 && (
            <div className="mt-4 space-y-2">
              {cr.blockers.slice(0, 2).map((b) => (
                <div key={b.id} className="flex items-start justify-between gap-3 rounded-2xl border border-zinc-200 bg-white px-3 py-2">
                  <div className="text-sm font-semibold text-zinc-950">{b.title}</div>
                  <span className={cx("rounded-full px-3 py-1 text-[11px]", severityChip(b.severity).cls)}>{severityChip(b.severity).label}</span>
                </div>
              ))}
            </div>
          )}
          <div className="mt-4"><Button onClick={onOpenClose} className="w-full rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900"><Lock className="mr-2 h-4 w-4" />Open Close Assistant</Button></div>
        </div>
      </CardContent>
    </Card>
  );
}

function TodayFocusCard({ items, onOpenSuggestions }: { items: PlaybookItem[]; onOpenSuggestions: () => void }) {
  return (
    <Card className="border-zinc-200 bg-white shadow-sm">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div><CardTitle className="text-base">Today's Focus</CardTitle><CardDescription>Prioritized steps.</CardDescription></div>
          <Button onClick={onOpenSuggestions} variant="outline" className="rounded-full" size="sm">Review<ChevronRight className="ml-1 h-4 w-4" /></Button>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-3">
          {items.slice(0, 4).map((p) => {
            const chip = severityChip(p.severity);
            return (
              <div key={p.id} className="rounded-3xl border border-zinc-200 bg-white p-4">
                <div className="flex items-center gap-2 mb-2">
                  <span className={cx("rounded-full px-3 py-1 text-[11px]", chip.cls)}>{chip.label}</span>
                  {p.surface && <Badge variant="outline" className="rounded-full">{surfaceMeta(p.surface).label}</Badge>}
                </div>
                <div className="text-sm font-semibold text-zinc-950">{p.title}</div>
                {p.description && <div className="text-xs text-zinc-500 mt-1">{p.description}</div>}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function SurfacesGrid({ summary, proposals, issues, onOpenSuggestions, onOpenIssues }: any) {
  const coverageBy = new Map<SurfaceKey, Coverage>(summary.coverage.map((c: Coverage) => [c.key, c]));
  const subtitleBy = new Map<SurfaceKey, LlmSubtitle>(summary.llm_subtitles.map((s: LlmSubtitle) => [s.surface, s]));
  const surfaceCards: SurfaceKey[] = ["banking", "invoices", "receipts", "books"];
  const counts = (key: SurfaceKey) => ({ sug: proposals.filter((p: Proposal) => p.surface === key).length, iss: issues.filter((i: Issue) => i.surface === key).length });

  return (
    <Card className="border-zinc-200 bg-white shadow-sm">
      <CardHeader><CardTitle className="text-base">Surfaces</CardTitle></CardHeader>
      <CardContent className="pt-0">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {surfaceCards.map((k) => {
            const meta = surfaceMeta(k);
            const cov: Coverage | undefined = coverageBy.get(k);
            const sub: LlmSubtitle | undefined = subtitleBy.get(k);
            const c = counts(k);
            return (
              <button key={k} onClick={() => c.sug ? onOpenSuggestions() : onOpenIssues()} className="group rounded-3xl border border-zinc-200 bg-white p-5 text-left shadow-sm transition hover:bg-zinc-50">
                <div className="flex items-start gap-3">
                  <div className="grid h-10 w-10 place-items-center rounded-2xl border border-zinc-200 bg-white"><meta.icon className="h-4 w-4 text-zinc-900" /></div>
                  <div>
                    <div className="text-sm font-semibold text-zinc-950">{meta.label}</div>
                    {sub && <div className="mt-1 text-xs text-zinc-500">{sub.subtitle}</div>}
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-3 gap-3">
                  <div className="rounded-2xl border border-zinc-200 bg-zinc-50 px-3 py-2"><div className="text-[11px] text-zinc-500">Coverage</div><div className="text-sm font-semibold text-zinc-900">{cov?.coverage_percent || 0}%</div></div>
                  <div className="rounded-2xl border border-zinc-200 bg-zinc-50 px-3 py-2"><div className="text-[11px] text-zinc-500">Suggestions</div><div className="text-sm font-semibold text-zinc-900">{c.sug}</div></div>
                  <div className="rounded-2xl border border-zinc-200 bg-zinc-50 px-3 py-2"><div className="text-[11px] text-zinc-500">Issues</div><div className="text-sm font-semibold text-zinc-900">{c.iss}</div></div>
                </div>
              </button>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function FinanceSnapshotCard({ finance }: { finance: FinanceSnapshot }) {
  return (
    <Card className="border-zinc-200 bg-white shadow-sm">
      <CardHeader><CardTitle className="text-base">Finance Snapshot</CardTitle></CardHeader>
      <CardContent className="pt-0 space-y-4">
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4"><div className="text-[11px] text-zinc-500">Ending cash</div><div className="mt-1 text-base font-semibold text-zinc-950">{formatMoney(finance.ending_cash)}</div></div>
          <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4"><div className="text-[11px] text-zinc-500">Monthly burn</div><div className="mt-1 text-base font-semibold text-zinc-950">{formatMoney(finance.monthly_burn)}</div></div>
          <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4"><div className="text-[11px] text-zinc-500">Runway</div><div className="mt-1 text-base font-semibold text-zinc-950">{finance.runway_months?.toFixed(1) || 0} mo</div></div>
        </div>
        {finance.months?.length > 0 && (
          <div className="h-[140px] rounded-3xl border border-zinc-200 bg-zinc-50 p-3">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={finance.months}>
                <XAxis dataKey="m" tick={{ fontSize: 11 }} />
                <Area type="monotone" dataKey="rev" stroke="#18181b" fill="#18181b" fillOpacity={0.1} />
                <Area type="monotone" dataKey="exp" stroke="#a1a1aa" fill="#a1a1aa" fillOpacity={0.05} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function TaxGuardianCard({ tax }: { tax: TaxGuardian }) {
  const anomalyCounts = tax?.anomaly_counts || { low: 0, medium: 0, high: 0 };
  const totalAnoms = (anomalyCounts.low || 0) + (anomalyCounts.medium || 0) + (anomalyCounts.high || 0);
  const netTax = tax?.net_tax || [];
  const periodKey = tax?.period_key || "Current Period";

  return (
    <Card className="border-zinc-200 bg-white shadow-sm">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div><CardTitle className="text-base">Tax Guardian</CardTitle><CardDescription>{periodKey}</CardDescription></div>
          <Badge className="rounded-full bg-zinc-950 text-white">{totalAnoms} flags</Badge>
        </div>
      </CardHeader>
      <CardContent className="pt-0 space-y-3">
        <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
          <div className="text-xs font-semibold text-zinc-700">Net tax</div>
          <div className="mt-3 space-y-2">
            {netTax.length > 0 ? netTax.map((x) => (
              <div key={x.jurisdiction} className="flex items-center justify-between rounded-2xl border border-zinc-200 bg-white px-3 py-2">
                <div className="text-sm font-semibold text-zinc-950">{x.jurisdiction}</div>
                <div className="text-sm text-zinc-800">{formatMoney(x.amount)}</div>
              </div>
            )) : (
              <div className="text-xs text-zinc-500">No tax data available</div>
            )}
          </div>
        </div>
        <Button className="w-full rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900" onClick={() => window.location.href = "/ai-companion/tax"}><Gauge className="mr-2 h-4 w-4" />Open Tax Guardian</Button>
      </CardContent>
    </Card>
  );
}

function TrustSafetyCard({ safeMode }: { safeMode: boolean }) {
  return (
    <Card className="border-zinc-200 bg-white shadow-sm">
      <CardHeader><CardTitle className="text-base">Trust & Safety</CardTitle></CardHeader>
      <CardContent className="pt-0">
        <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
          <div className="flex items-start gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-2xl border border-zinc-200 bg-white"><Shield className="h-4 w-4 text-zinc-900" /></div>
            <div><div className="text-sm font-semibold text-zinc-950">Safe by design</div><div className="mt-1 text-xs text-zinc-500">Suggestions never auto-change your books.</div></div>
          </div>
          <Separator className="my-4 bg-zinc-200" />
          <div className="space-y-2">
            <div className="flex items-center justify-between rounded-2xl border border-zinc-200 bg-white px-3 py-2"><div className="text-xs text-zinc-600">Safe mode</div><div className="text-xs font-semibold text-zinc-900">{safeMode ? "On" : "Off"}</div></div>
            <div className="flex items-center justify-between rounded-2xl border border-zinc-200 bg-white px-3 py-2"><div className="text-xs text-zinc-600">Tax calculations</div><div className="text-xs font-semibold text-zinc-900">Deterministic</div></div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function PanelShell({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    if (open) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="fixed inset-0 z-50 bg-black/20" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.aside className="fixed right-0 top-0 z-50 h-full w-full max-w-[520px] border-l border-zinc-200 bg-white shadow-2xl" initial={{ x: 40, opacity: 0 }} animate={{ x: 0, opacity: 1 }} exit={{ x: 40, opacity: 0 }} transition={{ type: "spring", stiffness: 280, damping: 30 }}>
            <div className="flex h-full flex-col">
              <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4">
                <div className="text-sm font-semibold">{title}</div>
                <Button variant="ghost" size="icon" onClick={onClose} className="rounded-full"><X className="h-4 w-4" /></Button>
              </div>
              <div className="flex-1 overflow-auto p-5">{children}</div>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function SuggestionsPanel({ proposals, onApplied, onDismissed }: { proposals: Proposal[]; onApplied: (id: string) => void; onDismissed: (id: string) => void }) {
  if (!proposals.length) return <div className="rounded-3xl border border-zinc-200 bg-white p-6 text-center"><div className="text-sm font-semibold text-zinc-950">No suggestions</div><div className="mt-2 text-xs text-zinc-500">Nothing to review right now.</div></div>;

  return (
    <div className="space-y-3">
      {proposals.map((p) => {
        const meta = surfaceMeta(p.surface);
        const chip = riskChip(p.risk);
        return (
          <div key={p.id} className="rounded-3xl border border-zinc-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <span className={cx("rounded-full px-3 py-1 text-[11px]", chip.cls)}>{chip.label}</span>
              <Badge variant="outline" className="rounded-full"><meta.icon className="mr-1 h-3.5 w-3.5" />{meta.label}</Badge>
            </div>
            <div className="text-sm font-semibold text-zinc-950">{p.title}</div>
            <div className="text-xs text-zinc-500 mt-1">{p.description}</div>
            <div className="mt-4 flex gap-2">
              <Button className="rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900" onClick={() => onApplied(p.id)}><CheckCircle2 className="mr-2 h-4 w-4" />Apply</Button>
              <Button variant="outline" className="rounded-2xl" onClick={() => onDismissed(p.id)}>Dismiss</Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function IssuesPanel({ issues }: { issues: Issue[] }) {
  if (!issues.length) return <div className="rounded-3xl border border-zinc-200 bg-white p-6 text-center"><div className="text-sm font-semibold text-zinc-950">No issues</div><div className="mt-2 text-xs text-zinc-500">Everything looks clear.</div></div>;

  return (
    <div className="space-y-3">
      {issues.map((i) => {
        const chip = severityChip(i.severity);
        const meta = surfaceMeta(i.surface);
        return (
          <div key={i.id} className="rounded-3xl border border-zinc-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <span className={cx("rounded-full px-3 py-1 text-[11px]", chip.cls)}>{chip.label}</span>
              <Badge variant="outline" className="rounded-full"><meta.icon className="mr-1 h-3.5 w-3.5" />{meta.label}</Badge>
            </div>
            <div className="text-sm font-semibold text-zinc-950">{i.title}</div>
            {i.description && <div className="text-xs text-zinc-500 mt-1">{i.description}</div>}
            <div className="mt-4"><Button className="rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900" onClick={() => window.location.href = i.target_url || "#"}>Review<ChevronRight className="ml-1 h-4 w-4" /></Button></div>
          </div>
        );
      })}
    </div>
  );
}

function CloseAssistantDrawer({ summary }: { summary: Summary }) {
  const cr = summary.close_readiness;
  return (
    <div className="space-y-4">
      <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
        <div className="text-xs font-semibold text-zinc-700">Goal</div>
        <div className="mt-1 text-xs text-zinc-500">Get to "Ready" by resolving blockers.</div>
      </div>
      <Card className="border-zinc-200 bg-white shadow-sm">
        <CardHeader><CardTitle className="text-base">{cr.period_label}</CardTitle></CardHeader>
        <CardContent className="pt-0 space-y-3">
          <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
            <div className="flex items-center justify-between"><div className="text-xs font-semibold text-zinc-700">Progress</div><div className="text-xs text-zinc-600">{cr.progress_percent}%</div></div>
            <div className="mt-2"><Progress value={cr.progress_percent} /></div>
          </div>
          <div className="text-sm font-semibold">Blockers</div>
          <div className="space-y-2">
            {cr.blockers.map((b) => (
              <div key={b.id} className="rounded-3xl border border-zinc-200 bg-white p-4">
                <div className="text-sm font-semibold text-zinc-950">{b.title}</div>
                <div className="mt-4"><Button className="rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900" onClick={() => window.location.href = b.url || "#"}>Review<ChevronRight className="ml-1 h-4 w-4" /></Button></div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
