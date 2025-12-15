import React, { useMemo, useState } from "react";
import "../index.css";

type BankAccountRow = {
  id: string;
  accountName: string;
  helperText?: string;
  bankLabel: string;
  openingBalance: string;
  currency: string;
};

const defaultCurrencyOptions = ["CAD", "USD"];

function makeId() {
  return Math.random().toString(36).slice(2);
}

function BankAccountRowForm({
  row,
  onChange,
}: {
  row: BankAccountRow;
  onChange: (patch: Partial<BankAccountRow>) => void;
}) {
  return (
    <div className="grid grid-cols-1 gap-3 rounded-2xl border border-slate-100 bg-slate-50/80 px-3.5 py-3 md:grid-cols-4 md:px-4 md:py-3">
      <div className="flex flex-col justify-center">
        <span className="text-sm font-medium text-slate-900">
          {row.accountName || "New bank account"}
        </span>
        <span className="text-xs text-slate-500">
          {row.helperText || "This will be your default operating account."}
        </span>
      </div>

      <div className="flex flex-col">
        <label className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
          Bank label
        </label>
        <input
          type="text"
          placeholder="e.g. RBC Business Chequing"
          value={row.bankLabel}
          onChange={(e) => onChange({ bankLabel: e.target.value })}
          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-900 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/5"
        />
      </div>

      <div className="flex flex-col">
        <label className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
          Opening balance
        </label>
        <input
          type="number"
          value={row.openingBalance}
          onChange={(e) => onChange({ openingBalance: e.target.value })}
          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-right text-sm text-slate-900 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/5"
        />
      </div>

      <div className="flex flex-col">
        <label className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
          Currency
        </label>
        <select
          value={row.currency}
          onChange={(e) => onChange({ currency: e.target.value })}
          className="w-full rounded-xl border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-900 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/5"
        >
          {defaultCurrencyOptions.map((option) => (
            <option key={option}>{option}</option>
          ))}
        </select>
      </div>
    </div>
  );
}

