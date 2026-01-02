// frontend/src/reports/cashflow-report-print-entry.tsx
import React from "react";
import { createRoot } from "react-dom/client";
import CashflowReportPrintPage from "./CashflowReportPrintPage";
import { CashflowReportProps } from "./CashflowReportPage";
import "../setup";

const container = document.getElementById("cashflow-report-print-root");
const dataEl = document.getElementById("cashflow-report-print-data");

if (container && dataEl && dataEl.textContent) {
    try {
        const payload = JSON.parse(dataEl.textContent) as CashflowReportProps;
        const root = createRoot(container);
        root.render(<CashflowReportPrintPage {...payload} />);
    } catch (error) {
        console.error("Unable to mount cashflow print report", error);
    }
}
