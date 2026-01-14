import React, { useMemo } from "react";
import { Banknote, ChevronRight, FileText, Layers, ListChecks, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type SurfaceKey = "receipts" | "invoices" | "books" | "banking";

type Issue = {
  id: string;
  surface: SurfaceKey;
  title: string;
  description?: string;
  severity: "low" | "medium" | "high";
  created_at: string;
  target_url?: string;
};

interface IssuesPanelProps {
  issues: Issue[];
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

function severityChip(sev: "low" | "medium" | "high") {
  if (sev === "high") return { label: "Needs attention", cls: "bg-zinc-950 text-white" };
  if (sev === "medium") return { label: "Review recommended", cls: "bg-zinc-100 text-zinc-900 border border-zinc-200" };
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

export default function IssuesPanel({ issues, surface, loading = false }: IssuesPanelProps) {
  const surfaceKey = normalizeSurfaceKey(surface);

  const filteredIssues = useMemo(() => {
    if (!surfaceKey) return issues;
    return issues.filter((i) => i.surface === surfaceKey);
  }, [issues, surfaceKey]);

  const bySev = useMemo(() => {
    const rank = (s: Issue["severity"]) => (s === "high" ? 0 : s === "medium" ? 1 : 2);
    return [...filteredIssues].sort((a, b) => rank(a.severity) - rank(b.severity));
  }, [filteredIssues]);

  if (loading) {
    return <PanelLoading label="Loading issues..." />;
  }

  return (
    <div className="space-y-4">
      <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
        <div className="text-xs font-semibold text-zinc-700">What these mean</div>
        <div className="mt-1 text-xs text-zinc-500">
          Issues are checks that may affect accuracy. They don't change your books automatically.
        </div>
      </div>

      {!bySev.length ? (
        <EmptyPanel title="No open issues" description="Everything looks clear right now." />
      ) : (
        <div className="space-y-3">
          {bySev.map((i) => {
            const chip = severityChip(i.severity);
            const meta = surfaceMeta(i.surface);
            return (
              <div key={i.id} className="rounded-3xl border border-zinc-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className={cx("rounded-full px-3 py-1 text-[11px]", chip.cls)}>{chip.label}</span>
                      <Badge variant="outline" className="rounded-full border-zinc-200 bg-white text-zinc-700">
                        <meta.icon className="mr-1 h-3.5 w-3.5" />
                        {meta.label}
                      </Badge>
                    </div>
                    <div className="text-sm font-semibold text-zinc-950">{i.title}</div>
                    {i.description ? <div className="text-xs text-zinc-500">{i.description}</div> : null}
                  </div>
                  <div className="text-[11px] text-zinc-500">{new Date(i.created_at).toLocaleString()}</div>
                </div>

                <div className="mt-4 flex gap-2">
                  <Button
                    className="rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900"
                    onClick={() => (window.location.href = i.target_url || "#")}
                    disabled={!i.target_url}
                  >
                    Open review
                    <ChevronRight className="ml-1 h-4 w-4" />
                  </Button>
                  <Button variant="outline" className="rounded-2xl border-zinc-200 bg-white">
                    Mark as seen
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
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
