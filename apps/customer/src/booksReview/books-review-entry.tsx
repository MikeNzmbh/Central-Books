import React from "react";
import { createRoot } from "react-dom/client";
import "../setup";
import BooksReviewPage from "./BooksReviewPage";

const rootEl = document.getElementById("books-review-root");

if (rootEl) {
  const defaultCurrency = rootEl.dataset.defaultCurrency || "USD";
  const root = createRoot(rootEl);
  root.render(
    <React.StrictMode>
      <BooksReviewPage defaultCurrency={defaultCurrency} />
    </React.StrictMode>
  );
} else {
  console.warn("Books review root not found");
}
