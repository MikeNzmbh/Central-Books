import React from "react";
import "../index.css";

const to = (href: string) => () => {
  window.location.href = href;
};

export default function BusinessSkipLandingPage() {
  return (
    <div className="min-h-screen w-full bg-slate-50 flex flex-col">
      <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-20">
        <div className="mx-auto max-w-6xl px-4 py-4 flex items-center justify-between gap-4">
          <div className="space-y-1">
            <h1 className="text-xl md:text-2xl font-semibold tracking-tight text-slate-900">
              Workspace home
            </h1>
            <p className="text-sm text-slate-500 max-w-xl">
              You can start exploring CERN Books now. We’ll keep your unfinished setup in the background until you’re ready.
            </p>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <div className="mx-auto max-w-6xl px-4 py-6 md:py-8 flex flex-col gap-6 md:gap-8">
          <section className="grid gap-4 md:grid-cols-[minmax(0,2.1fr)_minmax(0,1.4fr)] items-start">
            <div className="space-y-4 md:space-y-5">
              <div className="rounded-2xl border border-amber-200 bg-amber-50/80 px-4 py-3.5 md:px-5 md:py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                <div className="space-y-1">
                  <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Setup pending</p>
                  <p className="text-sm text-amber-900">
                    Business details and bank setup are not finished yet. You can still create invoices and expenses, but reports may be incomplete.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={to("/business/setup/?force=true")}
                  className="inline-flex items-center justify-center rounded-xl bg-slate-900 px-4 py-2 text-xs font-medium text-slate-50 shadow-sm hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/50 focus-visible:ring-offset-1"
                >
                  Finish business setup
                </button>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white shadow-sm px-4 py-4 md:px-6 md:py-5 space-y-4">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <h2 className="text-sm font-semibold text-slate-900">Today’s picture</h2>
                    <p className="text-xs text-slate-500">A simple overview of where you are right now.</p>
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <div className="rounded-2xl border border-slate-100 bg-slate-50/80 px-3.5 py-3 flex flex-col gap-1.5">
                    <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">Unreconciled items</p>
                    <p className="text-xl font-semibold text-slate-900">0</p>
                    <p className="text-xs text-slate-500">
                      Bank setup is not finished yet, so we’ll start counting once statements arrive.
                    </p>
                  </div>
                  <div className="rounded-2xl border border-slate-100 bg-slate-50/80 px-3.5 py-3 flex flex-col gap-1.5">
                    <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">Open invoices</p>
                    <p className="text-xl font-semibold text-slate-900">0</p>
                    <p className="text-xs text-slate-500">Create your first invoice to see who owes you money.</p>
                  </div>
                  <div className="rounded-2xl border border-slate-100 bg-slate-50/80 px-3.5 py-3 flex flex-col gap-1.5">
                    <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">This month’s expenses</p>
                    <p className="text-xl font-semibold text-slate-900">0.00</p>
                    <p className="text-xs text-slate-500">Log a few expenses to get a feel for the workflow.</p>
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white shadow-sm px-4 py-4 md:px-6 md:py-5 space-y-3">
                <h2 className="text-sm font-semibold text-slate-900">Quick start</h2>
                <div className="grid gap-3 md:grid-cols-2">
                  <button
                    type="button"
                    onClick={to("/invoices/new/")}
                    className="flex flex-col items-start gap-1 rounded-2xl border border-slate-200 bg-slate-50/80 px-3.5 py-3 text-left hover:border-slate-300 hover:bg-slate-50"
                  >
                    <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Step 1</span>
                    <span className="text-sm font-semibold text-slate-900">Create your first customer invoice</span>
                    <span className="text-xs text-slate-500">
                      Test the sales flow end to end with a small example invoice.
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={to("/expenses/new/")}
                    className="flex flex-col items-start gap-1 rounded-2xl border border-slate-200 bg-slate-50/80 px-3.5 py-3 text-left hover:border-slate-300 hover:bg-slate-50"
                  >
                    <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Step 2</span>
                    <span className="text-sm font-semibold text-slate-900">Record a simple expense</span>
                    <span className="text-xs text-slate-500">
                      Capture one or two everyday expenses to see how categorisation feels.
                    </span>
                  </button>
                  <button
                    type="button"
                    onClick={to("/reports/cashflow/")}
                    className="flex flex-col items-start gap-1 rounded-2xl border border-slate-200 bg-slate-50/80 px-3.5 py-3 text-left hover:border-slate-300 hover:bg-slate-50"
                  >
                    <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Step 3</span>
                    <span className="text-sm font-semibold text-slate-900">Explore reports (preview)</span>
                    <span className="text-xs text-slate-500">See how your data will show up in simple, calm reports.</span>
                  </button>
                  <button
                    type="button"
                    onClick={to("/business/setup/?force=true")}
                    className="flex flex-col items-start gap-1 rounded-2xl border border-slate-200 bg-slate-50/80 px-3.5 py-3 text-left hover:border-slate-300 hover:bg-slate-50"
                  >
                    <span className="text-xs font-medium uppercase tracking-wide text-slate-500">Any time</span>
                    <span className="text-sm font-semibold text-slate-900">Return to setup</span>
                    <span className="text-xs text-slate-500">
                      Jump back into business and bank setup when you’re ready.
                    </span>
                  </button>
                </div>
              </div>
            </div>

            <aside className="space-y-4 md:space-y-5">
              <div className="rounded-2xl border border-slate-200 bg-white shadow-sm px-4 py-4 md:px-5 md:py-5 space-y-3">
                <h2 className="text-sm font-semibold text-slate-900">What’s waiting in setup</h2>
                <ul className="space-y-2 text-xs text-slate-600">
                  <li className="flex items-start gap-2">
                    <span className="mt-1 inline-block h-1.5 w-1.5 rounded-full bg-amber-500" />
                    <span>Business profile: legal name, address, tax numbers, logo.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-1 inline-block h-1.5 w-1.5 rounded-full bg-amber-500" />
                    <span>Bank mapping: choose which accounts are real bank or cash accounts.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="mt-1 inline-block h-1.5 w-1.5 rounded-full bg-amber-500" />
                    <span>Tax settings: confirm default sales tax for your invoices.</span>
                  </li>
                </ul>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-slate-900 text-slate-50 shadow-sm px-4 py-4 md:px-5 md:py-5 space-y-3">
                <h2 className="text-sm font-semibold">Calm accounting, even half set up</h2>
                <p className="text-xs text-slate-200/85">
                  It’s okay to try things before everything is perfect. CERN Books keeps drafts and test data separate
                  so you can learn the flows without breaking your real books.
                </p>
                <button
                  type="button"
                  onClick={to("/settings/account/")}
                  className="inline-flex items-center justify-center rounded-xl bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-900 hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-50/60 focus-visible:ring-offset-1"
                >
                  View how drafts are handled
                </button>
              </div>
            </aside>
          </section>
        </div>
      </main>
    </div>
  );
}
