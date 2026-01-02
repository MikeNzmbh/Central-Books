import React, { useState } from "react";
import { ChevronDown, ChevronUp, Sparkles, ArrowRight } from "lucide-react";

interface Task {
    title: string;
    body: string;
    color: string;
    cta: string;
    href: string;
}

interface AICommandStripProps {
    tasks: Task[];
}

/**
 * Full-width AI command strip with collapsible task list.
 * Shows the primary task with a CTA, and can expand to show all tasks.
 */
export const AICommandStrip: React.FC<AICommandStripProps> = ({ tasks }) => {
    const [isExpanded, setIsExpanded] = useState(false);

    const primaryTask = tasks[0];
    const hasMultipleTasks = tasks.length > 1;

    if (!tasks.length) {
        return (
            <div className="rounded-3xl border border-slate-100 bg-white/90 p-4 shadow-sm">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-50">
                            <Sparkles className="h-5 w-5 text-emerald-500" />
                        </div>
                        <div>
                            <p className="text-sm font-medium text-slate-900">Everything looks good</p>
                            <p className="text-xs text-slate-500">No outstanding tasks right now</p>
                        </div>
                    </div>
                    <span className="flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-600">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                        All clear
                    </span>
                </div>
            </div>
        );
    }

    return (
        <div className="rounded-3xl border border-slate-100 bg-white/90 shadow-sm overflow-hidden">
            {/* Primary task strip */}
            <div className="p-4">
                <div className="flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 flex-1 min-w-0">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100">
                            <Sparkles className="h-5 w-5 text-slate-600" />
                        </div>
                        <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium text-slate-900 truncate">{primaryTask.title}</p>
                            <p className="text-xs text-slate-500 truncate">{primaryTask.body}</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                        <a
                            href={primaryTask.href}
                            className="inline-flex items-center gap-1.5 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white shadow-sm transition-all hover:bg-slate-800 hover:scale-105 active:scale-95"
                        >
                            {primaryTask.cta}
                            <ArrowRight className="h-3 w-3" />
                        </a>

                        {hasMultipleTasks && (
                            <button
                                onClick={() => setIsExpanded(!isExpanded)}
                                className="flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50"
                            >
                                <span>{tasks.length - 1} more</span>
                                {isExpanded ? (
                                    <ChevronUp className="h-3 w-3" />
                                ) : (
                                    <ChevronDown className="h-3 w-3" />
                                )}
                            </button>
                        )}
                    </div>
                </div>

                {/* Progress indicator */}
                <div className="mt-3 flex items-center gap-2">
                    <div className="flex-1 h-1 rounded-full bg-slate-100 overflow-hidden">
                        <div
                            className="h-full bg-gradient-to-r from-slate-400 to-emerald-500 transition-all duration-500"
                            style={{ width: `${(1 / tasks.length) * 100}%` }}
                        />
                    </div>
                    <span className="text-[10px] text-slate-400">{tasks.length} task{tasks.length > 1 ? "s" : ""}</span>
                </div>
            </div>

            {/* Expandable task list */}
            {isExpanded && hasMultipleTasks && (
                <div className="border-t border-slate-100 bg-slate-50/50 px-4 py-3">
                    <ul className="space-y-2">
                        {tasks.slice(1).map((task, idx) => (
                            <li
                                key={`${task.title}-${idx}`}
                                className="flex items-center justify-between gap-3 rounded-xl bg-white px-3 py-2 transition-colors hover:bg-slate-50 border border-slate-100"
                            >
                                <div className="flex items-center gap-2 min-w-0">
                                    <span className={`h-2 w-2 rounded-full shrink-0 ${task.color}`} />
                                    <div className="min-w-0">
                                        <p className="text-xs font-medium text-slate-900 truncate">{task.title}</p>
                                        <p className="text-[10px] text-slate-500 truncate">{task.body}</p>
                                    </div>
                                </div>
                                <a
                                    href={task.href}
                                    className="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1 text-[10px] font-medium text-slate-700 transition-colors hover:bg-slate-50"
                                >
                                    {task.cta}
                                </a>
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </div>
    );
};

export default AICommandStrip;
