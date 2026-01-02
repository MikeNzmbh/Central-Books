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

type SurfaceKey = "receipts" | "invoices" | "books" | "banking";

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

interface SuggestionsPanelProps {
  proposals: Proposal[];
  onApplied: (id: string) => void;
  onDismissed: (id: string) => void;
  surface?: string | null;
  loading?: boolean;
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
  loading = false,
}: SuggestionsPanelProps) {
  const [tab, setTab] = useState<"all" | "ready" | "review" | "needs_attention">("all");
  const [q, setQ] = useState("");

  const surfaceKey = normalizeSurfaceKey(surface);

  const filtered = useMemo(() => {
    let items = proposals;
    if (surfaceKey) items = items.filter((p) => p.surface === surfaceKey);
    if (tab !== "all") items = items.filter((p) => p.risk === tab);
    if (q.trim()) {
      const s = q.trim().toLowerCase();
      items = items.filter((p) => (p.title + " " + p.description).toLowerCase().includes(s));
    }
    return items;
  }, [proposals, tab, q, surfaceKey]);

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

  const isApplyAllowed = proposal.risk !== "needs_attention";

  const apply = async () => {
    setBusy("apply");
    try {
      const csrf = await ensureCsrfToken();
      const headers: Record<string, string> = { Accept: "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;
      const res = await fetch(`/api/companion/v2/shadow-events/${proposal.id}/apply/`, {
        method: "POST",
        credentials: "same-origin",
        headers,
      });
      if (!res.ok) throw new Error("Failed to apply");
      onApplied(proposal.id);
      setConfirmOpen(false);
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
      const res = await fetch(`/api/companion/v2/shadow-events/${proposal.id}/reject/`, {
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
          <div className="text-sm font-semibold text-zinc-950">{proposal.title}</div>
          <div className="text-xs text-zinc-500">{proposal.description}</div>
        </div>
        <div className="text-[11px] text-zinc-500">{new Date(proposal.created_at).toLocaleString()}</div>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button
          className="rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900"
          onClick={() => setConfirmOpen(true)}
          disabled={!isApplyAllowed || busy === "apply"}
        >
          {busy === "apply" ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <CheckCircle2 className="mr-2 h-4 w-4" />
          )}
          Apply this change
        </Button>
        <Button
          variant="outline"
          className="rounded-2xl border-zinc-200 bg-white"
          onClick={() => setDismissOpen(true)}
          disabled={busy === "dismiss"}
        >
          Dismiss
        </Button>
        <Button
          variant="outline"
          className="rounded-2xl border-zinc-200 bg-white"
          onClick={() => (window.location.href = proposal.target_url || "#")}
          disabled={!proposal.target_url}
        >
          Review details
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
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
              <li>Make a change to your books based on this suggestion.</li>
              <li>Link it to the source item for traceability.</li>
              <li>Keep reports consistent with your policies.</li>
            </ul>
          </div>
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
              disabled={busy === "apply"}
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
