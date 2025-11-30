// frontend/src/reports/pl-report-entry.tsx
import React from "react";
import { createRoot } from "react-dom/client";
import ProfitAndLossReportPage from "./ProfitAndLossReportPage";
import "../index.css";

const container = document.getElementById("pl-report-root");
const dataEl = document.getElementById("pl-report-data");

interface PLReportData {
    periodLabel: string;
    currency: string;
    totalRevenue: number;
    totalExpenses: number;
    netIncome: number;
    revenueItems: Array<{
        category: string;
        amount: number;
    }>;
    expenseItems: Array<{
        category: string;
        amount: number;
    }>;
}

if (container && dataEl && dataEl.textContent) {
    try {
        const payload = JSON.parse(dataEl.textContent) as PLReportData;
        const root = createRoot(container);
        root.render(<ProfitAndLossReportPage {...payload} />);
    } catch (error) {
        console.error("Unable to mount P&L report", error);
    }
}
