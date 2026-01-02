import type {
  CashflowReportProps,
  CashflowPeriodPoint,
  CashDriver,
  CashflowActivityBreakdown,
} from "./CashflowReportPage";
import type { ProfitAndLossReportProps, PlAccountRow } from "./ProfitAndLossReportPage";

const cashflowTrend: CashflowPeriodPoint[] = [
  { periodLabel: "Sep", inflows: 42000, outflows: 31500, net: 10500 },
  { periodLabel: "Oct", inflows: 51000, outflows: 35200, net: 15800 },
  { periodLabel: "Nov", inflows: 47000, outflows: 33250, net: 13750 },
  { periodLabel: "Dec", inflows: 56000, outflows: 39500, net: 16500 },
  { periodLabel: "Jan", inflows: 61000, outflows: 44800, net: 16200 },
];

const cashflowDrivers: CashDriver[] = [
  { id: "inv", label: "Invoice collections", amount: 48200, type: "inflow" },
  { id: "subs", label: "Subscriptions", amount: 18600, type: "inflow" },
  { id: "rent", label: "Workspace rent", amount: 12400, type: "outflow" },
  { id: "payroll", label: "Payroll", amount: 28600, type: "outflow" },
  { id: "tax", label: "Quarterly tax", amount: 8800, type: "outflow" },
];

const cashflowActivities: CashflowActivityBreakdown = {
  operating: 92500,
  investing: -12800,
  financing: -18250,
};

export const cashflowSample: CashflowReportProps = {
  username: "Demo User",
  asOfLabel: "As of Jan 31, 2025",
  baseCurrency: "USD",
  period: { preset: "last_30_days", label: "Last 30 days" },
  comparison: { label: "Prev 30 days", compare_to: "previous_period" },
  summary: {
    netChange: 16200,
    totalInflows: 61000,
    totalOutflows: 44800,
    runwayLabel: "6.2 months",
  },
  trend: cashflowTrend,
  activities: cashflowActivities,
  topDrivers: cashflowDrivers,
  bankingUrl: "/banking",
  invoicesUrl: "/invoices",
  expensesUrl: "/expenses",
};

const plRows: PlAccountRow[] = [
  { id: "rev-1", name: "Subscription revenue", code: "4000", group: "INCOME", amount: 84500, compareAmount: 76000 },
  { id: "rev-2", name: "Professional services", code: "4010", group: "INCOME", amount: 23600, compareAmount: 20400 },
  { id: "cogs-1", name: "Contractor costs", code: "5000", group: "COGS", amount: 21400, compareAmount: 19800 },
  { id: "exp-1", name: "Payroll", code: "6000", group: "EXPENSE", amount: 35200, compareAmount: 33100 },
  { id: "exp-2", name: "Software & tooling", code: "6100", group: "EXPENSE", amount: 8400, compareAmount: 7800 },
  { id: "exp-3", name: "Marketing", code: "6200", group: "EXPENSE", amount: 5600, compareAmount: 5200 },
  { id: "exp-4", name: "Office & ops", code: "6300", group: "EXPENSE", amount: 4900, compareAmount: 4500 },
];

export const profitAndLossSample: ProfitAndLossReportProps = {
  businessName: "Clover Books",
  currency: "USD",
  periodPreset: "this_month",
  periodLabel: "January 2025",
  periodStart: "2025-01-01",
  periodEnd: "2025-01-31",
  comparePreset: "previous_period",
  compareLabel: "Dec 2024",
  kpi: {
    income: 108100,
    cogs: 21400,
    grossProfit: 86700,
    expenses: 54100,
    netIncome: 32600,
    grossMarginPct: 80.2,
    netMarginPct: 30.2,
    changeIncomePct: 8.2,
    changeCogsPct: 4.1,
    changeGrossProfitPct: 9.1,
    changeExpensesPct: 5.5,
    changeNetIncomePct: 11.4,
  },
  rows: plRows,
  diagnostics: { hasActivity: true, reasons: [] },
};
