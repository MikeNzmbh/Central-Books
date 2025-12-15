import React from "react";

interface CloverBooksWelcomeOnboardingProps {
  onStartBooks?: () => void;
  onUploadSampleCsv?: () => void;
}

const CloverBooksWelcomeOnboarding: React.FC<CloverBooksWelcomeOnboardingProps> = ({
  onStartBooks,
  onUploadSampleCsv,
}) => {
  return (
    <div className="min-h-screen w-full bg-slate-50 text-slate-900 flex items-center justify-center px-4 py-10">
      <div className="max-w-6xl w-full grid gap-10 lg:grid-cols-[1.1fr,0.9fr] items-stretch">
        {/* Left: copy + actions */}
        <section className="bg-white/90 backdrop-blur rounded-3xl shadow-lg border border-slate-100 px-7 sm:px-9 py-8 sm:py-10 flex flex-col gap-8">
          {/* Badge & title */}
          <div className="space-y-4">
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              <span>Clover Books · Welcome</span>
            </div>
            <div className="space-y-3">
              <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight text-slate-900">
                Welcome to your new finance workspace.
              </h1>
              <p className="text-sm text-slate-500">
                Start by connecting a bank, importing a CSV, or exploring with sample data. Clover Books keeps your invoices, expenses, and ledger in sync so you always see a clean picture of your business.
              </p>
            </div>
          </div>

          {/* Steps */}
          <div className="grid gap-4 sm:grid-cols-3 text-sm">
            <div className="rounded-2xl border border-slate-100 bg-slate-50/60 px-4 py-3 flex flex-col gap-1.5">
              <div className="inline-flex items-center gap-2 text-xs font-medium text-sky-700">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-sky-100 text-[11px] font-semibold">
                  1
                </span>
                Basics
              </div>
              <p className="text-xs text-slate-600">
                Confirm your workspace name, choose your home currency (CAD / USD), and we’ll scaffold a clean chart of accounts and tax defaults.
              </p>
            </div>

            <div className="rounded-2xl border border-slate-100 bg-slate-50/60 px-4 py-3 flex flex-col gap-1.5">
              <div className="inline-flex items-center gap-2 text-xs font-medium text-sky-700">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-sky-100 text-[11px] font-semibold">
                  2
                </span>
                Connect money
              </div>
              <p className="text-xs text-slate-600">
                Start with a bank CSV or provider export. Our reconciliation engine helps you match movements to invoices, expenses, and ledger entries.
              </p>
            </div>

            <div className="rounded-2xl border border-slate-100 bg-slate-50/60 px-4 py-3 flex flex-col gap-1.5">
              <div className="inline-flex items-center gap-2 text-xs font-medium text-sky-700">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-sky-100 text-[11px] font-semibold">
                  3
                </span>
                Stay in control
              </div>
              <p className="text-xs text-slate-600">
                Live balances on the dashboard, clean P&amp;L and invoice status at a glance, plus gentle AI suggestions you can accept or ignore.
              </p>
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
            <button
              type="button"
              onClick={onStartBooks}
              className="inline-flex items-center justify-center rounded-full bg-slate-900 px-5 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-slate-800 active:bg-slate-900 transition"
            >
              Start your books
              <span className="ml-2 text-xs text-slate-300">2–3 minutes</span>
            </button>

            <button
              type="button"
              onClick={onUploadSampleCsv}
              className="inline-flex items-center justify-center rounded-full border border-slate-200 bg-white px-5 py-2.5 text-sm font-medium text-slate-800 hover:bg-slate-50 active:bg-slate-100 transition"
            >
              Upload a sample bank CSV
            </button>

            <p className="text-xs text-slate-500 sm:ml-auto">
              You can configure banks, tax defaults, and more from
              <span className="font-medium"> Settings → Workspace</span> any time.
            </p>
          </div>
        </section>

        {/* Right: "sketch" illustration */}
        <aside className="relative">
          <div className="relative h-full rounded-3xl border border-slate-100 bg-gradient-to-br from-sky-50 via-white to-indigo-50 shadow-sm p-6 sm:p-7 flex flex-col justify-between overflow-hidden">
            {/* Top faux app chrome */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
                <span className="h-2.5 w-2.5 rounded-full bg-slate-200" />
                <span className="h-2.5 w-2.5 rounded-full bg-slate-100" />
              </div>
              <div className="flex items-center gap-2 text-[11px] text-slate-500">
                <span>Dashboard</span>
                <span className="h-1 w-1 rounded-full bg-slate-400" />
                <span className="font-medium text-slate-700">Banking</span>
                <span className="h-1 w-1 rounded-full bg-slate-400" />
                <span>Invoices</span>
              </div>
            </div>

            {/* Main sketch card */}
            <div className="flex-1 flex flex-col gap-4">
              <div className="rounded-2xl bg-white/90 border border-slate-100 shadow-sm p-4 flex flex-col gap-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      Cash position
                    </p>
                    <p className="mt-1 text-xl font-semibold text-slate-900">
                      $24,380.12
                    </p>
                  </div>
                  <div className="flex items-center gap-1.5 text-[11px] text-emerald-600 bg-emerald-50 px-2 py-1 rounded-full">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    <span>+12.4% this month</span>
                  </div>
                </div>

                {/* Simple line chart sketch */}
                <div className="relative mt-1 h-28 rounded-xl bg-slate-50 overflow-hidden">
                  <div className="absolute inset-x-3 bottom-4 top-5 flex items-end gap-2">
                    {/* Bars / line illusion */}
                    <div className="flex-1 rounded-full bg-sky-100 h-6" />
                    <div className="flex-1 rounded-full bg-sky-200 h-10" />
                    <div className="flex-1 rounded-full bg-sky-300 h-16" />
                    <div className="flex-1 rounded-full bg-sky-200 h-9" />
                    <div className="flex-1 rounded-full bg-sky-300 h-14" />
                    <div className="flex-1 rounded-full bg-sky-400 h-20" />
                  </div>
                  <div className="absolute inset-0 bg-gradient-to-t from-white/40 to-transparent" />
                </div>
              </div>

              {/* Two smaller cards: invoice + bank match */}
              <div className="grid sm:grid-cols-2 gap-3">
                <div className="rounded-2xl bg-white/90 border border-slate-100 shadow-sm p-3 flex flex-col gap-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-slate-800">Invoice #1043</span>
                    <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700">
                      Paid
                    </span>
                  </div>
                  <p className="text-xs text-slate-500">Studio design retainer</p>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-sm font-semibold text-slate-900">
                      $1,800.00
                    </span>
                    <span className="text-[11px] text-slate-500">via TD • 2d ago</span>
                  </div>
                </div>

                <div className="rounded-2xl bg-white/90 border border-slate-100 shadow-sm p-3 flex flex-col gap-2">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-slate-800">Bank feed</span>
                    <span className="inline-flex items-center rounded-full bg-sky-50 px-2 py-0.5 text-[11px] font-medium text-sky-700">
                      3 to review
                    </span>
                  </div>
                  <ul className="mt-1 space-y-1.5 text-xs text-slate-600">
                    <li className="flex items-center justify-between">
                      <span>Stripe payout</span>
                      <span className="text-slate-900 font-medium">$642.90</span>
                    </li>
                    <li className="flex items-center justify-between">
                      <span>Google Workspace</span>
                      <span className="text-slate-900 font-medium">-$24.00</span>
                    </li>
                    <li className="flex items-center justify-between">
                      <span>Coworking</span>
                      <span className="text-slate-900 font-medium">-$190.00</span>
                    </li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Floating labels to feel "sketchy" / illustrative */}
            <div className="pointer-events-none select-none">
              <div className="absolute -left-2 top-10 hidden md:flex items-center gap-2 rounded-full border border-slate-200 bg-white/90 px-3 py-1.5 text-[11px] text-slate-700 shadow-sm">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                Cash reconciled with invoices
              </div>
              <div className="absolute -right-3 bottom-10 hidden md:flex items-center gap-2 rounded-full border border-slate-200 bg-white/90 px-3 py-1.5 text-[11px] text-slate-700 shadow-sm">
                <span className="h-1.5 w-1.5 rounded-full bg-sky-500" />
                Partial payments tracked automatically
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
};

export default CloverBooksWelcomeOnboarding;
