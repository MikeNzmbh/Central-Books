import React from "react";
import { createRoot } from "react-dom/client";
import CashflowReportPage, { CashflowReportProps } from "./CashflowReportPage";
import "../setup";

const container = document.getElementById("cashflow-report-root");
const dataEl = document.getElementById("cashflow-report-data");

if (container && dataEl && dataEl.textContent) {
  try {
    const payload = JSON.parse(dataEl.textContent) as CashflowReportProps;
    const root = createRoot(container);
    root.render(<CashflowReportPage {...payload} />);
  } catch (error) {
    console.error("Unable to mount cashflow report", error);
  }
}
