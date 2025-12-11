import React from "react";
import { createRoot } from "react-dom/client";
import "../index.css";
import ExpensesListPage from "./ExpensesListPage";

const rootEl = document.getElementById("expenses-list-root");

if (rootEl) {
    const defaultCurrency = rootEl.dataset.defaultCurrency || "USD";
    const root = createRoot(rootEl);
    root.render(
        <React.StrictMode>
            <ExpensesListPage defaultCurrency={defaultCurrency} />
        </React.StrictMode>
    );
} else {
    console.warn("Expenses list root not found");
}
