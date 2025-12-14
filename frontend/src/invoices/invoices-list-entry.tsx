import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "../index.css";
import { TransactionsPageContent } from "../transactions/TransactionsPage";

const rootEl = document.getElementById("invoices-list-root");

if (rootEl) {
    const root = createRoot(rootEl);
    root.render(
        <React.StrictMode>
            <BrowserRouter>
                <TransactionsPageContent kind="invoice" />
            </BrowserRouter>
        </React.StrictMode>
    );
} else {
    console.warn("Invoices list root not found");
}
