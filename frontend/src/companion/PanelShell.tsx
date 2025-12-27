import React, { useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { getPanelTitle, PanelType } from "./companionCopy";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface PanelShellProps {
    /** Which panel is open (null = closed) */
    panel: PanelType | null;
    /** Close handler - should clear query param */
    onClose: () => void;
    /** Optional surface filter (bank, invoices, etc.) */
    surface?: string | null;
    /** Panel content */
    children: React.ReactNode;
}

// ─────────────────────────────────────────────────────────────────────────────
// PanelShell Component
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Slide-in panel shell for AI Companion.
 * 
 * - 640px wide, slides in from right
 * - Semi-transparent overlay
 * - ESC key closes
 * - Click outside closes
 * - Only one panel open at a time
 */
export const PanelShell: React.FC<PanelShellProps> = ({
    panel,
    onClose,
    surface,
    children,
}) => {
    // ESC key handler
    const handleKeyDown = useCallback(
        (e: KeyboardEvent) => {
            if (e.key === "Escape" && panel) {
                onClose();
            }
        },
        [panel, onClose]
    );

    useEffect(() => {
        document.addEventListener("keydown", handleKeyDown);
        return () => document.removeEventListener("keydown", handleKeyDown);
    }, [handleKeyDown]);

    // Prevent body scroll when panel is open
    useEffect(() => {
        if (panel) {
            document.body.style.overflow = "hidden";
        } else {
            document.body.style.overflow = "";
        }
        return () => {
            document.body.style.overflow = "";
        };
    }, [panel]);

    return (
        <AnimatePresence>
            {panel && (
                <>
                    {/* Overlay */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="fixed inset-0 z-40 bg-slate-900/20 backdrop-blur-[2px]"
                        onClick={onClose}
                        aria-hidden="true"
                    />

                    {/* Panel */}
                    <motion.aside
                        initial={{ x: "100%" }}
                        animate={{ x: 0 }}
                        exit={{ x: "100%" }}
                        transition={{ type: "spring", damping: 30, stiffness: 300 }}
                        className="fixed right-0 top-0 z-50 h-full w-full max-w-[640px] bg-white shadow-2xl shadow-slate-900/10 flex flex-col"
                    >
                        {/* Header */}
                        <header className="flex items-center justify-between border-b border-slate-200 px-6 py-4 shrink-0">
                            <div>
                                <h2 className="text-lg font-semibold text-slate-900">
                                    {getPanelTitle(panel)}
                                </h2>
                                {surface && (
                                    <p className="text-sm text-slate-500 mt-0.5">
                                        Filtered by: <span className="font-medium capitalize">{surface}</span>
                                    </p>
                                )}
                            </div>
                            <button
                                onClick={onClose}
                                className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                                aria-label="Close panel"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </header>

                        {/* Content */}
                        <div className="flex-1 overflow-y-auto">
                            {children}
                        </div>
                    </motion.aside>
                </>
            )}
        </AnimatePresence>
    );
};

export default PanelShell;
