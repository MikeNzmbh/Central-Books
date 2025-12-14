import React from "react";
import { createRoot } from "react-dom/client";
import "../index.css";
import { TransactionsPageContent } from "../transactions/TransactionsPage";

const rootEl = document.getElementById("expenses-list-root");

if (rootEl) {
    const root = createRoot(rootEl);
    root.render(
        <React.StrictMode>
            <TransactionsPageContent kind="expense" />
        </React.StrictMode>
    );
} else {
    console.warn("Expenses list root not found");
}
