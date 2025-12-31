import React from "react";
import { createRoot } from "react-dom/client";
import "../setup";
import InventoryApp from "./InventoryApp";

const rootEl = document.getElementById("inventory-root");

if (rootEl) {
  const root = createRoot(rootEl);
  root.render(
    <React.StrictMode>
      <InventoryApp />
    </React.StrictMode>,
  );
} else {
  console.warn("Inventory root not found");
}

