import React, { useEffect, useState } from "react";
import { Sparkles, ArrowRight, X } from "lucide-react";
import { buildApiUrl } from "../api/client";

type OnboardingStatus = "not_started" | "in_progress" | "completed" | "skipped";

interface SetupCardsProps {
    onDismiss?: () => void;
}

export const SetupCards: React.FC<SetupCardsProps> = ({ onDismiss }) => {
    const [status, setStatus] = useState<OnboardingStatus | null>(null);
    const [dismissed, setDismissed] = useState(false);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const checkOnboarding = async () => {
            // Check local storage first
            const localDismissed = localStorage.getItem("setup_cards_dismissed");
            if (localDismissed) {
                setDismissed(true);
                setLoading(false);
                return;
            }

            try {
                const token = localStorage.getItem("auth_token");
                const res = await fetch(buildApiUrl("/api/onboarding/profile"), {
                    headers: token ? { Authorization: `Bearer ${token}` } : {},
                    credentials: "include",
                });
                const data = await res.json();

                if (data.ok && data.profile) {
                    setStatus(data.profile.onboarding_status);
                } else {
                    setStatus("not_started");
                }
            } catch {
                setStatus("not_started");
            } finally {
                setLoading(false);
            }
        };

        checkOnboarding();
    }, []);

    const handleDismiss = () => {
        setDismissed(true);
        localStorage.setItem("setup_cards_dismissed", "true");
        onDismiss?.();
    };

    // Don't show if completed or dismissed
    if (loading || dismissed || status === "completed" || status === "skipped") {
        return null;
    }

    const isNotStarted = status === "not_started";

    return (
        <div className="rounded-2xl border border-slate-200 bg-gradient-to-r from-emerald-50 to-sky-50 p-4 sm:p-5 shadow-sm">
            <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-400 to-sky-500 flex items-center justify-center shadow">
                        <Sparkles className="w-5 h-5 text-white" />
                    </div>
                    <div className="space-y-1">
                        <h3 className="text-sm font-semibold text-slate-900">
                            {isNotStarted ? "Complete your setup" : "Continue setup"}
                        </h3>
                        <p className="text-sm text-slate-600">
                            {isNotStarted
                                ? "Tell us about your business so we can customize Clover for you."
                                : "You're almost done! Just a few more steps to go."}
                        </p>
                        <a
                            href="/onboarding"
                            className="inline-flex items-center gap-1.5 text-sm font-medium text-emerald-700 hover:text-emerald-800 mt-2"
                        >
                            {isNotStarted ? "Start setup" : "Continue"}
                            <ArrowRight className="w-4 h-4" />
                        </a>
                    </div>
                </div>
                <button
                    onClick={handleDismiss}
                    className="text-slate-400 hover:text-slate-600 p-1"
                    title="Dismiss"
                >
                    <X className="w-4 h-4" />
                </button>
            </div>
        </div>
    );
};

export default SetupCards;
