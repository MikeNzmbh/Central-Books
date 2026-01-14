import React, { useMemo, useState } from "react";
import {
  Banknote,
  CheckCircle2,
  ChevronRight,
  FileText,
  Layers,
  ListChecks,
  Loader2,
  Search,
} from "lucide-react";
import { ensureCsrfToken } from "../utils/csrf";
import { toCustomerCopy } from "./companionCopy";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { buildApiUrl, getAccessToken } from "@/api/client";

type SurfaceKey = "receipts" | "invoices" | "books" | "banking";

type Proposal = {
  id: string;
  surface: SurfaceKey;
  title: string;
  description: string;
  amount?: number;
  risk: "ready" | "review" | "needs_attention";
  customer_action_kind?: "apply" | "review" | "info";
  risk_level?: "low" | "medium" | "high";
  preview_effects?: string[];
  source_agent?: string | null;
  created_at: string;
  target_url?: string;
};

interface SuggestionsPanelProps {
  proposals: Proposal[];
  onApplied: (id: string) => void;
  onDismissed: (id: string) => void;
  surface?: string | null;
  agentFilter?: string | null;
  loading?: boolean;
  engineMode?: string | null;
}

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

function normalizeSurfaceKey(value?: string | null): SurfaceKey | null {
  if (!value) return null;
  const v = value.toLowerCase();
  if (v === "bank" || v === "banking" || v === "bank_review" || v === "bank-review") return "banking";
  if (v === "books" || v === "book" || v === "books_review" || v === "books-review") return "books";
  if (v === "receipts" || v === "expenses") return "receipts";
  if (v === "invoices" || v === "revenue") return "invoices";
  return null;
}

function actionKindForProposal(proposal: Proposal): "apply" | "review" | "info" {
  if (proposal.customer_action_kind === "apply" || proposal.customer_action_kind === "review" || proposal.customer_action_kind === "info") {
    return proposal.customer_action_kind;
  }
  return proposal.risk === "ready" ? "apply" : "review";
}

function riskLevelForProposal(proposal: Proposal): "low" | "medium" | "high" {
  if (proposal.risk_level === "low" || proposal.risk_level === "medium" || proposal.risk_level === "high") {
    return proposal.risk_level;
  }
  if (proposal.risk === "needs_attention") return "high";
  if (proposal.risk === "review") return "medium";
  return "low";
}