export default function BankSetupPage({ skipUrl }: { skipUrl?: string }) {
  const [rows, setRows] = useState<BankAccountRow[]>([
    {
      id: makeId(),
      accountName: "1000 · Cash (Main)",
      helperText: "This will be your default operating account.",
      bankLabel: "",
      openingBalance: "0",
      currency: "CAD",
    },
  ]);
  const [isSaving, setIsSaving] = useState(false);
  const [connectionMode, setConnectionMode] = useState<"manual" | "live">("manual");

  const firstRow = useMemo(() => rows[0], [rows]);

  function addRow() {
    setRows((prev) => [
      ...prev,
      {
        id: makeId(),
        accountName: "New bank account",
        helperText: "Additional bank or cash account.",
        bankLabel: "",
        openingBalance: "0",
        currency: firstRow?.currency || "CAD",
      },
    ]);
  }

  function updateRow(id: string, patch: Partial<BankAccountRow>) {
    setRows((prev) => prev.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  }

  async function handleSave() {
    setIsSaving(true);
    try {
      const csrfToken = document.querySelector<HTMLInputElement>(
        "[name=csrfmiddlewaretoken]"
      )?.value;

      const res = await fetch("/api/bank/setup/save/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken || "",
        },
        body: JSON.stringify({ accounts: rows }),
      });

      if (!res.ok) {
        throw new Error("Failed to save bank setup");
      }

      // Redirect to workspace or import page
      window.location.href = "/workspace/";
    } catch (err) {
      console.error(err);
      alert("Error saving bank setup. Please try again.");
    } finally {
      setIsSaving(false);
    }
  }

  // Allowlist of valid redirect destinations after skipping bank setup
  const ALLOWED_SKIP_DESTINATIONS = [
    "/workspace/",
    "/dashboard/",
    "/",
    "/invoices/",
    "/expenses/",
    "/banking/",
  ];

  async function handleSkip() {
    setIsSaving(true);
    try {
      const csrfToken = document.querySelector<HTMLInputElement>(
        "[name=csrfmiddlewaretoken]"
      )?.value;

      const res = await fetch("/api/bank/setup/skip/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken || "",
        },
      });

      if (!res.ok) {
        throw new Error("Failed to skip bank setup");
      }

      // Use allowlist validation - only redirect to known-safe paths
      const defaultUrl = "/workspace/";
      const targetUrl = ALLOWED_SKIP_DESTINATIONS.includes(skipUrl || "")
        ? skipUrl!
        : defaultUrl;
      window.location.href = targetUrl;
    } catch (err) {
      console.error(err);
      alert("Error skipping setup. Please try again.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="flex min-h-screen w-full flex-col bg-slate-50">
      <header className="sticky top-0 z-20 border-b bg-white/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4">
          <div className="space-y-1">
            <h1 className="text-xl font-semibold tracking-tight text-slate-900 md:text-2xl">
              Bank Setup
            </h1>
            <p className="max-w-xl text-sm text-slate-500">
              Configure how CERN Books talks to your bank. You can start with a simple
              manual import and add live feeds later.
            </p>
          </div>
          <div className="hidden items-center gap-3 sm:flex">
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
              Step 1 of 3 · Bank setup
            </span>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 md:gap-8 md:py-8">
          <div className="grid items-start gap-6 md:grid-cols-[minmax(0,2.2fr)_minmax(0,1.4fr)]">
            <section className="space-y-6">
              <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3.5 md:px-6 md:py-4">
                  <div>
                    <h2 className="text-sm font-semibold text-slate-900">Connection mode</h2>
                    <p className="text-xs text-slate-500">
                      Start simple with manual statement uploads. You can turn on live feeds later.
                    </p>
                  </div>
                </div>
                <div className="grid gap-4 px-4 py-4 md:px-6 md:py-5">
                  <label className={`flex cursor-pointer items-start gap-3 rounded-2xl border px-4 py-3 transition-colors ${connectionMode === 'manual' ? 'border-slate-900 bg-slate-50 ring-1 ring-slate-900' : 'border-slate-200 bg-white hover:border-slate-300'}`}>
                    <input
                      type="radio"
                      name="connectionMode"
                      checked={connectionMode === 'manual'}
                      onChange={() => setConnectionMode('manual')}
                      className="mt-1 h-4 w-4 border-slate-300 text-slate-900 focus:ring-slate-400"
                    />
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-900">Manual import only</span>
                        <span className="rounded-full bg-slate-900/90 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white">
                          Recommended
                        </span>
                      </div>
                      <p className="text-xs text-slate-500">
                        Upload monthly statements (PDF/CSV) and let CERN Books build a clean, auditable timeline
                        of your bank activity.
                      </p>
                      {connectionMode === 'manual' && (
                        <div className="mt-3 rounded-xl border border-slate-200 bg-white p-3 text-xs text-slate-600">
                          <p className="font-medium text-slate-900 mb-1">How manual import works:</p>
                          <ol className="list-decimal list-inside space-y-1 ml-1">
                            <li>Define your bank accounts below.</li>
                            <li>Click "Save bank setup".</li>
                            <li>You'll be taken to the dashboard where you can upload your first statement CSV.</li>
                          </ol>
                        </div>
                      )}
                    </div>
                  </label>

                  <label className={`flex cursor-not-allowed items-start gap-3 rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-3 opacity-60`}>
                    <input
                      type="radio"
                      name="connectionMode"
                      disabled
                      className="mt-1 h-4 w-4 border-slate-300 text-slate-900 focus:ring-slate-400"
                    />
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-900">Live bank feeds</span>
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] uppercase tracking-wide text-slate-500">
                          Coming soon
                        </span>
                      </div>
                      <p className="text-xs text-slate-500">
                        Connect to your bank provider and stream transactions automatically into your inbox.
                      </p>
                    </div>
                  </label>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3.5 md:px-6 md:py-4">
                  <div>
                    <h2 className="text-sm font-semibold text-slate-900">Bank accounts in CERN Books</h2>
                    <p className="text-xs text-slate-500">
                      Tell us which chart of accounts represent real bank or cash accounts.
                    </p>
                  </div>
                </div>

                <div className="flex flex-col gap-3 px-3.5 py-3.5 md:px-6 md:py-5">
                  <div className="hidden grid-cols-[minmax(0,1.8fr)_minmax(0,1.3fr)_minmax(0,1fr)_auto] gap-3 text-[11px] font-medium uppercase tracking-wide text-slate-400 md:grid">
                    <span>Account</span>
                    <span>Bank label (what you see on statements)</span>
                    <span className="text-right">Opening balance</span>
                    <span className="text-right">Currency</span>
                  </div>

                  {rows.map((row) => (
                    <BankAccountRowForm
                      key={row.id}
                      row={row}
                      onChange={(patch) => updateRow(row.id, patch)}
                    />
                  ))}

                  <button
                    type="button"
                    onClick={addRow}
                    className="mt-1 inline-flex items-center justify-center rounded-xl border border-dashed border-slate-300 px-3 py-2 text-xs font-medium text-slate-600 hover:border-slate-400 hover:bg-slate-50"
                  >
                    + Add another bank or cash account
                  </button>
                </div>
              </div>
            </section>

            <aside className="space-y-4 md:space-y-5">
              <div className="rounded-2xl border border-slate-200 bg-slate-900 text-slate-50 shadow-sm">
                <div className="space-y-3 px-4 py-4 md:px-5 md:py-5">
                  <h2 className="flex items-center gap-2 text-sm font-semibold">
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-800 text-[11px] font-semibold">
                      ?
                    </span>
                    How bank setup works
                  </h2>
                  <p className="text-xs text-slate-200/80">
                    CERN Books keeps your bank feed calm and auditable. Start with a single operating account,
                    import one statement, and you’re ready to reconcile.
                  </p>
                  <ul className="mt-2 space-y-1.5 text-xs text-slate-200/90">
                    <li className="flex gap-2">
                      <span className="mt-0.5 inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
                      Map at least one Cash/Bank account from your chart of accounts.
                    </li>
                    <li className="flex gap-2">
                      <span className="mt-0.5 inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
                      Set an opening balance that matches your last bank statement.
                    </li>
                    <li className="flex gap-2">
                      <span className="mt-0.5 inline-block h-1.5 w-1.5 rounded-full bg-emerald-400" />
                      Upload your first statement from the Reconciliation page to start matching.
                    </li>
                  </ul>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="space-y-3 px-4 py-4 md:px-5 md:py-5">
                  <h2 className="text-sm font-semibold text-slate-900">
                    Checklist before you go live
                  </h2>
                  <ul className="space-y-2 text-xs text-slate-600">
                    <li className="flex items-start gap-2">
                      <input
                        type="checkbox"
                        checked={rows.length > 0}
                        readOnly
                        className="mt-0.5 h-3.5 w-3.5 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                      />
                      <span>At least one bank or cash account is mapped from your chart of accounts.</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <input
                        type="checkbox"
                        checked={rows.some(r => r.openingBalance !== "0")}
                        readOnly
                        className="mt-0.5 h-3.5 w-3.5 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                      />
                      <span>Opening balance for your main operating account matches your last statement.</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <input
                        type="checkbox"
                        checked
                        readOnly
                        className="mt-0.5 h-3.5 w-3.5 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
                      />
                      <span>Your accounting year start date is configured in settings.</span>
                    </li>
                  </ul>
                </div>
              </div>

              <div className="rounded-2xl border border-transparent bg-transparent">
                <div className="flex flex-col gap-2 md:gap-3">
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={isSaving}
                    className="inline-flex items-center justify-center rounded-2xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-slate-50 shadow-sm hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/50 focus-visible:ring-offset-1 disabled:opacity-50"
                  >
                    {isSaving ? "Saving..." : "Save bank setup"}
                  </button>
                  <button
                    type="button"
                    onClick={handleSkip}
                    disabled={isSaving}
                    className="inline-flex items-center justify-center rounded-2xl border border-slate-300 bg-white px-4 py-2 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                  >
                    Skip for now · I’ll set this up later
                  </button>
                </div>
              </div>
            </aside>
          </div>
        </div>
      </main>
    </div>
  );
}
