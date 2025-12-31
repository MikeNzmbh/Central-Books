// Stub UI components for shadcn/ui
// These provide basic functionality for the ReconciliationPage

import React from "react";

// Helper function to combine class names
const cn = (...classes: (string | undefined | false)[]) => {
    return classes.filter(Boolean).join(" ");
};

// Card Components
export const Card = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={cn("rounded-lg border bg-white shadow-sm", className)} {...props}>
        {children}
    </div>
);

export const CardHeader = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={cn("flex flex-col space-y-1.5 p-6", className)} {...props}>
        {children}
    </div>
);

export const CardContent = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={cn("p-6 pt-0", className)} {...props}>
        {children}
    </div>
);

export const CardFooter = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={cn("flex items-center p-6 pt-0", className)} {...props}>
        {children}
    </div>
);

export const CardTitle = ({ className, children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3 className={cn("text-lg font-semibold leading-none tracking-tight", className)} {...props}>
        {children}
    </h3>
);

export const CardDescription = ({ className, children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className={cn("text-sm text-slate-500", className)} {...props}>
        {children}
    </p>
);

// Switch Component
export const Switch = ({ checked, onCheckedChange, disabled, className, ...props }: React.HTMLAttributes<HTMLButtonElement> & { checked?: boolean; onCheckedChange?: (checked: boolean) => void; disabled?: boolean }) => (
    <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        className={cn(
            "relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:cursor-not-allowed disabled:opacity-50",
            checked ? "bg-slate-900" : "bg-slate-200",
            className
        )}
        onClick={() => !disabled && onCheckedChange?.(!checked)}
        {...props}
    >
        <span
            className={cn(
                "pointer-events-none block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform",
                checked ? "translate-x-5" : "translate-x-0"
            )}
        />
    </button>
);

// Button Component
export const Button = React.forwardRef<
    HTMLButtonElement,
    React.ButtonHTMLAttributes<HTMLButtonElement> & {
        variant?: "default" | "outline" | "ghost" | "destructive" | "secondary";
        size?: "default" | "sm" | "lg" | "icon";
    }
>(({ className, variant = "default", size = "default", ...props }, ref) => {
    const baseStyles = "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 disabled:opacity-50 disabled:pointer-events-none";
    const variantStyles = {
        default: "bg-slate-900 text-white hover:bg-slate-800",
        outline: "border border-slate-200 bg-white hover:bg-slate-100",
        ghost: "hover:bg-slate-100",
        destructive: "bg-red-500 text-white hover:bg-red-600",
        secondary: "bg-slate-100 text-slate-900 hover:bg-slate-200",
    };
    const sizeStyles = {
        default: "h-10 py-2 px-4 text-sm",
        sm: "h-9 px-3 text-xs",
        lg: "h-11 px-8 text-base",
        icon: "h-10 w-10",
    };
    return (
        <button
            ref={ref}
            className={cn(baseStyles, variantStyles[variant], sizeStyles[size], className)}
            {...props}
        />
    );
});
Button.displayName = "Button";

// Badge Component
export const Badge = ({ className, variant = "default", children, ...props }: React.HTMLAttributes<HTMLDivElement> & {
    variant?: "default" | "secondary" | "destructive" | "outline";
}) => {
    const variantStyles = {
        default: "bg-slate-900 text-white",
        secondary: "bg-slate-100 text-slate-900",
        destructive: "bg-red-500 text-white",
        outline: "border border-slate-200",
    };
    return (
        <div className={cn("inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold", variantStyles[variant], className)} {...props}>
            {children}
        </div>
    );
};

// Progress Component
export const Progress = ({ value, className, ...props }: React.HTMLAttributes<HTMLDivElement> & { value?: number }) => (
    <div className={cn("relative h-4 w-full overflow-hidden rounded-full bg-slate-200", className)} {...props}>
        <div
            className="h-full bg-slate-900 transition-all"
            style={{ width: `${Math.min(100, Math.max(0, value || 0))}%` }}
        />
    </div>
);

// Input Component
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
    ({ className, ...props }, ref) => (
        <input
            ref={ref}
            className={cn(
                "flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:cursor-not-allowed disabled:opacity-50",
                className
            )}
            {...props}
        />
    )
);
Input.displayName = "Input";

// Select Components (simple controlled dropdown)
type SelectContextType = {
    value?: string;
    open: boolean;
    setOpen: (open: boolean) => void;
    onSelect: (value: string, label?: string) => void;
    setLabel: (label?: string) => void;
    selectedLabel?: string;
    disabled?: boolean;
};

const SelectContext = React.createContext<SelectContextType | null>(null);
const useSelectContext = () => React.useContext<SelectContextType | null>(SelectContext);

const textFromNode = (node: React.ReactNode): string => {
    if (typeof node === "string" || typeof node === "number") return String(node);
    if (Array.isArray(node)) return node.map(textFromNode).join("");
    if (React.isValidElement(node)) return textFromNode(node.props.children);
    return "";
};

export const Select = ({
    children,
    value,
    onValueChange,
    disabled,
}: {
    children: React.ReactNode;
    value?: string;
    onValueChange?: (value: string) => void;
    disabled?: boolean;
}) => {
    const [open, setOpen] = React.useState(false);
    const [selectedLabel, setSelectedLabel] = React.useState<string | undefined>();
    const containerRef = React.useRef<HTMLDivElement>(null);

    const handleSelect = React.useCallback(
        (val: string, label?: string) => {
            if (label) setSelectedLabel(label);
            onValueChange?.(val);
            setOpen(false);
        },
        [onValueChange]
    );

    React.useEffect(() => {
        const handler = (event: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setOpen(false);
            }
        };
        document.addEventListener("mousedown", handler);
        return () => document.removeEventListener("mousedown", handler);
    }, []);

    return (
        <SelectContext.Provider
            value={{
                value,
                open,
                setOpen: disabled ? () => undefined : setOpen,
                onSelect: handleSelect,
                setLabel: setSelectedLabel,
                selectedLabel,
                disabled,
            }}
        >
            <div ref={containerRef} className="relative">
                {children}
            </div>
        </SelectContext.Provider>
    );
};

