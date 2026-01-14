import React, { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { backendUrl } from "../utils/apiClient";

/**
 * Clover Books - Create Account Page
 * Matches the Login UI: white / black / grey + orange accent, JetBrains Mono
 */

interface CloverBooksCreateAccountProps {
  action?: string;
  csrfToken?: string;
  errors?: string[];
  initialEmail?: string;
  initialBusinessName?: string;
}

const CloverBooksCreateAccount: React.FC<CloverBooksCreateAccountProps> = ({
  action = "/signup/",
  csrfToken,
  errors = [],
  initialEmail = "",
  initialBusinessName = "",
}) => {
  const [fullName, setFullName] = useState("");
  const [company, setCompany] = useState(initialBusinessName);
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [agree, setAgree] = useState(true);

  const passwordOk = useMemo(() => {
    const longEnough = password.trim().length >= 8;
    const match = password === confirmPassword && confirmPassword.length > 0;
    return { longEnough, match };
  }, [password, confirmPassword]);

  const canSubmit = useMemo(() => {
    const hasBasics =
      fullName.trim().length >= 2 &&
      email.trim().length >= 4 &&
      password.trim().length >= 8 &&
      password === confirmPassword;
    return hasBasics && agree;
  }, [fullName, email, password, confirmPassword, agree]);

  const handleSubmit = (event: React.FormEvent) => {
    if (!canSubmit) {
      event.preventDefault();
    }
  };

  const googleSignup = () => {
    window.location.href = backendUrl("/accounts/google/login/?process=signup");
  };

  return (
    <div className="min-h-screen w-full bg-[#fbfbfc] text-neutral-900">
      {/* Font */}
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');
        :root { --cb-orange: #f97316; }
      `}</style>

      {/* Paper + grain */}
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
          <a href="#" className="rounded-full px-4 py-2 text-sm text-neutral-600 hover:bg-neutral-100">
            Pricing
          </a>
          <a href="#" className="rounded-full px-4 py-2 text-sm text-neutral-600 hover:bg-neutral-100">
            Security
          </a>
          <Link
            to="/login"
            className="rounded-full border border-neutral-200 bg-white px-4 py-2 text-sm text-neutral-900 shadow-sm hover:bg-neutral-50"
          >
            Sign in
          </Link>
        </div>
      </header>

      <main className="relative z-10 mx-auto grid w-full max-w-6xl grid-cols-1 gap-8 px-6 pb-12 pt-2 lg:grid-cols-2 lg:gap-10">
        {/* Left: Create card */}
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
                Create account
              </div>
              <p className="mt-2 max-w-md text-sm leading-6 text-neutral-600">
                Start clean. Connect bank feeds, capture receipts, and close books faster - with audit-ready history.
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

          {errors.length > 0 ? (
            <div className="mt-6 space-y-1.5 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {errors.map((message, idx) => (
                <p key={`${message}-${idx}`}>{message}</p>
              ))}
            </div>
          ) : null}

          <form onSubmit={handleSubmit} method="post" action={action} className="mt-8 space-y-5">
            {csrfToken ? <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} /> : null}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field
                label="Full name"
                placeholder="Vorg Eavy"
                value={fullName}
                onChange={setFullName}
                autoComplete="name"
                name="full_name"
                required
              />
              <Field
                label="Company (optional)"
                placeholder="Clover Studio"
                value={company}
                onChange={setCompany}
                autoComplete="organization"
                name="business_name"
              />
            </div>

            <Field
              label="Work email"
              placeholder="you@studio.com"
              value={email}
              onChange={setEmail}
              autoComplete="email"
              name="email"
              required
            />

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field
                label="Password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={setPassword}
                autoComplete="new-password"
                rightHint={<StrengthPill ok={passwordOk.longEnough} label="8+ chars" />}
                name="password1"
                required
              />
              <Field
                label="Confirm"
                type="password"
                placeholder="••••••••"
                value={confirmPassword}
                onChange={setConfirmPassword}
                autoComplete="new-password"
                rightHint={<StrengthPill ok={passwordOk.match} label="Match" />}
                name="password2"
                required
              />
            </div>

            <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-neutral-200 bg-white px-4 py-3 text-sm text-neutral-700 shadow-sm">
              <input
                type="checkbox"
                name="accept_tos"
                checked={agree}
                required
                onChange={(event) => setAgree(event.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-neutral-300 text-orange-500 focus:ring-orange-500"
              />
              <span>
                I agree to the{" "}
                <a className="font-semibold text-neutral-900 hover:underline" href="#">Terms</a> and{" "}
                <a className="font-semibold text-neutral-900 hover:underline" href="#">Privacy Policy</a>.
                <span className="block text-xs text-neutral-500">You can cancel anytime. No surprise charges.</span>
              </span>
            </label>

            <motion.button
              whileHover={{ y: -1 }}
              whileTap={{ y: 0 }}
              disabled={!canSubmit}
              className={
                "group relative w-full overflow-hidden rounded-2xl px-5 py-3 text-sm font-semibold shadow-sm transition focus:outline-none focus:ring-2 focus:ring-orange-500/60 focus:ring-offset-2 " +
                (canSubmit
                  ? "bg-neutral-950 text-white hover:bg-neutral-900"
                  : "cursor-not-allowed bg-neutral-200 text-neutral-500")
              }
            >
              <span className="relative z-10">Create account</span>
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
              onClick={googleSignup}
              className="flex w-full items-center justify-center gap-3 rounded-2xl border border-neutral-200 bg-white px-5 py-3 text-sm font-semibold text-neutral-800 shadow-sm hover:bg-neutral-50"
            >
              <GoogleIcon />
              Continue with Google
            </button>

            <p className="pt-2 text-center text-sm text-neutral-600">
              Already have an account?{" "}
              <Link to="/login" className="font-semibold text-neutral-900 hover:underline">
                Sign in
              </Link>
            </p>
          </form>

          <div className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <MiniBadge title="Audit-ready" desc="Changes logged" />
            <MiniBadge title="Bank sync" desc="Live feeds" />
            <MiniBadge title="Receipt capture" desc="OCR + rules" />
          </div>
        </motion.section>

        {/* Right: Onboarding / promise */}
        <motion.aside
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.55, ease: "easeOut", delay: 0.08 }}
          className="relative overflow-hidden rounded-[34px] bg-neutral-950 p-6 text-white shadow-[0_18px_50px_-26px_rgba(0,0,0,0.65)]"
        >
          <div aria-hidden className="absolute inset-0">
            <div className="absolute -left-24 -top-24 h-72 w-72 rounded-full bg-white/10 blur-3xl" />
            <div className="absolute -right-24 top-10 h-80 w-80 rounded-full bg-orange-500/10 blur-3xl" />
            <div className="absolute bottom-0 left-0 right-0 h-44 bg-gradient-to-t from-black/40 to-transparent" />
          </div>

          <div className="relative flex items-center justify-between">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/80">
              <span className="h-1.5 w-1.5 rounded-full bg-orange-400" />
              Setup in ~10 minutes
            </div>
            <div className="text-xs text-white/60">New workspace</div>
          </div>

          <div className="relative mt-5 rounded-[28px] border border-white/10 bg-white/5 p-5 backdrop-blur-xl">
            <div className="text-[11px] uppercase tracking-[0.22em] text-white/50">Your first close</div>
            <div
              className="mt-2 text-3xl font-semibold tracking-tight"
              style={{ fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular" }}
            >
              Calm. Fast. Proven.
            </div>
            <p className="mt-3 text-sm leading-6 text-white/70">
              Clover Books is built to keep your cash, receipts, and reconciliation aligned - with a paper trail you can trust.
            </p>

            <div className="mt-5 space-y-3">
              <StepRow idx={1} title="Connect bank" desc="Start live feed sync (read-only)" />
              <StepRow idx={2} title="Review & match" desc="Categorize with AI + rules" />
              <StepRow idx={3} title="Reconcile" desc="One-click close for the period" />
              <StepRow idx={4} title="Export" desc="Reports ready for tax time" />
            </div>
          </div>

          <div className="relative mt-5 grid grid-cols-2 gap-3">
            <GlassStat label="SOC2-ready" value="Security" />
            <GlassStat label="256-bit" value="Encryption" />
          </div>

          <div className="relative mt-5 rounded-[28px] border border-white/10 bg-white/5 p-5">
            <div className="text-[11px] uppercase tracking-[0.22em] text-white/45">What you get</div>
            <ul className="mt-4 space-y-3 text-sm text-white/75">
              <li className="flex items-start gap-3">
                <Check /> Real-time cash position and clean visibility
              </li>
              <li className="flex items-start gap-3">
                <Check /> Audit-ready receipts and change history
              </li>
              <li className="flex items-start gap-3">
                <Check /> Team collaboration when you are ready
              </li>
            </ul>
          </div>

          <DigitsOverlay />
        </motion.aside>
      </main>

      <footer className="relative z-10 mx-auto w-full max-w-6xl px-6 pb-10 text-xs text-neutral-500">
        <div className="flex flex-col items-center justify-between gap-3 border-t border-neutral-200/70 pt-6 sm:flex-row">
          <div>(c) {new Date().getFullYear()} Clover Books. Built for first impressions.</div>
          <div className="flex items-center gap-4">
            <a className="hover:text-neutral-800" href="#">Terms</a>
            <a className="hover:text-neutral-800" href="#">Privacy</a>
            <a className="hover:text-neutral-800" href="#">Status</a>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default CloverBooksCreateAccount;

function Field({
  label,
  placeholder,
  value,
  onChange,
  type = "text",
  autoComplete,
  rightHint,
  name,
  required,
}: {
  label: string;
  placeholder?: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  autoComplete?: string;
  rightHint?: React.ReactNode;
  name?: string;
  required?: boolean;
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
          name={name}
          required={required}
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

function StrengthPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={
        "inline-flex items-center gap-2 rounded-full border px-2 py-0.5 text-[11px] " +
        (ok
          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : "border-neutral-200 bg-neutral-50 text-neutral-500")
      }
    >
      <span className={"h-1.5 w-1.5 rounded-full " + (ok ? "bg-emerald-500" : "bg-neutral-300")} />
      {label}
    </span>
  );
}

function MiniBadge({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="rounded-2xl border border-neutral-200/70 bg-neutral-50 px-4 py-3">
      <div
        className="text-xs font-semibold text-neutral-900"
        style={{ fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular" }}
      >
        {title}
      </div>
      <div className="mt-0.5 text-xs text-neutral-600">{desc}</div>
    </div>
  );
}

function StepRow({ idx, title, desc }: { idx: number; title: string; desc: string }) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-2xl border border-white/10 bg-black/20 px-4 py-3">
      <div className="flex items-start gap-3">
        <div className="grid h-7 w-7 place-items-center rounded-full bg-white/10 text-xs text-white/75">
          {idx}
        </div>
        <div>
          <div className="text-sm text-white/90">{title}</div>
          <div className="text-xs text-white/55">{desc}</div>
        </div>
      </div>
      <div className="mt-0.5 rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] text-white/65">
        Ready
      </div>
    </div>
  );
}

function GlassStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
      <div className="text-[11px] uppercase tracking-[0.2em] text-white/45">{label}</div>
      <div
        className="mt-2 text-xl font-semibold"
        style={{ fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular" }}
      >
        {value}
      </div>
    </div>
  );
}

function Check() {
  return (
    <span className="mt-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full border border-white/10 bg-white/5">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
        <path
          d="M20 6L9 17l-5-5"
          stroke="rgba(255,255,255,0.75)"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
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
