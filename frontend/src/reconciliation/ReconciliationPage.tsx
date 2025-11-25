import React, { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  Check,
  Filter,
  Info,
  RefreshCw,
  Search,
  Split,
} from "lucide-react";

import {
  Card,
  CardHeader,
  CardContent,
  CardFooter,
} from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Progress } from "../components/ui/progress";
import { Input } from "../components/ui/input";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "../components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "../components/ui/dialog";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "../components/ui/sheet";
import { ScrollArea } from "../components/ui/scroll-area";
import { Separator } from "../components/ui/separator";

import "../index.css";

type BankTransactionStatus =
  | "NEW"
  | "MATCHED_SINGLE"
  | "MATCHED_MULTI"
  | "PARTIAL"
  | "IGNORED";

interface BankTransaction {
  id: number;
  date: string;
  description: string;
  counterparty?: string | null;
  amount: string;
  currency: string;
  status: BankTransactionStatus;
  match_confidence?: string | null;
}

interface MatchCandidate {
  journal_entry_id: number;
  reference: string;
  description: string;
  date: string;
  amount: string;
  confidence: string;
  match_type: "ONE_TO_ONE" | "ONE_TO_MANY" | "MANY_TO_ONE";
  reason: string;
}

interface ReconciliationStats {
  total_transactions: number;
  reconciled: number;
  unreconciled: number;
  total_reconciled_amount: string;
  total_unreconciled_amount: string;
  progress_percent: number;
}

interface SplitLine {
  id: string;
  accountId: string;
  amount: string;
  description: string;
}

interface PeriodOption {
  id: string;
  label: string;
}

interface ReconciliationPageProps {
  bankAccountId: string;
}

async function fetchJson<T = any>(
  url: string,
  options?: RequestInit
): Promise<T> {
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    ...options,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }

  return res.json();
}

function formatAmount(amount: string | number, currency: string) {
  const num = Number(amount);
  if (Number.isNaN(num)) return String(amount);

  const formatter = new Intl.NumberFormat(undefined, {
    style: "currency",
    currency,
  });
  return formatter.format(num);
}

function statusBadgeVariant(
  status: BankTransactionStatus
): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "NEW":
      return "outline";
    case "MATCHED_SINGLE":
    case "MATCHED_MULTI":
      return "secondary";
    case "PARTIAL":
      return "default";
    case "IGNORED":
      return "destructive";
    default:
      return "outline";
  }
}

function makeId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}

const statusFilterOptions: (BankTransactionStatus | "ALL")[] = [
  "ALL",
  "NEW",
  "MATCHED_SINGLE",
  "MATCHED_MULTI",
  "PARTIAL",
  "IGNORED",
];

