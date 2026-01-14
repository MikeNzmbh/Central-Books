import React from "react";
import { Banknote, ChevronRight, FileText, Layers, ListChecks, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";

type SurfaceKey = "receipts" | "invoices" | "books" | "banking";

type CloseReadiness = {
  status: "ready" | "not_ready";
  period_label: string;
  progress_percent: number;
  blockers: Array<{ id: string; title: string; surface?: SurfaceKey; url?: string; severity: "medium" | "high" }>;
};

type Summary = {
  close_readiness: CloseReadiness;
};

interface CloseAssistantDrawerProps {
  summary: Summary | null;
  loading?: boolean;
}

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

function severityChip(sev: "medium" | "high") {
  if (sev === "high") return { label: "Needs attention", cls: "bg-zinc-950 text-white" };
  return { label: "Review recommended", cls: "bg-zinc-100 text-zinc-900 border border-zinc-200" };
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

export default function CloseAssistantDrawer({ summary, loading = false }: CloseAssistantDrawerProps) {
  if (loading) {
    return <PanelLoading label="Loading close assistant..." />;
  }

  if (!summary?.close_readiness) {
    return (
      <div className="rounded-3xl border border-zinc-200 bg-white p-6 text-center">
        <div className="text-sm font-semibold text-zinc-950">Close assistant unavailable</div>
        <div className="mt-2 text-xs text-zinc-500">We couldn't load the close readiness data.</div>
      </div>
    );
  }

  const cr = summary.close_readiness;

  return (
    <div className="space-y-4">
      <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
        <div className="text-xs font-semibold text-zinc-700">Goal</div>
        <div className="mt-1 text-xs text-zinc-500">
          Get to \"Ready\" by resolving blockers and reviewing suggested changes.
        </div>
      </div>

      <Card className="border-zinc-200 bg-white shadow-sm">
        <CardHeader>
          <CardTitle className="text-base">{cr.period_label}</CardTitle>
          <CardDescription>{cr.status === "ready" ? "You're ready to close." : "You're almost there."}</CardDescription>
        </CardHeader>
        <CardContent className="pt-0 space-y-3">
          <div className="rounded-3xl border border-zinc-200 bg-zinc-50 p-4">
            <div className="flex items-center justify-between">
              <div className="text-xs font-semibold text-zinc-700">Progress</div>
              <div className="text-xs text-zinc-600">{cr.progress_percent}%</div>
            </div>
            <div className="mt-2">
              <Progress value={cr.progress_percent} />
            </div>
          </div>

          <div className="text-sm font-semibold">Blockers</div>
          <div className="space-y-2">
            {cr.blockers.map((b) => (
              <div key={b.id} className="rounded-3xl border border-zinc-200 bg-white p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-zinc-950">{b.title}</div>
                    <div className="mt-1 text-xs text-zinc-500">
                      {b.surface ? surfaceMeta(b.surface).label : ""}
                    </div>
                  </div>
                  <span className={cx("rounded-full px-3 py-1 text-[11px]", severityChip(b.severity).cls)}>
                    {severityChip(b.severity).label}
                  </span>
                </div>
                <div className="mt-4 flex gap-2">
                  <Button
                    className="rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900"
                    onClick={() => (window.location.href = b.url || "#")}
                    disabled={!b.url}
                  >
                    Open review
                    <ChevronRight className="ml-1 h-4 w-4" />
                  </Button>
                  <Button variant="outline" className="rounded-2xl border-zinc-200 bg-white">
                    Mark as handled
                  </Button>
                </div>
              </div>
            ))}
          </div>

          <Separator className="bg-zinc-200" />

          <div className="flex gap-2">
            <Button className="flex-1 rounded-2xl bg-zinc-950 text-white hover:bg-zinc-900">
              Finish close checklist
            </Button>
            <Button variant="outline" className="rounded-2xl border-zinc-200 bg-white">
              Export report
            </Button>
          </div>
        </CardContent>
      </Card>
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
