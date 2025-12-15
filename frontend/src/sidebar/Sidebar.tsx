import React, { useState, useEffect, useRef } from "react";
import { Plus, ChevronDown } from "lucide-react";
import { useAuth } from "../contexts/AuthContext";

interface SidebarProps {
    businessName?: string;
    businessInitials?: string;
    userName?: string;
    userEmail?: string;
    activeRoute?: string;
}

interface NavItemProps {
    href: string;
    active?: boolean;
    children: React.ReactNode;
}

interface SidebarSectionProps {
    label: string;
    children: React.ReactNode;
}

const Sidebar: React.FC<SidebarProps> = ({
    businessName = "Your business",
    businessInitials = "CB",
    userName = "User",
    userEmail = "",
    activeRoute = "",
}) => {
    const { logout } = useAuth();
    const currentPath = typeof window !== "undefined" ? window.location.pathname : "";

    return (
        <aside className="sticky top-0 flex h-screen w-[280px] flex-col border-r border-slate-200 bg-slate-50/80 px-6 pt-6 pb-4">
            {/* Brand */}
            <a href="/dashboard/" className="flex items-center gap-3 pb-4 border-b border-slate-100 no-underline">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-900 p-1.5 overflow-hidden shadow-md shadow-slate-900/25">
                    <img
                        src="/branding/clover-logo-dark-bg.png"
                        alt="Clover"
                        className="h-7 w-7 object-contain"
                    />
                </div>
                <div className="flex flex-col leading-tight">
                    <span className="text-sm font-semibold tracking-[0.08em] text-slate-900 uppercase" style={{ fontFamily: "'Museo Moderno', system-ui, sans-serif" }}>Clover</span>
                    <span className="text-[11px] font-medium text-slate-400">
                        {businessName}
                    </span>
                </div>
            </a>

            {/* NEW pill button */}
            <div className="pb-6">
                <NewMenuButton />
            </div>

            {/* Navigation */}
            <nav className="flex-1 space-y-6 overflow-y-auto pb-4 pr-1 text-sm scrollbar-thin scrollbar-thumb-slate-200">
                <SidebarSection label="Main">
                    <NavItem href="/dashboard/" active={activeRoute === "dashboard"}>
                        Dashboard
                    </NavItem>
                </SidebarSection>

                <SidebarSection label="Sales">
                    <NavItem href="/customers/" active={activeRoute === "customer_list"}>
                        Customers
                    </NavItem>
                    <NavItem
                        href="/products/"
                        active={
                            activeRoute === "product_list" ||
                            activeRoute === "item_create" ||
                            activeRoute === "item_update"
                        }
                    >
                        Products & Services
                    </NavItem>
                    <NavItem href="/invoices/" active={activeRoute === "invoice_list"}>
                        Invoices
                    </NavItem>
                </SidebarSection>

                <SidebarSection label="Expenses">
                    <NavItem href="/suppliers/" active={activeRoute === "suppliers"}>
                        Suppliers
                    </NavItem>
                    <NavItem href="/expenses/" active={activeRoute === "expense_list"}>
                        Expenses
                    </NavItem>
                    <NavItem href="/receipts/" active={activeRoute === "receipts_page"}>
                        Receipts
                    </NavItem>
                    <NavItem
                        href="/ai-companion/"
                        active={
                            activeRoute === "companion_overview_page" ||
                            activeRoute === "invoices_ai_page" ||
                            activeRoute === "books_review_page" ||
                            activeRoute === "bank_review_page"
                        }
                    >
                        AI Companion
                    </NavItem>
                    <NavItem href="/categories/" active={activeRoute === "category_list"}>
                        Categories
                    </NavItem>
                </SidebarSection>

                <SidebarSection label="Banking">
                    <NavItem
                        href="/banking/"
                        active={
                            activeRoute === "banking_accounts_feed" ||
                            activeRoute === "bank_account_list" ||
                            activeRoute === "bank_feeds_overview" ||
                            activeRoute === "bank_feed_review" ||
                            activeRoute === "bank_account_create" ||
                            activeRoute === "bank_account_edit" ||
                            activeRoute === "bank_import" ||
                            activeRoute === "bank_feed_spa"
                        }
                    >
                        Banking
                    </NavItem>
                    <NavItem href="/reconciliation/" active={activeRoute === "reconciliation_entry"}>
                        Reconciliation
                    </NavItem>
                </SidebarSection>

                <SidebarSection label="Reports">
                    <NavItem href="/reports/pl-shadow/" active={activeRoute === "report_pnl" || activeRoute === "pl_shadow"}>
                        Profit & Loss
                    </NavItem>
                    <NavItem href="/reports/cashflow/" active={activeRoute === "cashflow_report"}>
                        Cashflow
                    </NavItem>
                    <NavItem
                        href="/ai-companion/tax"
                        active={activeRoute === "companion_overview_page" && currentPath.startsWith("/ai-companion/tax")}
                    >
                        Tax Guardian
                    </NavItem>
                    <NavItem href="/accounts/" active={activeRoute === "account_list"}>
                        Chart of Accounts
                    </NavItem>
                </SidebarSection>

                <SidebarSection label="Account">
                    <NavItem href="/account/settings/" active={activeRoute === "account_settings"}>
                        Account settings
                    </NavItem>
                </SidebarSection>
            </nav>

            {/* User footer */}
            <footer className="mt-4 border-t border-slate-200 pt-4">
                <div className="flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">
                        {userName.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex flex-col leading-tight flex-1 min-w-0">
                        <span className="text-sm font-medium text-slate-900 truncate">{userName}</span>
                        <span className="text-[11px] text-slate-400 truncate">{userEmail}</span>
                    </div>
                </div>
                <button
                    onClick={logout}
                    className="mt-3 w-full rounded-2xl border border-slate-200 bg-white/90 px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 hover:text-slate-900"
                >
                    Logout
                </button>
            </footer>
        </aside>
    );
};

const NewMenuButton: React.FC = () => {
    const [isOpen, setIsOpen] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        const handleEscape = (event: KeyboardEvent) => {
            if (event.key === "Escape") {
                setIsOpen(false);
            }
        };

        if (isOpen) {
            document.addEventListener("mousedown", handleClickOutside);
            document.addEventListener("keydown", handleEscape);
        }

        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
            document.removeEventListener("keydown", handleEscape);
        };
    }, [isOpen]);

    return (
        <div className="relative" ref={menuRef}>
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className="group relative flex w-full items-center justify-between gap-3 rounded-3xl border border-white/80 bg-white/95 px-4 py-2.5 text-sm font-medium text-slate-900 shadow-[0_10px_30px_-18px_rgba(15,23,42,0.65)] outline-none transition-all duration-200 hover:-translate-y-[1px] hover:bg-white hover:shadow-[0_18px_40px_-22px_rgba(15,23,42,0.85)] focus-visible:ring-2 focus-visible:ring-sky-200/80"
            >
                {/* Left: icon bubble */}
                <div className="flex items-center gap-2">
                    <div className="relative flex h-7 w-7 items-center justify-center rounded-full bg-slate-900/90 text-white shadow-sm shadow-slate-900/40">
                        <Plus className="h-3.5 w-3.5" />
                        {/* subtle inner highlight */}
                        <span className="pointer-events-none absolute inset-[1px] rounded-full bg-gradient-to-b from-white/18 to-transparent" />
                    </div>
                    <span className="text-sm font-semibold tracking-tight">New</span>
                </div>

                {/* Right: caret with micro animation */}
                <div className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400">
                    <span className="hidden sm:inline">Quick create</span>
                    <ChevronDown className="h-3 w-3 text-slate-500 transition-transform duration-200 group-hover:translate-y-[1px]" />
                </div>

                {/* Soft glow ring */}
                <span className="pointer-events-none absolute inset-0 rounded-3xl bg-gradient-to-b from-white/40 via-transparent to-slate-200/40 opacity-0 blur-[1px] transition-opacity duration-200 group-hover:opacity-100" />
            </button>

            {/* Dropdown Menu */}
            {isOpen && (
                <div className="absolute left-0 right-0 top-full mt-2 rounded-2xl bg-white border border-slate-200 shadow-lg py-2 z-50">
                    <a
                        href="/invoices/new/"
                        className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition"
                    >
                        Invoice
                    </a>
                    <a
                        href="/expenses/new/"
                        className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition"
                    >
                        Expense
                    </a>
                    <div className="border-t border-slate-100 my-1" />
                    <a
                        href="/customers/new/"
                        className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition"
                    >
                        Customer
                    </a>
                    <a
                        href="/suppliers/new/"
                        className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 transition"
                    >
                        Supplier
                    </a>
                </div>
            )}
        </div>
    );
};

const SidebarSection: React.FC<SidebarSectionProps> = ({ label, children }) => (
    <section>
        <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
            {label}
        </p>
        <div className="space-y-1">{children}</div>
    </section>
);

const NavItem: React.FC<NavItemProps> = ({ active, children, href }) => {
    if (active) {
        return (
            <a
                href={href}
                className="flex w-full items-center justify-between rounded-2xl bg-slate-900 text-[13px] font-medium text-white shadow-sm shadow-slate-900/40 transition-colors no-underline"
            >
                <span className="flex-1 px-3 py-2.5 text-left">{children}</span>
                <span className="pr-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-300">
                    Active
                </span>
            </a>
        );
    }

    return (
        <a
            href={href}
            className="flex w-full items-center rounded-2xl px-3 py-2.5 text-left text-[13px] font-medium text-slate-600 transition-colors hover:bg-white hover:text-slate-900 no-underline"
        >
            {children}
        </a>
    );
};

export default Sidebar;