export const SelectTrigger = React.forwardRef<
    HTMLButtonElement,
    React.ButtonHTMLAttributes<HTMLButtonElement> & { value?: string; onValueChange?: (value: string) => void }
>(({ className, children, ...props }, ref) => {
    const ctx = useSelectContext();
    const toggle = () => {
        if (ctx?.disabled) return;
        ctx?.setOpen(!ctx.open);
    };
    return (
        <button
            ref={ref}
            type="button"
            className={cn(
                "flex h-10 w-full items-center justify-between rounded-md border border-slate-200 bg-white px-3 py-2 text-sm",
                ctx?.disabled ? "cursor-not-allowed opacity-60" : "",
                className
            )}
            onClick={toggle}
            {...props}
        >
            {children}
        </button>
    );
});
SelectTrigger.displayName = "SelectTrigger";

export const SelectValue = ({ placeholder }: { placeholder?: string }) => {
    const ctx = useSelectContext();
    const display = ctx?.selectedLabel || placeholder || ctx?.value || "";
    return <span className="truncate text-left">{display}</span>;
};

export const SelectContent = ({ children, className }: { children: React.ReactNode; className?: string }) => {
    const ctx = useSelectContext();
    if (!ctx?.open) return null;
    return (
        <div className={cn("absolute z-20 mt-1 w-full rounded-md border border-slate-200 bg-white p-1 shadow-md", className)}>
            {children}
        </div>
    );
};

export const SelectItem = ({ value, children }: { value: string; children: React.ReactNode }) => {
    const ctx = useSelectContext();
    const label = textFromNode(children) || value;
    const isSelected = ctx?.value === value;

    React.useEffect(() => {
        if (isSelected && label && ctx && !ctx.selectedLabel) {
            ctx.setLabel(label);
        }
    }, [isSelected, label, ctx]);

    const handleClick = () => {
        if (ctx?.disabled) return;
        ctx?.setLabel(label);
        ctx?.onSelect(value, label);
    };

    return (
        <div
            className={cn(
                "cursor-pointer rounded-sm px-2 py-1.5 text-sm hover:bg-slate-100",
                isSelected ? "bg-slate-100 text-slate-900" : "text-slate-700"
            )}
            onClick={handleClick}
        >
            {children}
        </div>
    );
};

// Dialog Components
export const Dialog = ({ open, onOpenChange, children }: { open?: boolean; onOpenChange?: (open: boolean) => void; children: React.ReactNode }) => {
    if (!open) return null;
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="fixed inset-0 bg-black/50" onClick={() => onOpenChange?.(false)} />
            {children}
        </div>
    );
};

export const DialogContent = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={cn("relative z-50 grid w-full max-w-lg gap-4 border bg-white p-6 shadow-lg sm:rounded-lg", className)} {...props}>
        {children}
    </div>
);

export const DialogHeader = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)} {...props}>
        {children}
    </div>
);

export const DialogTitle = ({ className, children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 className={cn("text-lg font-semibold", className)} {...props}>
        {children}
    </h2>
);

export const DialogDescription = ({ className, children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className={cn("text-sm text-slate-500", className)} {...props}>
        {children}
    </p>
);

// Sheet Components (side drawer)
export const Sheet = ({ open, onOpenChange, children }: { open?: boolean; onOpenChange?: (open: boolean) => void; children: React.ReactNode }) => {
    if (!open) return null;
    return (
        <div className="fixed inset-0 z-50">
            <div className="fixed inset-0 bg-black/50" onClick={() => onOpenChange?.(false)} />
            {children}
        </div>
    );
};

export const SheetContent = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={cn("fixed right-0 top-0 h-full w-96 border-l bg-white p-6 shadow-lg", className)} {...props}>
        {children}
    </div>
);

export const SheetHeader = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={cn("flex flex-col space-y-2", className)} {...props}>
        {children}
    </div>
);

