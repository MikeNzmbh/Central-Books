import React, { useEffect, useMemo, useRef, useState } from "react";
import {
    BarChart3,
    Boxes,
    ChevronDown,
    ChevronLeft,
    ChevronRight,
    CreditCard,
    FileText,
    LifeBuoy,
    LogOut,
    Package,
    Plus,
    Receipt,
    Search,
    Settings,
    Sparkles,
    Users,
    Wallet,
    Landmark,
    Scale,
    FolderOpen,
    Bot,
} from "lucide-react";
import {
    AnimatePresence,
    LayoutGroup,
    motion,
    useReducedMotion,
} from "framer-motion";
import { useAuth } from "../contexts/AuthContext";

// -----------------------------------------------------------------------------
// Clover Sidebar v2.4 — GREY / SILVER edition
// - Grey gradient accents only
// - Nearly-invisible binary numbers in the background
// - Calm, usable animations
// - Silver orb
// -----------------------------------------------------------------------------

function cn(...classes: Array<string | false | null | undefined>) {
    return classes.filter(Boolean).join(" ");
}

type QuickAction = {
    id: string;
    label: string;
    icon: React.ComponentType<any>;
    hint?: string;
    href?: string;
};

type NavItem = {
    id: string;
    label: string;
    icon: React.ComponentType<any>;
    badge?: number;
    hint?: string;
    href: string;
};

type NavGroup = {
    id: string;
    label: string;
    items: NavItem[];
    defaultOpen?: boolean;
};

export type CloverSidebarProps = {
    current?: string;
    onNavigate?: (id: string) => void;
    user?: { name: string; email: string };
    brand?: { name: string; subtitle?: string };
};

// Silver / grayscale orb
const ORB_GRADIENT =
    "radial-gradient(55% 55% at 30% 30%, rgba(255,255,255,.95) 0%, rgba(255,255,255,.58) 18%, rgba(148,163,184,.60) 44%, rgba(30,41,59,.22) 72%, rgba(15,23,42,0) 100%)";

function Tooltip({ label, show }: { label: string; show: boolean }) {
    return (
        <AnimatePresence>
            {show ? (
                <motion.div
                    initial={{ opacity: 0, y: 6, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 6, scale: 0.98 }}
                    transition={{ duration: 0.14 }}
                    className="pointer-events-none absolute left-full top-1/2 z-50 ml-3 -translate-y-1/2"
                >
                    <div className="rounded-xl border border-slate-200/70 bg-white/92 px-3 py-2 text-xs font-medium text-slate-800 shadow-[0_18px_40px_rgba(2,6,23,.10)] backdrop-blur-xl">
                        {label}
                    </div>
                </motion.div>
            ) : null}
        </AnimatePresence>
    );
}

function useClickOutside(ref: React.RefObject<HTMLElement | null>, onOutside: () => void) {
    useEffect(() => {
        const onDown = (e: MouseEvent) => {
            if (!ref.current) return;
            if (!ref.current.contains(e.target as Node)) onOutside();
        };
        window.addEventListener("mousedown", onDown);
        return () => window.removeEventListener("mousedown", onDown);
    }, [ref, onOutside]);
}

function BinaryMist({ reduceMotion }: { reduceMotion: boolean }) {
    const lines = useMemo(
        () => [
            "01001001 01001110 01010110 00110001",
            "00110000 00110001 00110000 00110000 00110001",
            "01100011 01101100 01101111 01110110 01100101 01110010",
            "00110001 00110000 00110001 00110000 00110001 00110000",
            "01000100 01000001 01010100 01000001",
            "01010011 01011001 01001110 01000011",
        ],
        []
    );

    return (
        <div className="absolute inset-0">
            {lines.map((t, i) => (
                <motion.div
                    key={i}
                    className="absolute select-none font-mono text-[10px] tracking-[0.34em] text-slate-700/30"
                    style={{
                        left: `${10 + (i % 3) * 28}%`,
                        top: `${12 + Math.floor(i / 3) * 44}%`,
                        opacity: 0.12,
                    }}
                    animate={
                        reduceMotion
                            ? undefined
                            : {
                                y: [0, -10, 0],
                                opacity: [0.10, 0.14, 0.10],
                            }
                    }
                    transition={
                        reduceMotion
                            ? undefined
                            : { duration: 7.2 + i * 0.6, repeat: Infinity, ease: "easeInOut" }
                    }
                >
                    {t}
                </motion.div>
            ))}

            <div
                className="absolute inset-0 opacity-[0.10]"
                style={{
                    backgroundImage:
                        "repeating-linear-gradient(135deg, rgba(2,6,23,.06) 0px, rgba(2,6,23,.06) 1px, transparent 1px, transparent 14px)",
                }}
            />
        </div>
    );
}

