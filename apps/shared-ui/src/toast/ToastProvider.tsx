import React, { createContext, useCallback, useContext, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Undo2, X } from "lucide-react";
import { Button } from "../components/primitives";

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

export const useToast = () => {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return ctx;
};

export const ToastProvider = ({ children }: { children: React.ReactNode }) => {
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
};

const ToastContainer = ({
  toasts,
  onDismiss,
}: {
  toasts: ToastData[];
  onDismiss: (id: number) => void;
}) => (
  <div className="fixed bottom-4 right-4 z-50 flex max-w-sm flex-col gap-2">
    <AnimatePresence mode="popLayout">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </AnimatePresence>
  </div>
);

const ToastItem = ({
  toast,
  onDismiss,
}: {
  toast: ToastData;
  onDismiss: (id: number) => void;
}) => {
  const handleUndo = () => {
    toast.onUndo?.();
    onDismiss(toast.id);
  };

  const bgColor =
    toast.type === "error"
      ? "bg-rose-900"
      : toast.type === "info"
      ? "bg-slate-800"
      : "bg-zinc-900";

  const borderColor =
    toast.type === "error"
      ? "border-rose-700"
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
      className={`${bgColor} ${borderColor} flex items-center gap-3 rounded-2xl border px-4 py-3 text-white shadow-lg`}
    >
      <span className="flex-1 text-sm font-medium">{toast.message}</span>

      {toast.onUndo ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={handleUndo}
          className="h-auto rounded-lg px-2 py-1 text-xs font-semibold text-emerald-400 hover:bg-emerald-900/50 hover:text-emerald-300"
        >
          <Undo2 className="mr-1 h-3 w-3" />
          Undo
        </Button>
      ) : null}

      <button
        onClick={() => onDismiss(toast.id)}
        className="text-zinc-400 transition-colors hover:text-white"
      >
        <X className="h-4 w-4" />
      </button>
    </motion.div>
  );
};