export const SheetTitle = ({ className, children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 className={cn("text-lg font-semibold", className)} {...props}>
        {children}
    </h2>
);

export const SheetDescription = ({ className, children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className={cn("text-sm text-slate-500", className)} {...props}>
        {children}
    </p>
);

// ScrollArea Component
export const ScrollArea = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={cn("overflow-auto", className)} {...props}>
        {children}
    </div>
);

// Separator Component
export const Separator = ({ className, orientation = "horizontal", ...props }: React.HTMLAttributes<HTMLDivElement> & { orientation?: "horizontal" | "vertical" }) => (
    <div
        className={cn(
            orientation === "horizontal" ? "h-px w-full" : "h-full w-px",
            "bg-slate-200",
            className
        )}
        {...props}
    />
);

// Tabs Components
export const Tabs = ({ value, onValueChange, children, className, ...props }: React.HTMLAttributes<HTMLDivElement> & { value?: string; onValueChange?: (value: string) => void }) => {
    return (
        <div className={cn("w-full", className)} {...props}>
            {React.Children.map(children, child =>
                React.isValidElement(child)
                    ? React.cloneElement(child as any, { currentValue: value, onValueChange })
                    : child
            )}
        </div>
    );
};

export const TabsList = ({ className, children, currentValue, onValueChange, ...props }: React.HTMLAttributes<HTMLDivElement> & { currentValue?: string; onValueChange?: (value: string) => void }) => (
    <div className={cn("inline-flex h-10 items-center justify-center rounded-md bg-slate-100 p-1", className)} {...props}>
        {React.Children.map(children, child =>
            React.isValidElement(child)
                ? React.cloneElement(child as any, { currentValue, onValueChange })
                : child
        )}
    </div>
);

export const TabsTrigger = ({ value, className, children, onValueChange, currentValue, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { value: string; onValueChange?: (value: string) => void; currentValue?: string }) => {
    const isActive = currentValue === value;
    return (
        <button
            type="button"
            onClick={() => onValueChange?.(value)}
            className={cn(
                "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium transition-all",
                isActive ? "bg-white text-slate-900 shadow-sm mb-accent-underline" : "text-slate-600 hover:text-slate-900",
                className
            )}
            {...props}
        >
            {children}
        </button>
    );
};

export const TabsContent = ({ value, className, children, currentValue, ...props }: React.HTMLAttributes<HTMLDivElement> & { value: string; currentValue?: string }) => {
    if (currentValue !== value) return null;
    return (
        <div className={cn("mt-2", className)} {...props}>
            {children}
        </div>
    );
};

// DialogFooter Component
export const DialogFooter = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
    <div className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)} {...props}>
        {children}
    </div>
);

// Textarea Component
export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
    ({ className, ...props }, ref) => (
        <textarea
            ref={ref}
            className={cn(
                "flex min-h-[80px] w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:cursor-not-allowed disabled:opacity-50",
                className
            )}
            {...props}
        />
    )
);
Textarea.displayName = "Textarea";

// Tooltip Components
type TooltipContextType = {
    open: boolean;
    setOpen: (open: boolean) => void;
    delayDuration: number;
};

const TooltipContext = React.createContext<TooltipContextType | null>(null);

export const TooltipProvider = ({ children, delayDuration = 200 }: { children: React.ReactNode; delayDuration?: number }) => {
    return <>{children}</>;
};

export const Tooltip = ({ children, delayDuration = 200 }: { children: React.ReactNode; delayDuration?: number }) => {
    const [open, setOpen] = React.useState(false);

    return (
        <TooltipContext.Provider value={{ open, setOpen, delayDuration }}>
            <div className="relative inline-block">
                {children}
            </div>
        </TooltipContext.Provider>
    );
};

export const TooltipTrigger = React.forwardRef<HTMLSpanElement, React.HTMLAttributes<HTMLSpanElement> & { asChild?: boolean }>(
    ({ asChild, children, ...props }, ref) => {
        const ctx = React.useContext(TooltipContext);
        const timeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

        const onMouseEnter = () => {
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
            timeoutRef.current = setTimeout(() => {
                ctx?.setOpen(true);
            }, ctx?.delayDuration ?? 200);
        };

        const onMouseLeave = () => {
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
            ctx?.setOpen(false);
        };

        if (asChild && React.isValidElement(children)) {
            return React.cloneElement(children as React.ReactElement<any>, {
                onMouseEnter,
                onMouseLeave,
                ref,
                ...props,
            });
        }

        return (
            <span ref={ref} onMouseEnter={onMouseEnter} onMouseLeave={onMouseLeave} {...props}>
                {children}
            </span>
        );
    }
);
TooltipTrigger.displayName = "TooltipTrigger";

export const TooltipContent = ({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) => {
    const ctx = React.useContext(TooltipContext);
    if (!ctx?.open) return null;

    return (
        <div
            className={cn(
                "absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5 text-xs bg-slate-900 text-white rounded-md shadow-md whitespace-nowrap",
                className
            )}
            {...props}
        >
            {children}
            <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-slate-900" />
        </div>
    );
};

