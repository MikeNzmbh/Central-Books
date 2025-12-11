import React from "react";
import { createRoot } from "react-dom/client";
import "../index.css";
import InvoicesListPage from "./InvoicesListPage";

const rootEl = document.getElementById("invoices-list-root");

if (rootEl) {
    const defaultCurrency = rootEl.dataset.defaultCurrency || "USD";
    const root = createRoot(rootEl);
    root.render(
        <React.StrictMode>
            <InvoicesListPage defaultCurrency={defaultCurrency} />
        </React.StrictMode>
    );
} else {
    console.warn("Invoices list root not found");
}
