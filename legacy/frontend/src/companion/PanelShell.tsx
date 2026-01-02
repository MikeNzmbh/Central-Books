import React, { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
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
 * - 520px wide, slides in from right
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
    const title = panel ? getPanelTitle(panel) : "";

    useEffect(() => {
        if (!panel) return undefined;
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [panel, onClose]);

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
                        className="fixed inset-0 z-50 bg-black/20"
                        onClick={onClose}
                        aria-hidden="true"
                    />

                    {/* Panel */}
                    <motion.aside
                        initial={{ x: "100%" }}
                        animate={{ x: 0 }}
                        exit={{ x: "100%" }}
                        transition={{ type: "spring", damping: 30, stiffness: 300 }}
                        className="fixed right-0 top-0 z-50 h-full w-full max-w-[520px] border-l border-zinc-200 bg-white shadow-2xl flex flex-col"
                    >
                        {/* Header */}
                        <header className="flex items-center justify-between border-b border-zinc-200 px-5 py-4 shrink-0">
                            <div>
                                <div className="text-sm font-semibold text-zinc-950">{title}</div>
                                {surface && (
                                    <div className="mt-1 text-[11px] text-zinc-500">
                                        Filtered by: <span className="font-medium capitalize">{surface}</span>
                                    </div>
                                )}
                            </div>
                            <Button variant="ghost" size="icon" onClick={onClose} className="rounded-full">
                                <X className="h-4 w-4" />
                            </Button>
                        </header>

                        {/* Content */}
                        <div className="flex-1 overflow-auto p-5">
                            {children}
                        </div>

                        <div className="border-t border-zinc-200 px-5 py-4 text-[11px] text-zinc-500">
                            Tip: Press <span className="font-semibold">Esc</span> to close.
                        </div>
                    </motion.aside>
                </>
            )}
        </AnimatePresence>
    );
};

export default PanelShell;
