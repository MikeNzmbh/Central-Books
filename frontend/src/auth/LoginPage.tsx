import React from "react";

type Message = {
  level: string;
  message: string;
};

export type LoginPayload = {
  action: string;
  csrfToken: string;
  next?: string;
  signupUrl: string;
  forgotUrl: string;
  messages?: Message[];
};

const AuthShell: React.FC<{
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}> = ({ title, subtitle, children }) => (
  <div className="min-h-screen w-full bg-slate-50 flex items-center justify-center px-4 py-10 text-slate-900">
    <div className="max-w-5xl w-full grid gap-10 lg:grid-cols-[1.2fr,0.9fr] items-stretch">
      <section className="bg-white/90 backdrop-blur rounded-3xl shadow-lg border border-slate-100 px-6 sm:px-10 py-8 sm:py-10 flex flex-col gap-6">
        <header className="space-y-5">
          <div className="flex items-center gap-3">
            <div className="inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 text-white text-sm font-semibold">
              MB
            </div>
            <div className="space-y-1">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                Mini-Books
              </p>
              <p className="text-[11px] text-slate-500">Calm accounting, live cash.</p>
            </div>
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-slate-900">
              {title}
            </h1>
            {subtitle && <p className="text-sm text-slate-600 max-w-md">{subtitle}</p>}
          </div>
        </header>
        <div className="space-y-6">{children}</div>
        <footer className="pt-2 text-[11px] text-slate-400 flex items-center justify-between flex-wrap gap-2">
          <span>© {new Date().getFullYear()} Mini-Books</span>
          <span>Built for owner-led businesses.</span>
        </footer>
      </section>
      <aside className="hidden lg:flex flex-col justify-between rounded-3xl border border-slate-100 bg-gradient-to-br from-slate-50 via-white to-sky-50 shadow-sm p-6">
        <div className="space-y-6">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-white/80 border border-slate-100 px-3 py-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Live cash preview
            </span>
            <span>Central-Books · Dashboard</span>
          </div>
          <div className="rounded-2xl bg-white/90 border border-slate-100 shadow-sm p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Cash on hand</p>
                <p className="mt-1 text-xl font-semibold text-slate-900">$24,380.12</p>
              </div>
              <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-medium text-emerald-700">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                +12.4% vs last month
              </div>
            </div>
            <div className="relative h-24 rounded-xl bg-slate-50 overflow-hidden">
              <div className="absolute inset-x-4 bottom-3 top-4 flex items-end gap-1.5">
                <div className="flex-1 rounded-full bg-sky-100 h-4" />
                <div className="flex-1 rounded-full bg-sky-200 h-7" />
                <div className="flex-1 rounded-full bg-sky-300 h-10" />
                <div className="flex-1 rounded-full bg-sky-200 h-6" />
                <div className="flex-1 rounded-full bg-sky-400 h-12" />
              </div>
              <div className="absolute inset-0 bg-gradient-to-t from-white/40 to-transparent" />
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-3 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-slate-800">Invoices</span>
                  <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700">
                    8 paid · 3 open
                  </span>
                </div>
                <p className="text-[11px] text-slate-500">Clean aging, no double-counting.</p>
              </div>
              <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-3 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-slate-800">Bank feed</span>
                  <span className="inline-flex items-center rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-medium text-sky-700">
                    3 to review
                  </span>
                </div>
                <p className="text-[11px] text-slate-500">Every line tied back to the ledger.</p>
              </div>
            </div>
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Sign in once to see a reconciled dashboard—cash, invoices, expenses, and tax-ready
            ledgers always in sync.
          </p>
        </div>
        <div className="flex items-center justify-between text-[11px] text-slate-500">
          <span className="inline-flex items-center gap-1">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Secure by default
          </span>
          <span>CAD / USD ready</span>
        </div>
      </aside>
    </div>
  </div>
);

const AlertStack: React.FC<{ messages?: Message[] }> = ({ messages }) => {
  if (!messages || messages.length === 0) {
    return null;
  }
  return (
    <div className="space-y-2">
      {messages.map((msg, idx) => (
        <div
          key={`${msg.message}-${idx}`}
          className={`rounded-2xl border px-3.5 py-2 text-sm ${
            msg.level === "success"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-rose-200 bg-rose-50 text-rose-700"
          }`}
        >
          {msg.message}
        </div>
      ))}
    </div>
  );
};

const LoginPage: React.FC<{ data: LoginPayload }> = ({ data }) => (
  <AuthShell
    title="Sign in to Central-Books"
    subtitle="Use your work email to access invoices, expenses, and live cash."
  >
    <AlertStack messages={data.messages} />
    <form
      method="POST"
      action={data.action}
      className="space-y-5"
      noValidate
    >
      <input type="hidden" name="csrfmiddlewaretoken" value={data.csrfToken} />
      {data.next && <input type="hidden" name="next" value={data.next} />}
      <div className="space-y-1.5 text-sm">
        <label className="block text-slate-700" htmlFor="id_username">
          Email
        </label>
        <input
          id="id_username"
          name="username"
          type="email"
          autoComplete="username"
          required
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/80 focus:ring-offset-1 focus:ring-offset-slate-50"
          placeholder="you@example.com"
        />
      </div>
      <div className="space-y-1.5 text-sm">
        <div className="flex items-center justify-between">
          <label className="block text-slate-700" htmlFor="id_password">
            Password
          </label>
          <a
            href={data.forgotUrl || "#"}
            className="text-[11px] font-medium text-slate-500 hover:text-slate-800"
          >
            Forgot password?
          </a>
        </div>
        <input
          id="id_password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-900/80 focus:ring-offset-1 focus:ring-offset-slate-50"
          placeholder="••••••••••"
        />
      </div>
      <label className="inline-flex items-center gap-2 text-[13px] text-slate-600">
        <input
          type="checkbox"
          name="remember_me"
          className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900/70"
        />
        Remember me on this device
      </label>
      <button
        type="submit"
        className="w-full inline-flex items-center justify-center rounded-full bg-slate-900 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-slate-800 active:bg-slate-900 transition"
      >
        Sign in
      </button>
      <p className="text-xs text-slate-500 text-center">
        Don’t have an account yet?{" "}
        <a href={data.signupUrl} className="font-semibold text-slate-800 hover:underline">
          Sign up
        </a>
      </p>
    </form>
  </AuthShell>
);

export default LoginPage;
