import React, { useState, useEffect, useCallback } from "react";
import { createRoot } from "react-dom/client";
import "../setup";
import ProfitAndLossReportPage, {
    PlPeriodPreset,
    PlComparePreset,
    PlKpiSummary,
    PlAccountRow,
    PlDiagnostics,
    ProfitAndLossReportProps,
} from "./ProfitAndLossReportPage";

// --- API Response Interface (snake_case from backend) ---

interface PlApiResponse {
    business_name: string;
    currency: string;
    period_preset: PlPeriodPreset;
    period_label: string;
    period_start: string;
    period_end: string;
    compare_preset: PlComparePreset;
    compare_label?: string | null;
    kpi: {
        income: number;
        cogs: number;
        gross_profit: number;
        expenses: number;
        net_income: number;
        gross_margin_pct: number | null;
        net_margin_pct: number | null;
        change_income_pct: number | null;
        change_cogs_pct: number | null;
        change_gross_profit_pct: number | null;
        change_expenses_pct: number | null;
        change_net_income_pct: number | null;
    };
    rows: {
        id: string | number;
        name: string;
        code?: string | null;
        group: "INCOME" | "COGS" | "EXPENSE";
        amount: number;
        compare_amount: number | null;
    }[];
    diagnostics: {
        has_activity: boolean;
        reasons: string[];
    };
}

// --- Helper: Map API response to component props ---

function mapApiToProps(data: PlApiResponse): Omit<ProfitAndLossReportProps, "onBack" | "onChangePeriod" | "onChangeCompare" | "onExportPdf" | "onExportCsv" | "onPrint" | "loading"> {
    return {
        businessName: data.business_name,
        currency: data.currency,
        periodPreset: data.period_preset,
        periodLabel: data.period_label,
        periodStart: data.period_start,
        periodEnd: data.period_end,
        comparePreset: data.compare_preset,
        compareLabel: data.compare_label ?? undefined,
        kpi: {
            income: data.kpi.income,
            cogs: data.kpi.cogs,
            grossProfit: data.kpi.gross_profit,
            expenses: data.kpi.expenses,
            netIncome: data.kpi.net_income,
            grossMarginPct: data.kpi.gross_margin_pct,
            netMarginPct: data.kpi.net_margin_pct,
            changeIncomePct: data.kpi.change_income_pct,
            changeCogsPct: data.kpi.change_cogs_pct,
            changeGrossProfitPct: data.kpi.change_gross_profit_pct,
            changeExpensesPct: data.kpi.change_expenses_pct,
            changeNetIncomePct: data.kpi.change_net_income_pct,
        },
        rows: data.rows.map((row) => ({
            id: String(row.id),
            name: row.name,
            code: row.code ?? undefined,
            group: row.group,
            amount: row.amount,
            compareAmount: row.compare_amount,
        })),
        diagnostics: {
            hasActivity: data.diagnostics.has_activity,
            reasons: data.diagnostics.reasons,
        },
    };
}

// --- Main Entry Component ---

interface PlReportAppProps {
    rootElement: HTMLElement;
}

