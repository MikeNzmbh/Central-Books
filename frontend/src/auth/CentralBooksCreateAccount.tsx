import React from "react";

interface CentralBooksCreateAccountProps {
  action?: string;
  csrfToken?: string;
  errors?: string[];
  initialEmail?: string;
  initialBusinessName?: string;
}

const CentralBooksCreateAccount: React.FC<CentralBooksCreateAccountProps> = ({
  action = "/signup/",
  csrfToken,
  errors = [],
  initialEmail = "",
  initialBusinessName = "",
}) => {
  return (
    <div className="min-h-screen w-full bg-slate-50 text-slate-900 flex items-center justify-center px-4 py-10">
      <div className="max-w-5xl w-full grid gap-10 lg:grid-cols-[1.05fr,0.95fr] items-stretch">
        <section className="hidden lg:flex flex-col justify-between rounded-3xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-slate-50 p-8 shadow-xl">
          <div className="space-y-6">
            <div className="inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-slate-100">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              <span>Central-Books workspace</span>
            </div>
            <div className="space-y-3">
              <h1 className="text-3xl font-semibold tracking-tight">
                Create your Central-Books account
              </h1>
              <p className="text-sm text-slate-200/80 max-w-sm">
                Spin up a clean, lightweight accounting workspace. Perfect for small studios, contractors, and solo founders.
              </p>
            </div>
          </div>
          <div className="mt-6 rounded-2xl bg-slate-900/40 border border-white/10 p-4 space-y-4">
            <div className="flex items-center justify-between text-xs text-slate-200/90">
              <span className="font-medium">Your first 10 minutes</span>
              <span className="text-slate-300/80">3 quick steps</span>
            </div>
            <div className="space-y-2 text-[11px] text-slate-200/80">
              <div className="flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-[10px]">1</span>
                <div>
                  <p className="font-medium">Create your account</p>
                  <p className="text-slate-300/80">Email, name, and a secure password.</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-sky-500/20 text-[10px]">2</span>
                <div>
                  <p className="font-medium">Tell us about your business</p>
                  <p className="text-slate-300/80">Currency, year-end, and base country.</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-500/20 text-[10px]">3</span>
                <div>
                  <p className="font-medium">Connect money or import CSV</p>
                  <p className="text-slate-300/80">Start with a bank feed or sample data.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="bg-white/95 backdrop-blur rounded-3xl shadow-lg border border-slate-100 px-7 sm:px-9 py-8 sm:py-10 flex flex-col justify-center">
          <div className="mb-6 space-y-2">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-2xl bg-slate-900 flex items-center justify-center text-xs font-semibold text-slate-50">
                MB
              </div>
              <div className="flex flex-col">
                <span className="text-xs font-medium tracking-wide text-slate-500 uppercase">Mini-Books</span>
                <span className="text-sm font-medium text-slate-900">Central-Books</span>
              </div>
            </div>
            <h2 className="text-xl sm:text-2xl font-semibold tracking-tight text-slate-900 mt-4">Create your account</h2>
            <p className="text-sm text-slate-500">
              Use an email you check often. We&apos;ll send important updates about invoices, payments, and bank activity.
            </p>
          </div>

          {errors.length > 0 && (
            <div className="mb-4 space-y-1 rounded-2xl border border-rose-100 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {errors.map((msg, idx) => (
                <p key={idx}>{msg}</p>
              ))}
            </div>
          )}

          <form method="post" action={action} className="space-y-4">
            {csrfToken && <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />}

            <div className="space-y-1.5">
              <label htmlFor="id_full_name" className="text-sm font-medium text-slate-800">
                Your name
              </label>
              <input
                id="id_full_name"
                name="full_name"
                type="text"
                autoComplete="name"
                required
                className="block w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 shadow-sm outline-none ring-0 transition focus:border-slate-400 focus:bg-white"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="id_email" className="text-sm font-medium text-slate-800">
                Work email
              </label>
              <input
                id="id_email"
                name="email"
                type="email"
                defaultValue={initialEmail}
                autoComplete="email"
                required
                className="block w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 shadow-sm outline-none ring-0 transition focus:border-slate-400 focus:bg-white"
              />
            </div>

            <div className="space-y-1.5">
              <label htmlFor="id_business_name" className="text-sm font-medium text-slate-800">
                Business or project name
              </label>
              <input
                id="id_business_name"
                name="business_name"
                type="text"
                defaultValue={initialBusinessName}
                autoComplete="organization"
                required
                className="block w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 shadow-sm outline-none ring-0 transition focus:border-slate-400 focus:bg-white"
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label htmlFor="id_password1" className="text-sm font-medium text-slate-800">
                  Password
                </label>
                <input
                  id="id_password1"
                  name="password1"
                  type="password"
                  autoComplete="new-password"
                  required
                  className="block w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 shadow-sm outline-none ring-0 transition focus:border-slate-400 focus:bg-white"
                />
                <p className="text-[11px] text-slate-500">At least 8 characters, ideally a phrase you won&apos;t forget.</p>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="id_password2" className="text-sm font-medium text-slate-800">
                  Confirm password
                </label>
                <input
                  id="id_password2"
                  name="password2"
                  type="password"
                  autoComplete="new-password"
                  required
                  className="block w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 shadow-sm outline-none ring-0 transition focus:border-slate-400 focus:bg-white"
                />
              </div>
            </div>

            <div className="flex flex-col gap-3 pt-1">
              <label className="inline-flex items-start gap-2 text-xs text-slate-600">
                <input
                  type="checkbox"
                  name="accept_tos"
                  required
                  className="mt-0.5 h-3.5 w-3.5 rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                />
                <span>
                  I agree to the
                  <button
                    type="button"
                    className="ml-1 font-medium text-slate-900 underline decoration-slate-300 underline-offset-2 hover:decoration-slate-500"
                  >
                    Terms of Use
                  </button>
                  and
                  <button
                    type="button"
                    className="ml-1 font-medium text-slate-900 underline decoration-slate-300 underline-offset-2 hover:decoration-slate-500"
                  >
                    Privacy Policy
                  </button>
                  .
                </span>
              </label>
            </div>

            <button
              type="submit"
              className="mt-3 inline-flex w-full items-center justify-center rounded-2xl bg-slate-900 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-slate-800 active:bg-slate-900 transition"
            >
              Create account
            </button>

            <p className="pt-3 text-xs text-slate-500 text-center">
              Already using Central-Books?{" "}
              <a href="/login/" className="font-medium text-slate-900 hover:underline">
                Sign in
              </a>
            </p>
          </form>
        </section>
      </div>
    </div>
  );
};

export default CentralBooksCreateAccount;
