import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

interface InviteData {
    valid: boolean;
    role?: string;
    email?: string | null;
    email_locked?: boolean;
    error?: string;
}

export const InviteRedeemPage: React.FC = () => {
    const { token } = useParams<{ token: string }>();
    const [invite, setInvite] = useState<InviteData | null>(null);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // Form fields
    const [username, setUsername] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [firstName, setFirstName] = useState("");
    const [lastName, setLastName] = useState("");

    useEffect(() => {
        if (!token) return;
        fetch(`/api/admin/invite/${token}/`)
            .then((res) => res.json())
            .then((data) => {
                setInvite(data);
                if (data.email) setEmail(data.email);
                setLoading(false);
            })
            .catch(() => {
                setInvite({ valid: false, error: "Could not validate invite." });
                setLoading(false);
            });
    }, [token]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        if (password !== confirmPassword) {
            setError("Passwords do not match.");
            return;
        }

        if (password.length < 8) {
            setError("Password must be at least 8 characters.");
            return;
        }

        setSubmitting(true);

        try {
            const res = await fetch(`/api/admin/invite/${token}/`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    username,
                    email,
                    password,
                    first_name: firstName,
                    last_name: lastName,
                }),
            });
            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.error || data.detail || "Failed to create account.");
            }

            setSuccess(data.message || "Account created! Redirecting to login...");
            setTimeout(() => {
                const redirectTo = data.redirect || "/internal-admin/login/";
                window.location.assign(redirectTo);
            }, 2000);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Something went wrong.");
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                <div className="text-slate-600">Validating invite...</div>
            </div>
        );
    }

    if (!invite?.valid) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
                <div className="w-full max-w-md text-center space-y-4">
                    <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-50 text-rose-600 text-2xl">
                        ✕
                    </div>
                    <h1 className="text-xl font-semibold text-slate-900">Invalid Invite</h1>
                    <p className="text-sm text-slate-600">{invite?.error || "This invite link is invalid or has expired."}</p>
                    <a
                        href="/internal-admin/login"
                        className="inline-block mt-4 text-sm font-medium text-emerald-600 hover:text-emerald-500"
                    >
                        Go to login →
                    </a>
                </div>
            </div>
        );
    }

    if (success) {
        return (
            <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4">
                <div className="w-full max-w-md text-center space-y-4">
                    <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 text-2xl">
                        ✓
                    </div>
                    <h1 className="text-xl font-semibold text-slate-900">Account Created!</h1>
                    <p className="text-sm text-slate-600">{success}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center px-4 py-10">
            <div className="w-full max-w-md space-y-6">
                <div className="text-center space-y-2">
                    <div className="inline-flex h-10 w-10 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700 font-semibold">
                        CB
                    </div>
                    <h1 className="text-2xl font-semibold text-slate-900">Join Clover Books Admin</h1>
                    <p className="text-sm text-slate-600">
                        You've been invited as <span className="font-medium text-emerald-600">{invite.role}</span>
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                    {error && (
                        <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
                    )}

                    <div className="grid grid-cols-2 gap-3">
                        <div className="space-y-1">
                            <label className="text-xs font-semibold text-slate-700">First name</label>
                            <input
                                type="text"
                                value={firstName}
                                onChange={(e) => setFirstName(e.target.value)}
                                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
                                placeholder="Jane"
                            />
                        </div>
                        <div className="space-y-1">
                            <label className="text-xs font-semibold text-slate-700">Last name</label>
                            <input
                                type="text"
                                value={lastName}
                                onChange={(e) => setLastName(e.target.value)}
                                className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
                                placeholder="Doe"
                            />
                        </div>
                    </div>

                    <div className="space-y-1">
                        <label className="text-xs font-semibold text-slate-700">Username</label>
                        <input
                            type="text"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
                            placeholder="janedoe"
                            required
                        />
                    </div>

                    <div className="space-y-1">
                        <label className="text-xs font-semibold text-slate-700">Email</label>
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            disabled={invite.email_locked}
                            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50 disabled:bg-slate-50 disabled:text-slate-500"
                            placeholder="jane@cernbooks.com"
                            required
                        />
                        {invite.email_locked && (
                            <p className="text-xs text-slate-500">This invite is for this email address only.</p>
                        )}
                    </div>

                    <div className="space-y-1">
                        <label className="text-xs font-semibold text-slate-700">Password</label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
                            placeholder="••••••••"
                            required
                            minLength={8}
                        />
                    </div>

                    <div className="space-y-1">
                        <label className="text-xs font-semibold text-slate-700">Confirm password</label>
                        <input
                            type="password"
                            value={confirmPassword}
                            onChange={(e) => setConfirmPassword(e.target.value)}
                            className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-emerald-400 focus:outline-none focus:ring-2 focus:ring-emerald-50"
                            placeholder="••••••••"
                            required
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={submitting}
                        className="w-full rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-70"
                    >
                        {submitting ? "Creating account..." : "Create account"}
                    </button>

                    <p className="text-xs text-center text-slate-500">
                        By creating an account, you agree to Clover Books' terms of service.
                    </p>
                </form>
            </div>
        </div>
    );
};
