import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

/**
 * Clover Books - Login Page
 * Palette: white / black / grey + orange accent
 * Font: JetBrains Mono (loaded via the <style> block below)
 */

const CloverBooksLoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { auth, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [keepSignedIn, setKeepSignedIn] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const redirectPath = (location.state as { from?: string } | undefined)?.from ?? "/dashboard";

  useEffect(() => {
    if (auth.authenticated) {
      navigate(redirectPath, { replace: true });
    }
  }, [auth.authenticated, navigate, redirectPath]);

  const canSubmit = useMemo(() => {
    return email.trim().length > 2 && password.trim().length > 3;
  }, [email, password]);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canSubmit || loading) {
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      navigate(redirectPath, { replace: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Invalid credentials";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = () => {
    window.location.href = "/api/auth/google/login";
  };

  return (
    <div className="min-h-screen w-full bg-[#fbfbfc] text-neutral-900">
      {/* Font */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
        :root { --cb-orange: #f97316; }
      `}</style>

      {/* Subtle paper + grain */}
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 opacity-[0.85]"
        style={{
          backgroundImage:
            "radial-gradient(1200px 600px at 15% 10%, rgba(249,115,22,0.12), transparent 55%), radial-gradient(800px 500px at 90% 30%, rgba(0,0,0,0.06), transparent 55%), radial-gradient(700px 500px at 40% 95%, rgba(249,115,22,0.08), transparent 55%), linear-gradient(to bottom, rgba(255,255,255,0.9), rgba(250,250,252,1))",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none fixed inset-0 mix-blend-multiply opacity-[0.18]"
        style={{
          backgroundImage:
            "url('data:image/svg+xml;utf8,<?xml version=\"1.0\" encoding=\"UTF-8\"?><svg xmlns=\"http://www.w3.org/2000/svg\" width=\"260\" height=\"260\"><filter id=\"n\"><feTurbulence type=\"fractalNoise\" baseFrequency=\"0.9\" numOctaves=\"3\" stitchTiles=\"stitch\"/></filter><rect width=\"260\" height=\"260\" filter=\"url(%23n)\" opacity=\"0.35\"/></svg>')",
        }}
      />

      {/* Top bar */}
      <header className="relative z-10 mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-2xl bg-neutral-950 text-white shadow-sm">
            <span className="text-sm font-semibold" style={{ fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular" }}>
              CB
            </span>
          </div>
          <div className="leading-tight">
            <div
              className="text-sm font-semibold tracking-tight"
              style={{ fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular" }}
            >
              Clover Books
            </div>
            <div className="text-xs text-neutral-500">Calm accounting, real data.</div>
          </div>
        </div>

        <div className="hidden items-center gap-2 md:flex">
          <a
            href="#"
            className="rounded-full px-4 py-2 text-sm text-neutral-600 hover:bg-neutral-100"
          >
            Pricing
          </a>
          <a
            href="#"
            className="rounded-full px-4 py-2 text-sm text-neutral-600 hover:bg-neutral-100"
          >
            Security
          </a>
          <Link
            to="/signup"
            className="rounded-full bg-neutral-950 px-4 py-2 text-sm text-white shadow-sm hover:bg-neutral-900"
          >
            Create account
          </Link>
        </div>
      </header>

      {/* Content */}
      <main className="relative z-10 mx-auto grid w-full max-w-6xl grid-cols-1 gap-8 px-6 pb-12 pt-2 lg:grid-cols-2 lg:gap-10">
        {/* Left: Form Card */}
        <motion.section
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="rounded-[28px] border border-neutral-200/80 bg-white/70 p-6 shadow-[0_10px_30px_-18px_rgba(0,0,0,0.28)] backdrop-blur-xl sm:p-8"
        >
          <div className="flex items-start justify-between gap-6">
            <div>
              <div
                className="text-3xl font-semibold tracking-tight sm:text-4xl"
                style={{ fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular" }}
              >
                Sign in
              </div>
              <p className="mt-2 max-w-md text-sm leading-6 text-neutral-600">
                Use your email or username to unlock cash, ledgers, and banking - in one calm workspace.
              </p>
            </div>

            {/* Tiny orange orb */}
            <motion.div
              aria-hidden
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.15, duration: 0.55 }}
              className="relative mt-1 hidden h-10 w-10 sm:block"
            >
              <div className="absolute inset-0 rounded-full bg-orange-500/25 blur-md" />
              <div className="absolute inset-1 rounded-full bg-orange-500" />
              <div className="absolute inset-1 rounded-full bg-gradient-to-b from-white/30 to-transparent" />
            </motion.div>
          </div>

          {error ? (
            <div className="mt-6 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {error}
            </div>
          ) : null}

          <form onSubmit={onSubmit} className="mt-8 space-y-5">
            <Field
              label="Email or username"
              placeholder="you@studio.com"
              value={email}
              onChange={setEmail}
              autoComplete="username"
            />

            <Field
              label="Password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={setPassword}
              autoComplete="current-password"
              rightHint={
                <span className="inline-flex items-center gap-2 text-xs text-neutral-500">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  Secured
                </span>
              }
            />

            <div className="flex items-center justify-between gap-4">
              <label className="flex cursor-pointer items-center gap-2 text-sm text-neutral-600">
                <input
                  type="checkbox"
                  checked={keepSignedIn}
                  onChange={(event) => setKeepSignedIn(event.target.checked)}
                  className="h-4 w-4 rounded border-neutral-300 text-orange-500 focus:ring-orange-500"
                />
                Keep me signed in
              </label>

              <a href="#" className="text-sm text-neutral-600 hover:text-neutral-900">
                Forgot password?
              </a>
            </div>

            <motion.button
              whileHover={{ y: -1 }}
              whileTap={{ y: 0 }}
              disabled={!canSubmit || loading}
              className={
                "group relative w-full overflow-hidden rounded-2xl px-5 py-3 text-sm font-semibold shadow-sm transition focus:outline-none focus:ring-2 focus:ring-orange-500/60 focus:ring-offset-2 " +
                (canSubmit && !loading
                  ? "bg-neutral-950 text-white hover:bg-neutral-900"
                  : "cursor-not-allowed bg-neutral-200 text-neutral-500")
              }
            >
              <span className="relative z-10">{loading ? "Signing in..." : "Sign in"}</span>
              <span className="pointer-events-none absolute inset-0 opacity-0 transition group-hover:opacity-100">
                <span className="absolute -left-10 top-1/2 h-24 w-24 -translate-y-1/2 rounded-full bg-orange-500/25 blur-2xl" />
                <span className="absolute -right-10 top-1/2 h-24 w-24 -translate-y-1/2 rounded-full bg-orange-500/10 blur-2xl" />
              </span>
            </motion.button>

            <div className="relative flex items-center justify-center">
              <div className="h-px w-full bg-neutral-200" />
              <span className="absolute bg-white/80 px-3 text-xs text-neutral-500">or continue with</span>
            </div>

            <button
              type="button"
              onClick={handleGoogleLogin}
              className="flex w-full items-center justify-center gap-3 rounded-2xl border border-neutral-200 bg-white px-5 py-3 text-sm font-semibold text-neutral-800 shadow-sm hover:bg-neutral-50"
            >
              <GoogleIcon />
              Continue with Google
            </button>

            <p className="pt-2 text-center text-sm text-neutral-600">
              New to Clover Books?{" "}
              <Link to="/signup" className="font-semibold text-neutral-900 hover:underline">
                Create one
              </Link>
            </p>
          </form>

          {/* Tiny footer */}
          <div className="mt-8 rounded-2xl border border-neutral-200/70 bg-neutral-50 px-4 py-3 text-xs text-neutral-600">
            <span className="font-semibold text-neutral-900">Tip:</span> Use a calm close workflow - connect bank, review feed, reconcile, then export.
          </div>
        </motion.section>

        {/* Right: Preview / Story Card */}
        <motion.aside
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut", delay: 0.08 }}
          className="relative overflow-hidden rounded-[34px] bg-neutral-950 p-6 text-white shadow-[0_18px_50px_-26px_rgba(0,0,0,0.65)]"
        >
          {/* Ambient */}
          <div aria-hidden className="absolute inset-0">
            <div className="absolute -left-24 -top-24 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
            <div className="absolute -right-24 top-10 h-80 w-80 rounded-full bg-orange-500/10 blur-3xl" />
            <div className="absolute bottom-0 left-0 right-0 h-44 bg-gradient-to-t from-black/40 to-transparent" />
          </div>

          <div className="relative flex items-center justify-between">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/80">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              Live banking sync
            </div>
            <div className="text-xs text-white/60">Owner view</div>
          </div>

          <div className="relative mt-5 rounded-[28px] border border-white/10 bg-white/5 p-5 backdrop-blur-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="text-[11px] uppercase tracking-[0.22em] text-white/50">Today's cash position</div>
                <div
                  className="mt-2 text-4xl font-semibold tracking-tight"
                  style={{ fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular" }}
                >
                  $124,830
                </div>
              </div>
              <div className="rounded-full bg-emerald-400/15 px-3 py-1 text-xs text-emerald-200">
                +$8,420 vs last 30d
              </div>
            </div>

            <div className="mt-5 rounded-3xl border border-white/10 bg-black/25 p-4">
              <div className="flex items-center justify-between">
                <div className="text-[11px] uppercase tracking-[0.2em] text-white/45">Cashflow</div>
                <div className="text-xs text-emerald-200">Aligned</div>
              </div>

              {/* bubbles */}
              <div className="mt-4 flex items-end justify-between gap-3">
                {[
                  "h-7 w-14",
                  "h-10 w-16",
                  "h-12 w-20",
                  "h-9 w-16",
                  "h-14 w-16",
                ].map((c, idx) => (
                  <div key={idx} className={`relative ${c} rounded-full bg-white/10`}>
                    <div className="absolute inset-0 rounded-full bg-gradient-to-b from-white/10 to-transparent" />
                    <div className="absolute -inset-0.5 rounded-full bg-orange-500/0" />
                  </div>
                ))}
              </div>

              <div className="mt-4 flex items-center justify-between text-xs text-white/55">
                <span>Invoices reconciled</span>
                <span>Expenses posted</span>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <MiniStat label="Receivables" value="$38,900" pill="Live" />
              <MiniStat label="Payables" value="$26,420" pill="Live" />
            </div>
          </div>

          <div className="relative mt-5 rounded-[28px] border border-white/10 bg-white/5 p-5">
            <div className="text-[11px] uppercase tracking-[0.22em] text-white/45">Schedule</div>
            <div className="mt-4 space-y-3">
              <ScheduleRow title="Bank feed review" time="9:30 AM" />
              <ScheduleRow title="Owner update" time="11:00 AM" />
              <ScheduleRow title="Quiet close" time="4:00 PM" />
            </div>
            <p className="mt-4 text-xs leading-5 text-white/55">
              Sign in once. Clover Books keeps cash, revenue, and expenses aligned - without tab juggling or exports.
            </p>
          </div>

          {/* Orange micro-digits */}
          <DigitsOverlay />
        </motion.aside>
      </main>

      {/* Footer */}
      <footer className="relative z-10 mx-auto w-full max-w-6xl px-6 pb-10 text-xs text-neutral-500">
        <div className="flex flex-col items-center justify-between gap-3 border-t border-neutral-200/70 pt-6 sm:flex-row">
          <div>(c) {new Date().getFullYear()} Clover Books. Built for first impressions.</div>
          <div className="flex items-center gap-4">
            <a className="hover:text-neutral-800" href="#">
              Terms
            </a>
            <a className="hover:text-neutral-800" href="#">
              Privacy
            </a>
            <a className="hover:text-neutral-800" href="#">
              Status
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default CloverBooksLoginPage;

function Field({
  label,
  placeholder,
  value,
  onChange,
  type = "text",
  autoComplete,
  rightHint,
}: {
  label: string;
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  autoComplete?: string;
  rightHint?: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-3">
        <label
          className="text-sm font-semibold text-neutral-800"
          style={{ fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular" }}
        >
          {label}
        </label>
        {rightHint}
      </div>
      <div className="group relative">
        <input
          type={type}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          autoComplete={autoComplete}
          placeholder={placeholder}
          className="w-full rounded-2xl border border-neutral-200 bg-white px-4 py-3 text-sm text-neutral-900 shadow-sm outline-none transition placeholder:text-neutral-400 focus:border-orange-300 focus:ring-4 focus:ring-orange-500/15"
        />
        <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-inset ring-transparent transition group-focus-within:ring-orange-500/10" />
      </div>
    </div>
  );
}

function MiniStat({ label, value, pill }: { label: string; value: string; pill?: string }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-black/20 p-4">
      <div className="flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-[0.2em] text-white/45">{label}</div>
        {pill ? (
          <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] text-white/65">
            <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-orange-400" />
            {pill}
          </span>
        ) : null}
      </div>
      <div
        className="mt-2 text-xl font-semibold"
        style={{ fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular" }}
      >
        {value}
      </div>
    </div>
  );
}

function ScheduleRow({ title, time }: { title: string; time: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
      <div className="text-sm text-white/85">{title}</div>
      <div className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs text-white/70">{time}</div>
    </div>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden>
      <path
        fill="#FFC107"
        d="M43.611 20.083H42V20H24v8h11.303C33.659 32.653 29.223 36 24 36c-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.957 3.043l5.657-5.657C34.95 6.053 29.701 4 24 4 12.954 4 4 12.954 4 24s8.954 20 20 20 20-8.954 20-20c0-1.341-.138-2.65-.389-3.917z"
      />
      <path
        fill="#FF3D00"
        d="M6.306 14.691l6.571 4.819C14.655 16.108 18.961 13 24 13c3.059 0 5.842 1.154 7.957 3.043l5.657-5.657C34.95 6.053 29.701 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.115 0 9.877-1.957 13.409-5.147l-6.19-5.238C29.211 35.091 26.715 36 24 36c-5.201 0-9.625-3.323-11.287-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.611 20.083H42V20H24v8h11.303c-.792 2.21-2.215 4.09-4.084 5.615l.003-.002 6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
      />
    </svg>
  );
}

function DigitsOverlay() {
  // subtle numbers layer (orange) to match your brand accent
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0">
      <div
        className="absolute -right-10 top-16 rotate-6 text-[10px] leading-5 text-orange-400/25"
        style={{ fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular" }}
      >
        {Array.from({ length: 18 }).map((_, i) => (
          <div key={i}>
            {"" +
              (i % 2 === 0
                ? "1010 0110 1100 0011 0101 1001"
                : "0011 1100 0101 1010 1001 0110")}
          </div>
        ))}
      </div>

      <div
        className="absolute -left-8 bottom-10 -rotate-6 text-[10px] leading-5 text-orange-400/18"
        style={{ fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular" }}
      >
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i}>{i % 3 === 0 ? "24 08 30 12 49 26" : "38 90 26 42 12 48"}</div>
        ))}
      </div>
    </div>
  );
}
