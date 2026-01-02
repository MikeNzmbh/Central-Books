import React from "react";
import { Sparkles } from "lucide-react";

interface CompanionThinkingProps {
    surfaceLabel?: string; // e.g. "Invoices", "Banking", "Receipts", "Books"
    firstName?: string; // e.g. "Mike"
    headline?: string; // optional custom line
}

const CompanionThinkingScreen: React.FC<CompanionThinkingProps> = ({
    surfaceLabel = "Workspace",
    firstName = "there",
    headline,
}) => {
    const safeHeadline =
        headline ?? `I'm reviewing your ${surfaceLabel.toLowerCase()} right now…`;

    return (
        <section className="relative w-full rounded-3xl border border-slate-100/80 bg-white/90 shadow-[0_18px_60px_rgba(15,23,42,0.08)] px-5 py-4 sm:px-7 sm:py-5 overflow-hidden">
            {/* soft ambient halo */}
            <div className="pointer-events-none absolute inset-0 rounded-[26px] bg-[radial-gradient(circle_at_top_left,rgba(59,130,246,0.12),transparent_55%),radial-gradient(circle_at_bottom_right,rgba(45,212,191,0.1),transparent_55%)] opacity-80" />

            {/* inner glass panel */}
            <div className="relative z-10 flex flex-col gap-4 sm:gap-5">
                {/* top row: avatar + title + status chip */}
                <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                        <div className="relative">
                            <div className="flex h-10 w-10 sm:h-11 sm:w-11 items-center justify-center rounded-2xl bg-slate-900 text-[0.7rem] font-semibold tracking-[0.18em] text-white shadow-[0_12px_32px_rgba(15,23,42,0.45)]">
                                AI
                            </div>
                            <div className="pointer-events-none absolute -inset-1 rounded-3xl bg-[conic-gradient(from_210deg,rgba(59,130,246,0.3),rgba(45,212,191,0.15),transparent_40%)] blur-md opacity-80" />
                        </div>

                        <div className="flex min-w-0 flex-col">
                            <div className="text-[0.68rem] font-semibold uppercase tracking-[0.2em] text-slate-400">
                                {surfaceLabel} Companion
                            </div>
                            <div className="mt-0.5 text-sm sm:text-[0.95rem] font-semibold text-slate-900 truncate">
                                Good day, {firstName}. I'm on it.
                            </div>
                        </div>
                    </div>

                    <div className="hidden shrink-0 items-center gap-2 rounded-full border border-slate-200/80 bg-slate-50/80 px-3 py-1.5 text-[0.72rem] font-medium text-slate-600 sm:inline-flex">
                        <span className="flex h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                        <span className="inline-flex items-center gap-1">
                            <Sparkles className="h-3.5 w-3.5" />
                            Thinking through your {surfaceLabel.toLowerCase()}&hellip;
                        </span>
                    </div>
                </div>

                {/* middle: headline + skeleton lines */}
                <div className="grid gap-4 sm:grid-cols-[minmax(0,1.7fr)_minmax(0,1.1fr)] sm:items-start">
                    <div className="flex min-w-0 flex-col gap-2.5">
                        <p className="text-[0.95rem] sm:text-[1.02rem] font-semibold text-slate-900 leading-snug">
                            {safeHeadline}
                        </p>
                        <p className="text-[0.8rem] text-slate-500 leading-snug">
                            I'm cross-checking recent activity, issues, and coverage to bring you a clean, prioritized summary.
                        </p>

                        <div className="mt-1.5 flex flex-col gap-1.5 text-[0.75rem] text-slate-400">
                            <div className="h-1.5 w-32 rounded-full bg-slate-100/90 animate-pulse" />
                            <div className="h-1.5 w-40 rounded-full bg-slate-100/90 animate-pulse" style={{ animationDelay: "0.1s" }} />
                            <div className="h-1.5 w-24 rounded-full bg-slate-100/90 animate-pulse" style={{ animationDelay: "0.2s" }} />
                        </div>
                    </div>

                    {/* right: shimmer tiles */}
                    <div className="flex flex-col gap-2.5">
                        <div className="rounded-2xl border border-slate-100/90 bg-slate-50/60 px-3 py-2.5 shadow-[0_10px_30px_rgba(15,23,42,0.04)]">
                            <div className="mb-1.5 flex items-center justify-between text-[0.7rem] text-slate-500">
                                <span>Coverage snapshot</span>
                                <span className="rounded-full bg-white/80 px-2 py-0.5 text-[0.68rem] font-medium text-slate-600 shadow-sm">
                                    Updating…
                                </span>
                            </div>

                            {/* Animated progress bar - teal to blue gradient */}
                            <div className="relative mt-1 flex h-2.5 w-full items-center overflow-hidden rounded-full bg-slate-100">
                                <div
                                    className="absolute inset-y-[2px] w-1/3 rounded-full shadow-[0_0_0_1px_rgba(15,23,42,0.12)]"
                                    style={{
                                        background: "linear-gradient(to right, #2dd4bf, #14b8a6, #0ea5e9, #3b82f6)",
                                        animation: "companionLiquid 1.7s ease-in-out infinite",
                                    }}
                                />
                                <div className="pointer-events-none absolute inset-x-1 top-0 h-[1px] bg-white/60 mix-blend-screen" />
                            </div>

                            <div className="mt-2 flex items-center justify-between text-[0.7rem] text-slate-500">
                                <span>Looking across risk, coverage, and recent changes.</span>
                                <span className="hidden text-[0.65rem] uppercase tracking-[0.16em] text-slate-400 sm:inline">
                                    Live preview
                                </span>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-1.5 text-[0.72rem]">
                            <div className="rounded-xl border border-slate-100/80 bg-slate-50/70 px-2.5 py-2">
                                <div className="mb-1 h-1.5 w-16 rounded-full bg-slate-100 animate-pulse" />
                                <div className="h-1.5 w-20 rounded-full bg-slate-100 animate-pulse" style={{ animationDelay: "0.15s" }} />
                            </div>
                            <div className="rounded-xl border border-slate-100/80 bg-slate-50/70 px-2.5 py-2">
                                <div className="mb-1 h-1.5 w-14 rounded-full bg-slate-100 animate-pulse" style={{ animationDelay: "0.1s" }} />
                                <div className="h-1.5 w-24 rounded-full bg-slate-100 animate-pulse" style={{ animationDelay: "0.2s" }} />
                            </div>
                        </div>
                    </div>
                </div>

                {/* bottom helper text */}
                <div className="mt-1 flex flex-wrap items-center justify-between gap-2 text-[0.72rem] text-slate-400">
                    <span>
                        You can stay on this page &mdash; I'll update this panel as soon as your summary is ready.
                    </span>
                    <span className="rounded-full bg-slate-50/80 px-2.5 py-1 text-[0.7rem] font-medium text-slate-500 border border-slate-100">
                        No changes are posted without your approval.
                    </span>
                </div>
            </div>

            {/* Inline keyframes for the animated bar */}
            <style>{`
        @keyframes companionLiquid {
          0% { transform: translateX(-25%); }
          50% { transform: translateX(200%); }
          100% { transform: translateX(-25%); }
        }
      `}</style>
        </section>
    );
};

export default CompanionThinkingScreen;
