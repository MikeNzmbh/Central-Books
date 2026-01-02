import React, { createContext, useContext, useState, useCallback, ReactNode } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, Undo2 } from "lucide-react";
import { Button } from "../components/ui/button";

/** 
 * Toast notification system for QBO-style "action + undo" pattern.
 * Shows brief success messages with optional undo callback.
 */

interface ToastData {
    id: number;
    message: string;
    type: "success" | "error" | "info";
    onUndo?: () => void;
    duration: number;
}

interface ToastContextValue {
    showToast: (params: {
        message: string;
        type?: "success" | "error" | "info";
        onUndo?: () => void;
        duration?: number;
    }) => void;
    dismissToast: (id: number) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
    const ctx = useContext(ToastContext);
    if (!ctx) {
        throw new Error("useToast must be used within ToastProvider");
    }
    return ctx;
}

export function ToastProvider({ children }: { children: ReactNode }) {
    const [toasts, setToasts] = useState<ToastData[]>([]);
    const toastIdRef = React.useRef(0);

    const showToast = useCallback(
        ({
            message,
            type = "success",
            onUndo,
            duration = 5000,
        }: {
            message: string;
            type?: "success" | "error" | "info";
            onUndo?: () => void;
            duration?: number;
        }) => {
            const id = ++toastIdRef.current;
            const toast: ToastData = { id, message, type, onUndo, duration };
            setToasts((prev) => [...prev, toast]);

            // Auto-dismiss after duration
            setTimeout(() => {
                setToasts((prev) => prev.filter((t) => t.id !== id));
            }, duration);
        },
        []
    );

    const dismissToast = useCallback((id: number) => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
    }, []);

    return (
        <ToastContext.Provider value={{ showToast, dismissToast }}>
            {children}
            <ToastContainer toasts={toasts} onDismiss={dismissToast} />
        </ToastContext.Provider>
    );
}

function ToastContainer({
    toasts,
    onDismiss,
}: {
    toasts: ToastData[];
    onDismiss: (id: number) => void;
}) {
    return (
        <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
            <AnimatePresence mode="popLayout">
                {toasts.map((toast) => (
                    <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
                ))}
            </AnimatePresence>
        </div>
    );
}

function ToastItem({
    toast,
    onDismiss,
}: {
    toast: ToastData;
    onDismiss: (id: number) => void;
}) {
    const handleUndo = () => {
        if (toast.onUndo) {
            toast.onUndo();
        }
        onDismiss(toast.id);
    };

    const bgColor =
        toast.type === "error"
            ? "bg-red-900"
            : toast.type === "info"
                ? "bg-slate-800"
                : "bg-zinc-900";

    const borderColor =
        toast.type === "error"
            ? "border-red-700"
            : toast.type === "info"
                ? "border-slate-600"
                : "border-emerald-700";

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95, transition: { duration: 0.15 } }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
            className={`${bgColor} ${borderColor} border rounded-2xl px-4 py-3 shadow-lg flex items-center gap-3 text-white`}
        >
            <span className="text-sm font-medium flex-1">{toast.message}</span>

            {toast.onUndo && (
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleUndo}
                    className="text-emerald-400 hover:text-emerald-300 hover:bg-emerald-900/50 px-2 py-1 h-auto text-xs font-semibold rounded-lg"
                >
                    <Undo2 className="h-3 w-3 mr-1" />
                    Undo
                </Button>
            )}

            <button
                onClick={() => onDismiss(toast.id)}
                className="text-zinc-400 hover:text-white transition-colors"
            >
                <X className="h-4 w-4" />
            </button>
        </motion.div>
    );
}

export default ToastProvider;