function formatMoney(x: number | undefined | null) {
  if (x == null || Number.isNaN(x)) return "$0";
  const abs = Math.abs(x);
  if (abs >= 1_000_000) return `$${(x / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `$${(x / 1_000).toFixed(1)}K`;
  return `$${x.toFixed(0)}`;
}

function riskChip(risk: Proposal["risk"]) {
  if (risk === "needs_attention") return { label: "Needs attention", cls: "bg-zinc-950 text-white" };
  if (risk === "review") return { label: "Review", cls: "bg-zinc-100 text-zinc-900 border border-zinc-200" };
  return { label: "Ready", cls: "bg-zinc-50 text-zinc-700 border border-zinc-200" };
}

function surfaceMeta(key: SurfaceKey) {
  const map: Record<SurfaceKey, { label: string; icon: React.ComponentType<{ className?: string }> }> = {
    receipts: { label: "Receipts", icon: FileText },
    invoices: { label: "Invoices", icon: Layers },
    books: { label: "Books Review", icon: ListChecks },
    banking: { label: "Banking", icon: Banknote },
  };
  return map[key];
}

export default function SuggestionsPanel({
  proposals,
  onApplied,
  onDismissed,
  surface,
  agentFilter,
  loading = false,
  engineMode,
}: SuggestionsPanelProps) {
  const [tab, setTab] = useState<"all" | "ready" | "review" | "needs_attention">("all");
  const [q, setQ] = useState("");
  const [batchOpen, setBatchOpen] = useState(false);
  const [batchBusy, setBatchBusy] = useState(false);

  const surfaceKey = normalizeSurfaceKey(surface);

  const filtered = useMemo(() => {
    let items = proposals;
    if (surfaceKey) items = items.filter((p) => p.surface === surfaceKey);
    if (agentFilter) {
      const agentNeedle = agentFilter.toLowerCase();
      items = items.filter((p) => (p.source_agent || "").toLowerCase() === agentNeedle);
    }
    if (tab !== "all") items = items.filter((p) => p.risk === tab);
    if (q.trim()) {
      const s = q.trim().toLowerCase();
      items = items.filter((p) => (p.title + " " + p.description).toLowerCase().includes(s));
    }
    return items;
  }, [proposals, tab, q, surfaceKey, agentFilter]);

  const readyItems = useMemo(
    () => filtered.filter((p) => actionKindForProposal(p) === "apply" && riskLevelForProposal(p) === "low"),
    [filtered]
  );
  const batchAllowed = engineMode === "autopilot_limited" || engineMode === "drafts";
  const canBatchApply = batchAllowed && readyItems.length > 0;

  const applyBatch = async () => {
    if (!canBatchApply) return;
    setBatchBusy(true);
    try {
      const csrf = await ensureCsrfToken();
      const headers: Record<string, string> = { Accept: "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;
      const token = getAccessToken();
      if (token) headers.Authorization = `Bearer ${token}`;
      for (const proposal of readyItems) {
        const res = await fetch(buildApiUrl(`/api/companion/v2/shadow-events/${proposal.id}/apply/`), {
          method: "POST",
          credentials: "same-origin",
          headers,
        });
        if (res.ok) {
          onApplied(proposal.id);
        }
      }
      setBatchOpen(false);
    } catch (err) {
      console.error("Failed to batch apply proposals", err);
    } finally {
      setBatchBusy(false);
    }
  };

  if (loading) {
    return <PanelLoading label="Loading suggestions..." />;
  }

  return (
    <div className="space-y-4">
      <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
        <div className="text-xs font-semibold text-zinc-700">What you're reviewing</div>
        <div className="mt-1 text-xs text-zinc-500">
          These are safe suggestions. Applying will update your books only after confirmation.
        </div>
      </div>

      {canBatchApply ? (
        <div className="rounded-3xl border border-zinc-200 bg-white p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs font-semibold text-zinc-900 uppercase tracking-wide">Apply safe items</div>
              <div className="mt-1 text-xs text-zinc-500">{readyItems.length} ready to apply</div>
            </div>
            <Button
              className="rounded-full bg-zinc-950 text-white hover:bg-zinc-900"
              onClick={() => setBatchOpen(true)}
            >
              Apply safe items
            </Button>
          </div>
        </div>
      ) : null}

      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search suggestions..."
          className="h-11 rounded-2xl border-zinc-200 bg-white pl-10"
        />
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
        <TabsList className="grid w-full grid-cols-4 rounded-2xl bg-zinc-100 p-1">
          <TabsTrigger value="all" className="rounded-xl">
            All
          </TabsTrigger>
          <TabsTrigger value="ready" className="rounded-xl">
            Ready
          </TabsTrigger>
          <TabsTrigger value="review" className="rounded-xl">
            Review
          </TabsTrigger>
          <TabsTrigger value="needs_attention" className="rounded-xl">
            Attention
          </TabsTrigger>
        </TabsList>
        <TabsContent value={tab} className="mt-4 space-y-3">
          {!filtered.length ? (
            <EmptyPanel title="No suggestions" description="Nothing matches the current filter." />
          ) : (
            filtered.map((p) => (
              <SuggestionCard
                key={p.id}
                proposal={p}
                onApplied={onApplied}
                onDismissed={onDismissed}
              />
            ))
          )}
        </TabsContent>
      </Tabs>

      <Dialog open={batchOpen} onOpenChange={setBatchOpen}>
        <DialogContent className="rounded-3xl border-zinc-200 bg-white">
          <DialogHeader>
            <DialogTitle className="text-zinc-950">Apply {readyItems.length} safe items?</DialogTitle>
            <DialogDescription className="text-zinc-500">
              We'll apply low-risk items and keep a clear audit trail.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
            <div className="text-xs font-semibold text-zinc-700">What will change</div>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-zinc-800">
              <li>Apply low-risk suggestions that are ready.</li>
              <li>Link each change to its source for traceability.</li>
              <li>Keep your books consistent with your settings.</li>
            </ul>
          </div>
          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              className="rounded-2xl border-zinc-200 bg-white"
              onClick={() => setBatchOpen(false)}
            >
              Cancel
            </Button>
            <Button
              className="rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900"
              onClick={applyBatch}
              disabled={batchBusy}
            >
              {batchBusy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Apply
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SuggestionCard({
  proposal,
  onApplied,
  onDismissed,
}: {
  proposal: Proposal;
  onApplied: (id: string) => void;
  onDismissed: (id: string) => void;
}) {
  const meta = surfaceMeta(proposal.surface);
  const chip = riskChip(proposal.risk);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [dismissOpen, setDismissOpen] = useState(false);

  const [busy, setBusy] = useState<null | "apply" | "dismiss">(null);
  const [note, setNote] = useState("");
  const [applyNote, setApplyNote] = useState("");

  const actionKind = actionKindForProposal(proposal);
  const riskLevel = riskLevelForProposal(proposal);
  const requiresNote = actionKind === "apply" && riskLevel === "high";
  const isApplyAllowed = actionKind === "apply";
  const previewEffects =
    proposal.preview_effects && proposal.preview_effects.length > 0
      ? proposal.preview_effects
      : [
          "Make a change to your books based on this suggestion.",
          "Link it to the source item for traceability.",
          "Keep reports consistent with your policies.",
        ];
  const safeTitle = toCustomerCopy(proposal.title);
  const safeDescription = toCustomerCopy(proposal.description);
  const safePreviewEffects = previewEffects.map((item) => toCustomerCopy(item));

  const apply = async () => {
    if (requiresNote && !applyNote.trim()) return;
    setBusy("apply");
    try {
      const csrf = await ensureCsrfToken();
      const headers: Record<string, string> = { Accept: "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;
      const token = getAccessToken();
      if (token) headers.Authorization = `Bearer ${token}`;
      const res = await fetch(buildApiUrl(`/api/companion/v2/shadow-events/${proposal.id}/apply/`), {
        method: "POST",
        credentials: "same-origin",
        headers,
      });
      if (!res.ok) throw new Error("Failed to apply");
      onApplied(proposal.id);
      setConfirmOpen(false);
      setApplyNote("");
    } catch (err) {
      console.error("Failed to apply proposal", err);
    } finally {
      setBusy(null);
    }
  };

  const dismiss = async () => {
    setBusy("dismiss");
    try {
      const csrf = await ensureCsrfToken();
      const headers: Record<string, string> = {
        Accept: "application/json",
        "Content-Type": "application/json",
      };
      if (csrf) headers["X-CSRFToken"] = csrf;
      const token = getAccessToken();
      if (token) headers.Authorization = `Bearer ${token}`;
      const res = await fetch(buildApiUrl(`/api/companion/v2/shadow-events/${proposal.id}/reject/`), {
        method: "POST",
        credentials: "same-origin",
        headers,
        body: JSON.stringify({ reason: note || "Dismissed" }),
      });
      if (!res.ok) throw new Error("Failed to dismiss");
      onDismissed(proposal.id);
      setDismissOpen(false);
      setNote("");
    } catch (err) {
      console.error("Failed to dismiss proposal", err);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="rounded-3xl border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className={cx("rounded-full px-3 py-1 text-[11px]", chip.cls)}>{chip.label}</span>
            <Badge variant="outline" className="rounded-full border-zinc-200 bg-white text-zinc-700">
              <meta.icon className="mr-1 h-3.5 w-3.5" />
              {meta.label}
            </Badge>
            {proposal.amount != null ? (
              <Badge variant="outline" className="rounded-full border-zinc-200 bg-white text-zinc-700">
                {formatMoney(proposal.amount)}
              </Badge>
            ) : null}
          </div>
          <div className="text-sm font-semibold text-zinc-950">{safeTitle}</div>
          <div className="text-xs text-zinc-500">{safeDescription}</div>
        </div>
        <div className="text-[11px] text-zinc-500">{new Date(proposal.created_at).toLocaleString()}</div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {isApplyAllowed ? (
          <Button
            className="rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900"
            onClick={() => setConfirmOpen(true)}
            disabled={busy === "apply"}
          >
            {busy === "apply" ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="mr-2 h-4 w-4" />
            )}
            Apply this change
          </Button>
        ) : null}
        <Button
          variant="outline"
          className="rounded-2xl border-zinc-200 bg-white"
          onClick={() => setDismissOpen(true)}
          disabled={busy === "dismiss"}
        >
          Dismiss
        </Button>
        <TooltipProvider>
          <Tooltip delayDuration={120}>
            <TooltipTrigger asChild>
              <span>
                <Button
                  variant="outline"
                  className="rounded-2xl border-zinc-200 bg-white"
                  onClick={() => (proposal.target_url ? (window.location.href = proposal.target_url) : undefined)}
                  disabled={!proposal.target_url}
                >
                  {actionKind === "review" ? "Open review" : "Review details"}
                  <ChevronRight className="ml-1 h-4 w-4" />
                </Button>
              </span>
            </TooltipTrigger>
            {!proposal.target_url ? (
              <TooltipContent className="rounded-2xl border-zinc-200 bg-white text-zinc-900 shadow-xl">
                <div className="text-xs">Review link not available yet.</div>
              </TooltipContent>
            ) : null}
          </Tooltip>
        </TooltipProvider>
      </div>

      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="rounded-3xl border-zinc-200 bg-white">
          <DialogHeader>
            <DialogTitle className="text-zinc-950">Apply this change?</DialogTitle>
            <DialogDescription className="text-zinc-500">
              We'll apply it safely and keep a clear audit trail.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
            <div className="text-xs font-semibold text-zinc-700">What this will do</div>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-zinc-800">
              {safePreviewEffects.map((item, index) => (
                <li key={`${proposal.id}-effect-${index}`}>{item}</li>
              ))}
            </ul>
          </div>
          {requiresNote ? (
            <div className="rounded-3xl border border-amber-200 bg-amber-50 p-4">
              <div className="text-xs font-semibold text-amber-900">High-risk note</div>
              <div className="mt-1 text-xs text-amber-700">
                Add a short note about why this change is correct.
              </div>
              <Textarea
                value={applyNote}
                onChange={(e) => setApplyNote(e.target.value)}
                placeholder="Example: Approved after reviewing the receipt."
                className="mt-3 min-h-[96px] rounded-3xl border-amber-200 bg-white"
              />
            </div>
          ) : null}
          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              className="rounded-2xl border-zinc-200 bg-white"
              onClick={() => setConfirmOpen(false)}
            >
              Cancel
            </Button>
            <Button
              className="rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900"
              onClick={apply}
              disabled={busy === "apply" || (requiresNote && !applyNote.trim())}
            >
              {busy === "apply" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Apply
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={dismissOpen} onOpenChange={setDismissOpen}>
        <DialogContent className="rounded-3xl border-zinc-200 bg-white">
          <DialogHeader>
            <DialogTitle className="text-zinc-950">Dismiss this suggestion</DialogTitle>
            <DialogDescription className="text-zinc-500">
              Optional: leave a note so we learn your preference.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Example: This vendor should be categorized differently."
            className="min-h-[120px] rounded-3xl border-zinc-200"
          />
          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              className="rounded-2xl border-zinc-200 bg-white"
              onClick={() => setDismissOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="outline"
              className="rounded-2xl border-zinc-200 bg-white"
              onClick={dismiss}
              disabled={busy === "dismiss"}
            >
              {busy === "dismiss" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Dismiss
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function EmptyPanel({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-3xl border border-zinc-200 bg-white p-6 text-center">
      <div className="text-sm font-semibold text-zinc-950">{title}</div>
      <div className="mt-2 text-xs text-zinc-500">{description}</div>
    </div>
  );
}

function PanelLoading({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center py-16">
      <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
      <span className="ml-2 text-sm text-zinc-500">{label}</span>
    </div>
  );
}
