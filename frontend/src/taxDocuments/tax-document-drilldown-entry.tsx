import React from "react";
import { createRoot } from "react-dom/client";
import "../index.css";
import TaxDocumentDrilldownCard from "./TaxDocumentDrilldownCard";

const rootEl = document.getElementById("tax-document-drilldown-root");

if (rootEl) {
  const documentType = (rootEl.dataset.documentType || "invoice") as "invoice" | "expense";
  const documentId = rootEl.dataset.documentId;
  if (!documentId) {
    console.warn("tax-document-drilldown-root missing data-document-id");
  } else {
    const root = createRoot(rootEl);
    root.render(
      <React.StrictMode>
        <TaxDocumentDrilldownCard documentType={documentType} documentId={documentId} />
      </React.StrictMode>
    );
  }
} else {
  // Optional: page may not include drilldown root.
}

