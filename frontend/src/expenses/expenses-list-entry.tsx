import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "../setup";
import { TransactionsPageContent } from "../transactions/TransactionsPage";

const rootEl = document.getElementById("expenses-list-root");

if (rootEl) {
    const root = createRoot(rootEl);
    root.render(
        <React.StrictMode>
            <BrowserRouter>
                <TransactionsPageContent kind="expense" />
            </BrowserRouter>
        </React.StrictMode>
    );
} else {
    console.warn("Expenses list root not found");
}