const ReconciliationPage: React.FC<ReconciliationPageProps> = ({
  bankAccountId,
}) => {
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<ReconciliationStats | null>(null);
  const [transactions, setTransactions] = useState<BankTransaction[]>([]);

  const [selectedStatusFilter, setSelectedStatusFilter] =
    useState<BankTransactionStatus | "ALL">("ALL");
  const [searchQuery, setSearchQuery] = useState("");

  const [selectedTx, setSelectedTx] = useState<BankTransaction | null>(null);
  const [matches, setMatches] = useState<MatchCandidate[]>([]);
  const [matchesOpen, setMatchesOpen] = useState(false);
  const [matchesLoading, setMatchesLoading] = useState(false);

  const [splitDialogOpen, setSplitDialogOpen] = useState(false);
  const [splitLines, setSplitLines] = useState<SplitLine[]>([]);
  const [splitError, setSplitError] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);

  const [accountName, setAccountName] = useState("Central-Books • Operating");
  const [periods, setPeriods] = useState<PeriodOption[]>([]);
  const [selectedPeriodId, setSelectedPeriodId] = useState<string | null>(null);
  const [isSoftLocked, setIsSoftLocked] = useState(false);

  useEffect(() => {
    void bootstrap();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bankAccountId]);

  async function bootstrap() {
    setLoading(true);
    setError(null);
    try {
      const now = new Date();
      const monthIdx = now.getMonth();
      const year = now.getFullYear();
      const monthNames = [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
      ];

      const currentId = `${year}-${String(monthIdx + 1).padStart(2, "0")}`;
      const prevDate = new Date(year, monthIdx - 1, 1);
      const previousId = `${prevDate.getFullYear()}-${String(
        prevDate.getMonth() + 1
      ).padStart(2, "0")}`;

      const options: PeriodOption[] = [
        {
          id: currentId,
          label: `${monthNames[monthIdx]} ${year}`,
        },
        {
          id: previousId,
          label: `${monthNames[prevDate.getMonth()]} ${prevDate.getFullYear()}`,
        },
      ];

      setPeriods(options);
      setSelectedPeriodId(currentId);

      await refreshData();
    } catch (e: any) {
      console.error(e);
      setError(e.message || "Failed to initialise reconciliation");
    } finally {
      setLoading(false);
    }
  }

  async function refreshData() {
    setLoading(true);
    setError(null);
    try {
      const [statsData, txData] = await Promise.all([
        fetchJson<ReconciliationStats>(
          `/api/bank-accounts/${bankAccountId}/reconciliation/overview/`
        ),
        fetchJson<BankTransaction[]>(
          `/api/bank-accounts/${bankAccountId}/reconciliation/transactions/?status=UNRECONCILED`
        ),
      ]);

      setStats(statsData);
      setTransactions(txData);
      setIsSoftLocked(statsData.progress_percent >= 99.5);
      if ("account_name" in (statsData as any)) {
        setAccountName(((statsData as any).account_name as string) || accountName);
      }
    } catch (e: any) {
      console.error(e);
      setError(e.message || "Failed to load reconciliation data");
    } finally {
      setLoading(false);
    }
  }

  const filteredTransactions = useMemo(() => {
    return transactions.filter((tx) => {
      if (selectedStatusFilter !== "ALL" && tx.status !== selectedStatusFilter) {
        return false;
      }
      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return (
        tx.description.toLowerCase().includes(q) ||
        (tx.counterparty || "").toLowerCase().includes(q)
      );
    });
  }, [transactions, selectedStatusFilter, searchQuery]);

  async function openMatches(tx: BankTransaction) {
    setSelectedTx(tx);
    setMatches([]);
    setMatchesLoading(true);
    setMatchesOpen(true);
    try {
      const data = await fetchJson<MatchCandidate[]>(
        `/api/reconciliation/matches/?transaction_id=${tx.id}`
      );
      setMatches(data);
    } catch (e: any) {
      console.error(e);
      setError(e.message || "Failed to load match suggestions");
    } finally {
      setMatchesLoading(false);
    }
  }

  async function handleConfirmMatch(candidate: MatchCandidate) {
    if (!selectedTx) return;
    setError(null);
    try {
      await fetchJson(`/api/reconciliation/confirm-match/`, {
        method: "POST",
        body: JSON.stringify({
          bank_transaction_id: selectedTx.id,
          journal_entry_id: candidate.journal_entry_id,
          match_confidence: candidate.confidence,
        }),
      });

      setMatchesOpen(false);
      setSelectedTx(null);
      await refreshData();
    } catch (e: any) {
      console.error(e);
      setError(e.message || "Failed to confirm match");
    }
  }

  function openSplitDialog(tx: BankTransaction) {
    setSelectedTx(tx);
    setSplitError(null);
    setSplitLines([
      {
        id: makeId(),
        accountId: "",
        amount: "",
        description: tx.description,
      },
    ]);
    setSplitDialogOpen(true);
  }

  function updateSplitLine(id: string, patch: Partial<SplitLine>) {
    setSplitLines((lines) =>
      lines.map((line) => (line.id === id ? { ...line, ...patch } : line))
    );
  }

  function addSplitLine() {
    setSplitLines((lines) => [
      ...lines,
      {
        id: makeId(),
        accountId: "",
        amount: "",
        description: "",
      },
    ]);
  }

  function removeSplitLine(id: string) {
    setSplitLines((lines) => lines.filter((line) => line.id !== id));
  }

  const splitTotal = useMemo(() => {
    return splitLines.reduce((sum, line) => {
      const v = Number(line.amount || 0);
      return sum + (Number.isNaN(v) ? 0 : v);
    }, 0);
  }, [splitLines]);

  const splitRemaining = useMemo(() => {
    if (!selectedTx) return 0;
    const txAmount = Math.abs(Number(selectedTx.amount));
    if (Number.isNaN(txAmount)) return 0;
    return txAmount - splitTotal;
  }, [selectedTx, splitTotal]);

  const splitIsBalanced =
    Math.abs(splitRemaining) < 0.005 &&
    splitLines.length > 0 &&
    splitLines.every((l) => l.accountId && l.amount);

  async function handleCreateSplit() {
    if (!selectedTx) return;
    setSplitError(null);

    if (!splitIsBalanced) {
      setSplitError("Split amounts must fully allocate the transaction amount.");
      return;
    }

    try {
      await fetchJson(`/api/reconciliation/create-split/`, {
        method: "POST",
        body: JSON.stringify({
          bank_transaction_id: selectedTx.id,
          splits: splitLines.map((l) => ({
            account_id: l.accountId,
            amount: l.amount,
            description: l.description,
          })),
        }),
      });

      setSplitDialogOpen(false);
      setSelectedTx(null);
      await refreshData();
    } catch (e: any) {
      console.error(e);
      setSplitError(e.message || "Failed to create split entry");
    }
  }

  const progress = stats?.progress_percent ?? 0;

  const timelineItems = [
    {
      label: "Period",
      value:
        periods.find((p) => p.id === selectedPeriodId)?.label ||
        "Current period",
    },
    {
      label: "Transactions",
      value: `${transactions.length} loaded`,
    },
    {
      label: "Unreconciled",
      value: `${stats?.unreconciled ?? "—"}`,
    },
    {
      label: "Soft lock",
      value: isSoftLocked ? "Locked" : "Open",
    },
  ];

  return (
    <div className="relative flex h-full min-h-screen w-full flex-col overflow-hidden bg-slate-50 text-slate-900">
      <header className="relative z-10 flex items-center justify-between px-4 pt-4 md:px-10 md:pt-6">
        <div className="inline-flex items-center gap-3 rounded-full border border-slate-200 bg-white/80 px-3 py-1.5 text-[11px] font-medium text-slate-700 shadow-sm backdrop-blur-xl">
          <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.25)]" />
          <span className="uppercase tracking-[0.18em] text-slate-400">
            Reconciliation Studio
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-500">
          <span className="hidden sm:inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white/80 px-3 py-1 shadow-sm backdrop-blur-xl">
            <span className="text-slate-400">Account</span>
            <span className="text-slate-900 font-medium">{accountName}</span>
          </span>
          <Button
            variant="outline"
            size="icon"
            onClick={() => void refreshData()}
            disabled={loading}
            className="h-8 w-8 rounded-full border-slate-200 bg-white/80 text-slate-700 shadow-sm hover:bg-slate-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </header>

      <main className="relative z-0 flex-1 px-4 pb-12 pt-4 md:px-10 md:pt-6">
        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <AlertTriangle className="h-4 w-4" />
            <span>{error}</span>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
          <Card className="border-slate-200 shadow-sm">
            <CardHeader className="flex flex-col gap-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    Progress
                  </p>
                  <h1 className="text-xl font-semibold text-slate-900">
                    {stats?.total_transactions ?? "—"} transactions this period
                  </h1>
                </div>
                {isSoftLocked && (
                  <Badge
                    variant="secondary"
                    className="border border-slate-200 bg-white text-xs text-slate-700"
                  >
                    Soft locked
                  </Badge>
                )}
              </div>
              <div className="flex flex-col gap-2 rounded-xl border border-slate-200 bg-white/80 p-4 shadow-sm">
                <div className="flex items-center justify-between text-xs text-slate-500">
                  <span>Reconciled</span>
                  <span className="font-semibold text-slate-900">
                    {progress.toFixed(0)}%
                  </span>
                </div>
                <Progress value={progress} className="h-3" />
                <div className="flex flex-wrap gap-4 text-[11px] text-slate-500">
                  <span>
                    Reconciled:{" "}
                    <strong className="text-slate-900">
                      {stats?.reconciled ?? "—"}
                    </strong>
                  </span>
                  <span>
                    Unreconciled:{" "}
                    <strong className="text-slate-900">
                      {stats?.unreconciled ?? "—"}
                    </strong>
                  </span>
                  <span>
                    Allocated:{" "}
                    <strong className="text-slate-900">
                      {formatAmount(
                        stats?.total_reconciled_amount ?? "0",
                        "USD"
                      )}
                    </strong>
                  </span>
                </div>
              </div>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-slate-200 bg-white/70 p-4">
                <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                  Period
                </p>
                <Select
                  value={selectedPeriodId ?? undefined}
                  onValueChange={(val: string) => setSelectedPeriodId(val)}
                >
                  <SelectTrigger className="mt-2 w-full text-sm">
                    <SelectValue
                      placeholder={
                        periods.find((p) => p.id === selectedPeriodId)?.label ??
                        "Current period"
                      }
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {periods.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="mt-2 text-xs text-slate-500">
                  Locked once reconciliation hits 100%.
                </p>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white/70 p-4">
                <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                  Session
                </p>
                <div className="mt-2 space-y-1 text-sm">
                  <div className="flex items-center gap-2 text-slate-600">
                    <Info className="h-4 w-4 text-emerald-500" />
                    Live suggestions enabled
                  </div>
                  <div className="flex items-center gap-2 text-slate-600">
                    <Check className="h-4 w-4 text-slate-500" />
                    Auto-save in workspace
                  </div>
                </div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white/70 p-4">
                <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                  Totals
                </p>
                <div className="mt-2 space-y-1 text-sm text-slate-600">
                  <div className="flex items-center justify-between">
                    <span>Cleared</span>
                    <span className="font-semibold text-slate-900">
                      {formatAmount(
                        stats?.total_reconciled_amount ?? "0",
                        "USD"
                      )}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Unreconciled</span>
                    <span className="font-semibold text-slate-900">
                      {formatAmount(
                        stats?.total_unreconciled_amount ?? "0",
                        "USD"
                      )}
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    Session context
                  </p>
                  <h3 className="text-lg font-semibold text-slate-900">
                    This workspace
                  </h3>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-slate-600">
              <div className="rounded-lg border border-slate-200 bg-white/80 p-3">
                <div className="flex items-center gap-2 text-[13px] font-semibold text-slate-900">
                  <Info className="h-4 w-4 text-slate-500" />
                  Live reconciliation
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  Matches appear instantly as the engine processes new
                  transactions.
                </p>
              </div>
              <div className="space-y-3 rounded-lg border border-slate-200 bg-white/80 p-3">
                <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                  Timeline
                </p>
                <div className="space-y-2">
                  {timelineItems.map((item) => (
                    <div
                      key={item.label}
                      className="flex items-center justify-between rounded-md border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-600"
                    >
                      <span className="font-medium text-slate-900">
                        {item.label}
                      </span>
                      <span>{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white/80 p-3 text-xs text-slate-500">
                Audit-ready. Every match and split is stored in the ledger
                history.
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="mt-6 grid gap-4 xl:grid-cols-[2fr_1fr]">
          <Card className="border-slate-200 shadow-sm">
            <CardHeader className="flex flex-col gap-3">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    Feed
                  </p>
                  <h3 className="text-lg font-semibold text-slate-900">
                    Transactions ready to reconcile
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <Select
                    value={selectedStatusFilter}
                    onValueChange={(val: string) =>
                      setSelectedStatusFilter(
                        val as BankTransactionStatus | "ALL"
                      )
                    }
                  >
                    <SelectTrigger className="w-[160px] border-slate-200 text-sm">
                      <SelectValue placeholder="All statuses" />
                    </SelectTrigger>
                    <SelectContent>
                      {statusFilterOptions.map((opt) => (
                        <SelectItem key={opt} value={opt}>
                          {opt === "ALL" ? "All statuses" : opt.replaceAll("_", " ")}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Button variant="outline" size="icon" className="h-9 w-9">
                    <Filter className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                <Input
                  placeholder="Search description or counterparty"
                  value={searchQuery}
                  onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                    setSearchQuery(e.target.value)
                  }
                  className="pl-10"
                />
              </div>
            </CardHeader>
            <CardContent className="pt-0">
              <ScrollArea className="max-h-[70vh] pr-3">
                <div className="space-y-3">
                  <AnimatePresence>
                    {filteredTransactions.map((tx) => (
                      <TransactionCard
                        key={tx.id}
                        tx={tx}
                        onOpenMatches={() => void openMatches(tx)}
                        onOpenSplit={() => openSplitDialog(tx)}
                        isSoftLocked={isSoftLocked}
                      />
                    ))}
                  </AnimatePresence>
                  {filteredTransactions.length === 0 && (
                    <div className="flex h-40 flex-col items-center justify-center rounded-lg border border-dashed border-slate-200 bg-white/70 text-sm text-slate-500">
                      <Check className="mb-2 h-5 w-5 text-emerald-500" />
                      Everything reconciled for this filter.
                    </div>
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          <Card className="border-slate-200 shadow-sm">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    Session health
                  </p>
                  <h3 className="text-lg font-semibold text-slate-900">
                    Engine insights
                  </h3>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-slate-600">
              <div className="rounded-lg border border-slate-200 bg-white/80 p-3">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="bg-emerald-50 text-emerald-700">
                    {transactions.length > 0
                      ? `${transactions.length} awaiting`
                      : "Idle"}
                  </Badge>
                  <span className="text-xs text-slate-500">
                    Engine watching for new matches
                  </span>
                </div>
              </div>
              <div className="rounded-lg border border-slate-200 bg-white/80 p-3 text-xs text-slate-500">
                Keep this tab open while you reconcile. Matches and splits save
                automatically.
              </div>
            </CardContent>
            <CardFooter className="text-[11px] text-slate-500">
              Need to change bank account? Use the account switcher in the
              workspace header.
            </CardFooter>
          </Card>
        </div>
      </main>

      <Sheet
        open={matchesOpen}
        onOpenChange={(open: boolean) => {
          setMatchesOpen(open);
          if (!open) {
            setSelectedTx(null);
          }
        }}
      >
        <SheetContent className="w-full max-w-xl border-slate-200">
          <SheetHeader className="space-y-2">
            <SheetTitle>Match suggestions</SheetTitle>
            <SheetDescription>
              {selectedTx ? (
                <div className="space-y-1 text-sm text-slate-600">
                  <p className="font-semibold text-slate-900">
                    {selectedTx.description}
                  </p>
                  <p className="text-xs text-slate-500">
                    {formatAmount(selectedTx.amount, selectedTx.currency)} •{" "}
                    {new Date(selectedTx.date).toLocaleDateString()}
                  </p>
                </div>
              ) : (
                "Choose a transaction to view matches."
              )}
            </SheetDescription>
          </SheetHeader>
          <Separator className="my-4" />
          <div className="space-y-3">
            {matchesLoading && (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">
                Loading matches…
              </div>
            )}
            {!matchesLoading && matches.length === 0 && (
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-500">
                No matches yet. Try refreshing or adjust filters.
              </div>
            )}
            {matches.map((match) => (
              <div
                key={match.journal_entry_id}
                className="rounded-lg border border-slate-200 bg-white/80 p-3 shadow-sm"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">
                      {match.reference}
                    </p>
                    <p className="text-xs text-slate-500">{match.description}</p>
                    <p className="text-xs text-slate-500">
                      {new Date(match.date).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="text-right text-sm font-semibold text-slate-900">
                    {formatAmount(match.amount, selectedTx?.currency ?? "USD")}
                  </div>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                  <span>{match.reason}</span>
                  <Badge variant="secondary">
                    {Math.round(Number(match.confidence) * 100)}% confidence
                  </Badge>
                </div>
                <div className="mt-3 flex justify-end">
                  <Button
                    onClick={() => void handleConfirmMatch(match)}
                    size="sm"
                    disabled={loading}
                  >
                    Confirm match
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </SheetContent>
      </Sheet>

      <Dialog
        open={splitDialogOpen}
        onOpenChange={(open: boolean) => {
          setSplitDialogOpen(open);
          if (!open) {
            setSelectedTx(null);
          }
        }}
      >
        <DialogContent className="max-w-3xl border-slate-200">
          <DialogHeader>
            <DialogTitle>Split & categorize</DialogTitle>
            <DialogDescription>
              Allocate the transaction across multiple accounts.
            </DialogDescription>
          </DialogHeader>
          {selectedTx && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold text-slate-900">
                    {selectedTx.description}
                  </p>
                  <p className="text-xs text-slate-500">
                    {selectedTx.counterparty || "Counterparty unavailable"}
                  </p>
                </div>
                <div className="text-right font-semibold text-slate-900">
                  {formatAmount(selectedTx.amount, selectedTx.currency)}
                </div>
              </div>
            </div>
          )}

          <div className="space-y-3">
            {splitLines.map((line) => (
              <div
                key={line.id}
                className="grid grid-cols-12 gap-2 rounded-lg border border-slate-200 bg-white/80 p-3"
              >
                <div className="col-span-5">
                  <Input
                    placeholder="Account ID"
                    value={line.accountId}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      updateSplitLine(line.id, { accountId: e.target.value })
                    }
                  />
                </div>
                <div className="col-span-3">
                  <Input
                    placeholder="Amount"
                    value={line.amount}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      updateSplitLine(line.id, { amount: e.target.value })
                    }
                  />
                </div>
                <div className="col-span-3">
                  <Input
                    placeholder="Description"
                    value={line.description}
                    onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                      updateSplitLine(line.id, { description: e.target.value })
                    }
                  />
                </div>
                <div className="col-span-1 flex justify-end">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removeSplitLine(line.id)}
                    className="h-9 w-9"
                    aria-label="Remove split line"
                  >
                    <Split className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={addSplitLine}>
                  Add line
                </Button>
                <span className="text-xs text-slate-500">
                  Each split needs an account and amount.
                </span>
              </div>
              <div className="text-right text-sm text-slate-600">
                <p>
                  Split total:{" "}
                  <span className="font-semibold text-slate-900">
                    {formatAmount(splitTotal, selectedTx?.currency || "USD")}
                  </span>
                </p>
                <p
                  className={
                    Math.abs(splitRemaining) < 0.01
                      ? "text-emerald-600"
                      : "text-amber-600"
                  }
                >
                  Remaining:{" "}
                  {formatAmount(splitRemaining, selectedTx?.currency || "USD")}
                </p>
              </div>
            </div>
            {splitError && (
              <div className="flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                <AlertTriangle className="h-4 w-4" />
                <span>{splitError}</span>
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Button
                onClick={() => void handleCreateSplit()}
                disabled={!splitIsBalanced || loading}
              >
                Create split
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const TransactionCard: React.FC<{
  tx: BankTransaction;
  onOpenMatches: () => void;
  onOpenSplit: () => void;
  isSoftLocked: boolean;
}> = ({ tx, onOpenMatches, onOpenSplit, isSoftLocked }) => {
  const confidence = tx.match_confidence
    ? Math.round(Number(tx.match_confidence) * 100)
    : null;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.16 }}
      className="rounded-xl border border-slate-200 bg-white/80 p-4 shadow-[0_8px_30px_rgba(15,23,42,0.04)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <Badge variant={statusBadgeVariant(tx.status)}>
              {tx.status.replaceAll("_", " ")}
            </Badge>
            {confidence !== null && (
              <div className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-1 text-[11px] font-semibold text-emerald-700">
                <Check className="h-3 w-3" />
                {confidence}% match
              </div>
            )}
          </div>
          <p className="text-sm font-semibold text-slate-900">
            {tx.description}
          </p>
          <p className="text-xs text-slate-500">
            {tx.counterparty || "Counterparty unavailable"}
          </p>
          <p className="text-[11px] text-slate-400">
            {new Date(tx.date).toLocaleDateString()}
          </p>
        </div>
        <div className="text-right">
          <div className="text-lg font-semibold">
            {formatAmount(tx.amount, tx.currency)}
          </div>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs text-slate-500">
          Calm, Apple-style UI — actions keep you in flow.
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onOpenMatches}
            disabled={isSoftLocked}
          >
            View matches
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={onOpenSplit}
            disabled={isSoftLocked}
          >
            Split & categorize
          </Button>
        </div>
      </div>
    </motion.div>
  );
};

export default ReconciliationPage;