function PlReportApp({ rootElement }: PlReportAppProps) {
    const defaultPeriod = (rootElement.dataset.defaultPeriod as PlPeriodPreset) || "this_month";
    const defaultCompare = (rootElement.dataset.defaultCompare as PlComparePreset) || "previous_period";

    const [periodPreset, setPeriodPreset] = useState<PlPeriodPreset>(defaultPeriod);
    const [comparePreset, setComparePreset] = useState<PlComparePreset>(defaultCompare);
    const [loading, setLoading] = useState(true);
    const [data, setData] = useState<PlApiResponse | null>(null);
    const [error, setError] = useState<string | null>(null);

    const fetchData = useCallback(async () => {
        setLoading(true);
        setError(null);

        try {
            const params = new URLSearchParams({
                period_preset: periodPreset,
                compare_preset: comparePreset,
            });

            const res = await fetch(`/api/reports/pl/?${params.toString()}`, {
                headers: {
                    Accept: "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                },
                credentials: "include",
            });

            if (!res.ok) {
                throw new Error(`Failed to fetch P&L data: ${res.status} ${res.statusText}`);
            }

            const json: PlApiResponse = await res.json();
            setData(json);
        } catch (err) {
            console.error("Error fetching P&L data:", err);
            setError(err instanceof Error ? err.message : "Unknown error");
        } finally {
            setLoading(false);
        }
    }, [periodPreset, comparePreset]);

    useEffect(() => {
        fetchData();
    }, [fetchData]);

    const handleChangePeriod = useCallback((period: PlPeriodPreset, custom?: { start: string; end: string }) => {
        setPeriodPreset(period);
        // If custom period support is needed, we'd store start/end dates in state too
    }, []);

    const handleChangeCompare = useCallback((compare: PlComparePreset) => {
        setComparePreset(compare);
    }, []);

    const handleBack = useCallback(() => {
        window.history.back();
    }, []);

    const buildQuery = useCallback(() => {
        return new URLSearchParams({
            period_preset: periodPreset,
            compare_preset: comparePreset,
        }).toString();
    }, [comparePreset, periodPreset]);

    const handleExportPdf = useCallback(() => {
        window.open(`/reports/pl/print/?${buildQuery()}`, "_blank");
    }, [buildQuery]);

    const handleExportCsv = useCallback(() => {
        window.open(`/reports/pl-export/?${buildQuery()}`, "_blank");
    }, [buildQuery]);

    const handlePrint = useCallback(() => {
        window.print();
    }, []);

    // Show error state
    if (error && !data) {
        return (
            <div className="min-h-screen bg-slate-100/50 flex items-center justify-center">
                <div className="bg-white p-8 rounded-2xl shadow-lg text-center max-w-md">
                    <div className="text-rose-500 text-5xl mb-4">⚠️</div>
                    <h2 className="text-xl font-semibold text-slate-900 mb-2">Failed to Load Report</h2>
                    <p className="text-slate-600 mb-4">{error}</p>
                    <button
                        onClick={fetchData}
                        className="px-4 py-2 bg-indigo-600 text-white rounded-lg font-medium hover:bg-indigo-700 transition-colors"
                    >
                        Retry
                    </button>
                </div>
            </div>
        );
    }

    // Default empty state while loading
    const defaultKpi: PlKpiSummary = {
        income: 0,
        cogs: 0,
        grossProfit: 0,
        expenses: 0,
        netIncome: 0,
        grossMarginPct: null,
        netMarginPct: null,
    };

    const defaultDiagnostics: PlDiagnostics = {
        hasActivity: false,
        reasons: [],
    };

    const props: ProfitAndLossReportProps = data
        ? {
            ...mapApiToProps(data),
            loading,
            onBack: handleBack,
            onChangePeriod: handleChangePeriod,
            onChangeCompare: handleChangeCompare,
            onExportPdf: handleExportPdf,
            onExportCsv: handleExportCsv,
            onPrint: handlePrint,
        }
        : {
            businessName: rootElement.dataset.businessName || "Loading...",
            currency: "USD",
            periodPreset,
            periodLabel: "Loading...",
            periodStart: "",
            periodEnd: "",
            comparePreset,
            loading: true,
            kpi: defaultKpi,
            rows: [],
            diagnostics: defaultDiagnostics,
            onBack: handleBack,
            onChangePeriod: handleChangePeriod,
            onChangeCompare: handleChangeCompare,
            onExportPdf: handleExportPdf,
            onExportCsv: handleExportCsv,
            onPrint: handlePrint,
        };

    return <ProfitAndLossReportPage {...props} />;
}

// --- Mount the app ---

const el = document.getElementById("pl-report-root");
if (el) {
    const root = createRoot(el);
    root.render(<PlReportApp rootElement={el} />);
}

export default PlReportApp;
