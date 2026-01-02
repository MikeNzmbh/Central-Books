import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

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

const CloverBooksLoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { auth, login } = useAuth();
  const [email, setEmail] = useState("demo@cloverbooks.local");
  const [password, setPassword] = useState("changeme");
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const redirectPath = (location.state as { from?: string } | undefined)?.from ?? "/dashboard";

  useEffect(() => {
    if (auth.authenticated) {
      navigate(redirectPath, { replace: true });
    }
  }, [auth.authenticated, navigate, redirectPath]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setErrors([]);
    setLoading(true);
    try {
      await login(email, password);
      navigate(redirectPath, { replace: true });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Invalid credentials";
      setErrors([message]);
    } finally {
      setLoading(false);
    }
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
                Use your email and password to unlock cash, ledgers, and banking in one place.
              </p>
            </div>
          </header>

          <ErrorStack errors={errors} />

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2 text-sm">
              <label className="font-medium text-slate-700" htmlFor="login_email">
                Email
              </label>
              <input
                id="login_email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:bg-white focus:outline-none"
                placeholder="you@studio.com"
                required
              />
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <label className="font-medium text-slate-700" htmlFor="login_password">
                  Password
                </label>
                <span className="text-xs font-medium text-slate-400">Secured</span>
              </div>
              <input
                id="login_password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-slate-900 placeholder:text-slate-400 focus:border-slate-400 focus:bg-white focus:outline-none"
                placeholder="••••••••"
                required
              />
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-600">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900/30"
              />
              Keep me signed in
            </label>
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-full bg-slate-900 py-3 text-sm font-semibold tracking-wide text-white shadow-[0_15px_45px_rgba(15,23,42,0.35)] transition hover:-translate-y-0.5 hover:bg-slate-800 disabled:opacity-60"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>

            <p className="text-center text-xs text-slate-500">
              Demo credentials are prefilled from the backend seed user.
            </p>
          </form>
        </section>

        <aside className="space-y-6">
          <div className="rounded-[28px] border border-white/60 bg-white/80 p-6 shadow-[0_30px_80px_rgba(15,23,42,0.08)]">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-400">Control tower snapshot</p>
            <p className="mt-3 text-xl font-semibold text-slate-900">AI companion ready</p>
            <p className="mt-2 text-sm text-slate-500">
              Your ledgers, banking feeds, and companion insights are synced to the latest refresh window.
            </p>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <InsightBar label="Receipts" value="92%" accent="text-emerald-600" />
              <InsightBar label="Banking" value="88%" accent="text-sky-600" />
            </div>
          </div>
          <CashCard />
        </aside>
      </div>
    </div>
  );
};

export default CloverBooksLoginPage;