export function CloverSidebar({
    current,
    onNavigate,
    user = { name: "User", email: "user@domain.com" },
    brand = { name: "CLOVER", subtitle: "CLOVER Books" },
}: CloverSidebarProps) {
    const reduceMotion = useReducedMotion();
    const { logout } = useAuth();

    const [collapsed, setCollapsed] = useState(false);
    const [query, setQuery] = useState("");
    const [hovered, setHovered] = useState<string | null>(null);
    const [actionsOpen, setActionsOpen] = useState(false);

    const searchRef = useRef<HTMLInputElement | null>(null);
    const actionsRef = useRef<HTMLDivElement | null>(null);
    useClickOutside(actionsRef, () => setActionsOpen(false));

    // Derive current from pathname
    const currentPath = typeof window !== "undefined" ? window.location.pathname : "";

    // Shortcuts
    useEffect(() => {
        const onKeyDown = (e: KeyboardEvent) => {
            const isMac = /(Mac|iPhone|iPod|iPad)/i.test(navigator.platform);
            const mod = isMac ? e.metaKey : e.ctrlKey;

            if (mod && e.key.toLowerCase() === "b") {
                e.preventDefault();
                setCollapsed((v) => !v);
            }
            if (mod && e.key.toLowerCase() === "k") {
                e.preventDefault();
                setCollapsed(false);
                setTimeout(() => searchRef.current?.focus(), 60);
            }
            if (e.key === "Escape") {
                setActionsOpen(false);
            }
        };

        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, []);

    const quickActions: QuickAction[] = useMemo(
        () => [
            { id: "new_invoice", label: "New invoice", icon: FileText, hint: "Create & send", href: "/invoices/new/" },
            { id: "new_expense", label: "New expense", icon: CreditCard, hint: "Log spend", href: "/expenses/new/" },
            { id: "new_customer", label: "New customer", icon: Users, hint: "Add contact", href: "/customers/new/" },
            { id: "new_supplier", label: "New supplier", icon: Wallet, hint: "Add vendor", href: "/suppliers/new/" },
        ],
        []
    );

    const groups: NavGroup[] = useMemo(
        () => [
            {
                id: "main",
                label: "MAIN",
                defaultOpen: true,
                items: [
                    { id: "dashboard", label: "Dashboard", icon: BarChart3, hint: "Overview & alerts", href: "/dashboard/" },
                ],
            },
            {
                id: "sales",
                label: "SALES",
                defaultOpen: true,
                items: [
                    { id: "customers", label: "Customers", icon: Users, href: "/customers/" },
                    { id: "products", label: "Products & Services", icon: Boxes, href: "/products/" },
                    { id: "inventory", label: "Inventory", icon: Package, href: "/inventory/" },
                    { id: "invoices", label: "Invoices", icon: FileText, href: "/invoices/" },
                ],
            },
            {
                id: "expenses",
                label: "EXPENSES",
                defaultOpen: true,
                items: [
                    { id: "suppliers", label: "Suppliers", icon: Wallet, href: "/suppliers/" },
                    { id: "expenses_list", label: "Expenses", icon: CreditCard, href: "/expenses/" },
                    { id: "receipts", label: "Receipts", icon: Receipt, hint: "Upload & match", href: "/receipts/" },
                    { id: "companion", label: "AI Companion", icon: Bot, hint: "Health pulse", href: "/ai-companion/" },
                    { id: "categories", label: "Categories", icon: FolderOpen, href: "/categories/" },
                ],
            },
            {
                id: "banking",
                label: "BANKING",
                defaultOpen: true,
                items: [
                    { id: "banking", label: "Banking", icon: Landmark, href: "/banking/" },
                    { id: "reconciliation", label: "Reconciliation", icon: Scale, href: "/reconciliation/" },
                ],
            },
            {
                id: "reports",
                label: "REPORTS",
                defaultOpen: true,
                items: [
                    { id: "pl_report", label: "Profit & Loss", icon: FileText, href: "/reports/pl-shadow/" },
                    { id: "cashflow_report", label: "Cashflow", icon: BarChart3, href: "/reports/cashflow/" },
                    { id: "tax_guardian", label: "Tax Guardian", icon: Sparkles, href: "/ai-companion/tax" },
                    { id: "chart_of_accounts", label: "Chart of Accounts", icon: FolderOpen, href: "/accounts/" },
                ],
            },
            {
                id: "system",
                label: "ACCOUNT",
                defaultOpen: false,
                items: [
                    { id: "settings", label: "Account settings", icon: Settings, href: "/settings/account/" },
                    { id: "help", label: "Help", icon: LifeBuoy, href: "/help/" },
                ],
            },
        ],
        []
    );

    const filteredGroups = useMemo(() => {
        const q = query.trim().toLowerCase();
        if (!q) return groups;
        return groups
            .map((g) => ({
                ...g,
                items: g.items.filter((it) => it.label.toLowerCase().includes(q)),
            }))
            .filter((g) => g.items.length > 0);
    }, [groups, query]);

    const handleNavigate = (href: string) => {
        window.location.href = href;
    };

    const handleLogout = () => {
        logout();
    };

    return (
        <LayoutGroup>
            <motion.aside
                aria-label="Primary"
                animate={{ width: collapsed ? 92 : 300 }}
                transition={{ type: "spring", stiffness: 320, damping: 30 }}
                className={cn(
                    "sticky top-0 h-screen shrink-0 overflow-hidden",
                    "border-r border-slate-200 bg-white"
                )}
            >
                {/* background: binary mist only */}
                <div className="pointer-events-none absolute inset-0">
                    <BinaryMist reduceMotion={!!reduceMotion} />
                </div>

                {/* left rail line */}
                <div className="pointer-events-none absolute left-0 top-0 h-full w-[2px]">
                    <div className="absolute inset-y-0 left-0 w-[1px] bg-slate-100" />
                </div>

                <div className="relative flex h-full flex-col">
                    {/* Header */}
                    <div className={cn("px-5 pt-5", collapsed ? "pb-3" : "pb-4")}>
                        <div className="flex items-center gap-3">
                            <a href="/dashboard/" className="no-underline">
                                <img
                                    src="/static/branding/clover-logo-dark-bg.png"
                                    alt="Clover"
                                    className="h-12 w-12 rounded-2xl object-cover"
                                />
                            </a>

                            <AnimatePresence initial={false}>
                                {!collapsed ? (
                                    <motion.div
                                        initial={{ opacity: 0, x: -8 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        exit={{ opacity: 0, x: -8 }}
                                        transition={{ duration: 0.1 }}
                                        className="min-w-0"
                                    >
                                        <div className="text-sm font-bold tracking-wide text-slate-900">
                                            {brand.name}
                                        </div>
                                        <div className="-mt-0.5 text-[11px] font-medium text-slate-500">
                                            {brand.subtitle}
                                        </div>
                                    </motion.div>
                                ) : null}
                            </AnimatePresence>

                            <div className="ml-auto flex items-center gap-2">
                                <button
                                    onClick={() => setCollapsed((v) => !v)}
                                    className={cn(
                                        "grid h-9 w-9 place-items-center rounded-2xl",
                                        "border border-slate-200/70 bg-white/70 text-slate-700",
                                        "shadow-sm hover:bg-white focus:outline-none focus:ring-2 focus:ring-slate-300"
                                    )}
                                    aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                                    title={collapsed ? "Expand (⌘/Ctrl+B)" : "Collapse (⌘/Ctrl+B)"}
                                >
                                    {collapsed ? (
                                        <ChevronRight className="h-4 w-4" />
                                    ) : (
                                        <ChevronLeft className="h-4 w-4" />
                                    )}
                                </button>
                            </div>
                        </div>

                        {/* Search */}
                        <div className={cn("mt-3", collapsed ? "hidden" : "block")}>
                            <div className="relative">
                                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                                <input
                                    ref={searchRef}
                                    value={query}
                                    onChange={(e) => setQuery(e.target.value)}
                                    placeholder="Search…  (⌘/Ctrl+K)"
                                    className={cn(
                                        "w-full rounded-2xl border border-slate-200/70 bg-white/70",
                                        "py-2.5 pl-9 pr-3 text-sm text-slate-800 placeholder:text-slate-400",
                                        "focus:outline-none focus:ring-2 focus:ring-slate-300"
                                    )}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Nav */}
                    <nav className="relative flex-1 overflow-y-auto px-4 pb-4 [scrollbar-width:none]">
                        <style>{"nav::-webkit-scrollbar{display:none}"}</style>
                        <div className="space-y-6">
                            {filteredGroups.map((group) => (
                                <NavGroupBlock
                                    key={group.id}
                                    group={group}
                                    collapsed={collapsed}
                                    currentPath={currentPath}
                                    hovered={hovered}
                                    onHover={setHovered}
                                    onSelect={handleNavigate}
                                    reduceMotion={!!reduceMotion}
                                />
                            ))}
                        </div>
                    </nav>

                    {/* Footer */}
                    <div className="relative border-t border-slate-200/70 p-4">
                        <div className={cn("flex items-center gap-4", collapsed ? "justify-center" : "")}>
                            <div className="relative grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-slate-950 text-white">
                                <span className="text-xs font-semibold">
                                    {(user.name || "U")
                                        .split(" ")
                                        .slice(0, 2)
                                        .map((p) => p[0])
                                        .join("")}
                                </span>
                            </div>

                            <AnimatePresence initial={false}>
                                {!collapsed ? (
                                    <motion.div
                                        initial={{ opacity: 0, x: -8 }}
                                        animate={{ opacity: 1, x: 0 }}
                                        exit={{ opacity: 0, x: -8 }}
                                        transition={{ duration: 0.16 }}
                                        className="min-w-0 flex-1"
                                    >
                                        <div className="truncate text-sm font-semibold">{user.name}</div>
                                        <div className="truncate text-xs text-slate-400">{user.email}</div>
                                    </motion.div>
                                ) : null}
                            </AnimatePresence>

                            <motion.button
                                whileHover={reduceMotion ? undefined : { y: -1 }}
                                whileTap={{ scale: 0.98 }}
                                className={cn(
                                    "grid place-items-center rounded-2xl",
                                    "border border-slate-200/70 bg-white/70 text-slate-700",
                                    "hover:bg-white focus:outline-none focus:ring-2 focus:ring-slate-300",
                                    collapsed ? "h-11 w-11" : "h-9 w-9"
                                )}
                                onClick={handleLogout}
                                aria-label="Logout"
                                title="Logout"
                            >
                                <LogOut className="h-4 w-4" />
                            </motion.button>
                        </div>
                    </div>
                </div>
            </motion.aside>
        </LayoutGroup>
    );
}

function NavGroupBlock({
    group,
    collapsed,
    currentPath,
    hovered,
    onHover,
    onSelect,
    reduceMotion,
}: {
    group: NavGroup;
    collapsed: boolean;
    currentPath: string;
    hovered: string | null;
    onHover: (id: string | null) => void;
    onSelect: (href: string) => void;
    reduceMotion: boolean;
}) {
    const [open, setOpen] = useState(group.defaultOpen ?? true);
    const isOpen = collapsed ? true : open;

    return (
        <div>
            <div className={cn("mb-3 flex items-center", collapsed ? "justify-center" : "justify-between")}>
                {!collapsed ? (
                    <div className="px-2 text-[11px] font-semibold tracking-[0.28em] text-slate-400">
                        {group.label}
                    </div>
                ) : (
                    <div className="h-6" />
                )}

                {!collapsed ? (
                    <button
                        onClick={() => setOpen((v) => !v)}
                        className={cn(
                            "grid h-7 w-7 place-items-center rounded-xl",
                            "text-slate-400 hover:text-slate-700",
                            "hover:bg-white/70 focus:outline-none focus:ring-2 focus:ring-slate-300"
                        )}
                        aria-label={open ? `Collapse ${group.label}` : `Expand ${group.label}`}
                        aria-expanded={open}
                    >
                        <motion.span
                            animate={{ rotate: open ? 0 : -90 }}
                            transition={{ duration: 0.18 }}
                            className="inline-flex"
                        >
                            <ChevronDown className="h-4 w-4" />
                        </motion.span>
                    </button>
                ) : null}
            </div>

            <AnimatePresence initial={false}>
                {isOpen ? (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.18 }}
                        className="space-y-1.5 overflow-hidden"
                    >
                        {group.items.map((item) => (
                            <NavItemRow
                                key={item.id}
                                item={item}
                                collapsed={collapsed}
                                active={currentPath.startsWith(item.href.replace(/\/$/, ""))}
                                hovered={hovered === item.id}
                                onHover={onHover}
                                onSelect={onSelect}
                                reduceMotion={reduceMotion}
                            />
                        ))}
                    </motion.div>
                ) : null}
            </AnimatePresence>
        </div>
    );
}

