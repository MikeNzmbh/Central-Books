import React from "react";
import { backendUrl } from "../utils/apiClient";

export interface CloverBooksLoginPageProps {
  action?: string;
  csrfToken?: string;
  nextUrl?: string;
  errors?: string[];
  googleEnabled?: boolean;
  googleLoginUrl?: string | null;
}

const ErrorStack: React.FC<{ errors?: string[] }> = ({ errors }) => {
  if (!errors || errors.length === 0) {
    return null;
  }
  return (
    <div className="space-y-1.5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
      {errors.map((message, idx) => (
        <p key={`${message}-${idx}`}>{message}</p>
      ))}
    </div>
  );
};

const InsightBar: React.FC<{ label: string; value: string; accent: string }> = ({
  label,
  value,
  accent,
}) => (
  <div className="flex items-center justify-between rounded-2xl border border-white/60 bg-white/70 px-4 py-3">
    <div>
      <p className="text-xs uppercase tracking-[0.22em] text-slate-400">{label}</p>
      <p className="mt-2 text-lg font-semibold text-slate-900">{value}</p>
    </div>
    <div
      className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-[11px] font-semibold ${accent}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      Live
    </div>
  </div>
);

const CashCard: React.FC = () => (
  <div className="space-y-5 rounded-[28px] border border-white/40 bg-gradient-to-br from-white/95 via-slate-50/95 to-sky-50/80 p-6 shadow-[0_30px_80px_rgba(15,23,42,0.08)]">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-slate-500">
          Today’s cash position
        </p>
        <p className="mt-2 text-3xl font-semibold text-slate-900">$124,830</p>
      </div>
      <div className="rounded-full bg-emerald-50 px-4 py-1 text-xs font-semibold text-emerald-700">
        +$8,420 vs last 30d
      </div>
    </div>
    <div className="rounded-3xl bg-white/80 p-4">
      <div className="flex items-baseline gap-3 text-slate-700">
        <p className="text-[11px] font-medium uppercase tracking-[0.3em] text-slate-400">
          Cashflow
        </p>
        <span className="text-sm text-emerald-600">Aligned</span>
      </div>
      <div className="mt-4 grid grid-cols-5 gap-1.5">
        <span className="h-8 rounded-full bg-sky-100" />
        <span className="h-12 rounded-full bg-sky-200" />
        <span className="h-16 rounded-full bg-sky-300" />
        <span className="h-10 rounded-full bg-sky-200" />
        <span className="h-20 rounded-full bg-sky-400" />
      </div>
      <div className="mt-5 flex items-center justify-between text-[11px] text-slate-500">
        <span>Invoices reconciled</span>
        <span>Expenses posted</span>
      </div>
    </div>
    <div className="grid grid-cols-2 gap-3">
      <InsightBar label="Receivables" value="$38,900" accent="text-amber-600" />
      <InsightBar label="Payables" value="$26,420" accent="text-sky-600" />
    </div>
  </div>
);

const CloverBooksLoginPage: React.FC<CloverBooksLoginPageProps> = ({
  action = "/login/",
  csrfToken = "",
  nextUrl,
  errors = [],
  googleEnabled = true,
  googleLoginUrl = backendUrl("/accounts/google/login/"),
}) => {
  const googleLogin = () => {
    window.location.href = googleLoginUrl || backendUrl("/accounts/google/login/?process=login");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-sky-50 px-4 py-10 text-slate-900">
      <div className="mx-auto grid max-w-6xl gap-8 lg:grid-cols-[1.1fr,0.9fr]">
        <section className="flex flex-col gap-8 rounded-[32px] border border-white/80 bg-white/90 px-8 py-10 shadow-[0_35px_80px_rgba(15,23,42,0.08)]">
          <header className="flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-base font-semibold text-white">
                CB
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.28em] text-slate-400">
                  Clover Books
                </p>
                <p className="text-sm text-slate-500">Quiet confidence for owner-led teams.</p>
              </div>
            </div>
            <div className="space-y-2">
              <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Sign in</h1>
              <p className="text-sm text-slate-500">
                Use your email or username to unlock cash, ledgers, and banking in one place.
              </p>
            </div>
          </header>
          <ErrorStack errors={errors} />
          <form method="post" action={action} className="space-y-5">
            <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
            {nextUrl && <input type="hidden" name="next" value={nextUrl} />}
            <div className="space-y-2 text-sm">
              <label className="font-medium text-slate-700" htmlFor="id_username">
                Email or username
              </label>
              <input
                id="id_username"
                name="username"
                type="text"
                autoComplete="username"
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:bg-white focus:outline-none"
                placeholder="you@studio.com"
                required
              />
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <label className="font-medium text-slate-700" htmlFor="id_password">
                  Password
                </label>
                <span className="text-xs font-medium text-slate-400">Secured</span>
              </div>
              <input
                id="id_password"
                name="password"
                type="password"
                autoComplete="current-password"
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:bg-white focus:outline-none"
                placeholder="••••••••"
                required
              />
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-600">
              <input
                type="checkbox"
                name="remember"
                className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900/30"
              />
              Keep me signed in
            </label>
            <button
              type="submit"
              className="w-full rounded-full bg-slate-900 py-3 text-sm font-semibold tracking-wide text-white shadow-[0_15px_45px_rgba(15,23,42,0.35)] transition hover:-translate-y-0.5 hover:bg-slate-800"
            >
              Sign in
            </button>

            {/* Google OAuth - only show if enabled */}
            {googleEnabled && (
              <>
                <div className="relative py-4">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-slate-200" />
                  </div>
                  <div className="relative flex justify-center text-xs">
                    <span className="bg-white px-3 text-slate-400">Or continue with</span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={googleLogin}
                  className="inline-flex w-full items-center justify-center gap-2.5 rounded-full border border-slate-200 bg-white py-3 text-sm font-medium text-slate-700 shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:bg-slate-50"
                >
                  <svg className="h-5 w-5" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                  </svg>
                  Continue with Google
                </button>
              </>
            )}

            <p className="text-center text-xs text-slate-500">
              New to Clover Books?{" "}
              <a href="/signup/" className="font-semibold text-slate-900 hover:underline">
                Create one
              </a>
            </p>
          </form>

        </section>
        <section className="hidden flex-col gap-6 rounded-[32px] border border-slate-100 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-8 text-white lg:flex">
          <div className="flex items-center justify-between text-xs text-slate-200">
            <span className="inline-flex items-center gap-1 rounded-full bg-white/10 px-3 py-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              Live banking sync
            </span>
            <span>Owner view</span>
          </div>
          <CashCard />
          <div className="rounded-[28px] border border-white/20 bg-white/10 p-6 backdrop-blur">
            <p className="text-[11px] uppercase tracking-[0.3em] text-slate-200">Schedule</p>
            <div className="mt-4 space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span>Bank feed review</span>
                <span className="rounded-full border border-white/30 px-3 py-1 text-[11px]">
                  9:30 AM
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Owner update</span>
                <span className="rounded-full border border-white/30 px-3 py-1 text-[11px]">
                  11:00 AM
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Quiet close</span>
                <span className="rounded-full border border-white/30 px-3 py-1 text-[11px]">
                  4:00 PM
                </span>
              </div>
            </div>
            <p className="mt-6 text-xs text-slate-200">
              Sign in once. Clover Books keeps cash, revenue, and expenses aligned without tab
              juggling or exports.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
};

export default CloverBooksLoginPage;
