import React from "react";
import { createRoot } from "react-dom/client";
import "../index.css";
import CloverBooksWelcomePage from "./CloverBooksWelcomePage";

document.addEventListener("DOMContentLoaded", () => {
  const rootEl = document.getElementById("welcome-root");
  if (!rootEl) return;

  const root = createRoot(rootEl);
  root.render(<CloverBooksWelcomePage />);

  window.dispatchEvent(new Event("welcome-app-mounted"));
});