function NavItemRow({
    item,
    collapsed,
    active,
    hovered,
    onHover,
    onSelect,
    reduceMotion,
}: {
    item: NavItem;
    collapsed: boolean;
    active: boolean;
    hovered: boolean;
    onHover: (id: string | null) => void;
    onSelect: (href: string) => void;
    reduceMotion: boolean;
}) {
    const Icon = item.icon;

    return (
        <div
            className="relative"
            onMouseEnter={() => onHover(item.id)}
            onMouseLeave={() => onHover(null)}
        >
            <a
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                    "group relative flex w-full items-center gap-4 rounded-2xl px-3 py-3 no-underline",
                    "focus:outline-none focus:ring-2 focus:ring-slate-300",
                    active
                        ? "text-slate-900"
                        : "text-slate-700 hover:bg-slate-50 hover:text-slate-900"
                )}
            >
                {/* active pill - static, no animation */}
                {active ? (
                    <span
                        className="absolute inset-0 rounded-2xl border border-slate-200 bg-slate-50"
                    />
                ) : null}


                {/* icon */}
                <span
                    className={cn(
                        "relative grid h-10 w-10 shrink-0 place-items-center rounded-2xl",
                        active
                            ? "bg-slate-950 text-white"
                            : "bg-white/70 text-slate-700 border border-slate-200/70 group-hover:bg-white"
                    )}
                >
                    <motion.span
                        animate={reduceMotion ? undefined : { rotate: hovered ? 1.6 : 0 }}
                        transition={{ duration: 0.16 }}
                        className="inline-flex"
                    >
                        <Icon className="h-[18px] w-[18px]" />
                    </motion.span>

                    {typeof item.badge === "number" && item.badge > 0 ? (
                        <span className="absolute -right-0.5 -top-0.5 grid h-5 min-w-[20px] place-items-center rounded-full bg-slate-950 px-1 text-[10px] font-semibold text-white shadow-sm">
                            {item.badge}
                        </span>
                    ) : null}
                </span>

                {/* label */}
                <AnimatePresence initial={false}>
                    {!collapsed ? (
                        <motion.div
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -8 }}
                            transition={{ duration: 0.08 }}
                            className="relative min-w-0 flex-1"
                        >
                            <div className="truncate text-sm font-semibold">{item.label}</div>
                            {item.hint ? (
                                <div className="truncate text-xs text-slate-400">{item.hint}</div>
                            ) : null}
                        </motion.div>
                    ) : null}
                </AnimatePresence>

                {!collapsed ? (
                    <span className="relative ml-auto inline-flex items-center gap-2 text-xs text-slate-400 opacity-0 transition-opacity group-hover:opacity-100">
                        <Sparkles className="h-3.5 w-3.5" />
                    </span>
                ) : null}

                {/* hover highlight (grey only) */}
                <span
                    className={cn(
                        "pointer-events-none absolute inset-0 rounded-2xl opacity-0 transition-opacity",
                        hovered && !active ? "opacity-100" : "opacity-0"
                    )}
                >
                    <span className="absolute inset-0 rounded-2xl bg-[radial-gradient(circle_at_25%_20%,rgba(148,163,184,.16),transparent_58%)]" />
                </span>
            </a>

            <Tooltip label={item.label} show={collapsed && hovered} />
        </div>
    );
}

export default CloverSidebar;
