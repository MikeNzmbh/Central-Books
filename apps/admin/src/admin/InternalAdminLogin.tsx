import React, { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

const canAccessAdmin = (user?: { is_admin?: boolean; role?: string | null; is_superuser?: boolean; is_staff?: boolean }) =>
  Boolean(
    user &&
      (user.is_admin ||
        user.role === "admin" ||
        user.role === "superadmin" ||
        user.is_superuser ||
        user.is_staff)
  );

export const InternalAdminLogin: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [email, setEmail] = useState("admin@cloverbooks.local");
  const [password, setPassword] = useState("changeme");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const redirectPath = (location.state as { from?: string } | undefined)?.from ?? "/control-tower";

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await login(email, password);
      if (!canAccessAdmin(response.user)) {
        setError("You don't have access to the admin workspace.");
        return;
      }
      navigate(redirectPath, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in. Try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100 flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-white font-semibold">
            CT
          </div>
          <h1 className="text-2xl font-semibold text-slate-900">Control Tower</h1>
          <p className="text-sm text-slate-600">Sign in to the Clover Books admin console</p>
        </div>
        <form
          onSubmit={handleSubmit}
          className="space-y-4 rounded-2xl border border-slate-200 bg-white/90 p-5 shadow-[0_25px_60px_rgba(15,23,42,0.12)]"
        >
          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </div>
          )}
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
              placeholder="admin@cloverbooks.local"
              required
            />
          </div>
          <div className="space-y-1">
            <label className="text-xs font-semibold text-slate-700">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-200"
              placeholder="••••••••"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {loading ? "Signing in…" : "Enter control tower"}
          </button>
          <p className="text-xs text-center text-slate-500">
            Internal staff only. Activity is monitored and audited.
          </p>
        </form>
      </div>
    </div>
  );
};
