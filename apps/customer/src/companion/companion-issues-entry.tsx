import "../index.css";
import React from "react";
import { createRoot } from "react-dom/client";
import CompanionIssuesPage from "./CompanionIssuesPage";

const rootEl = document.getElementById("companion-issues-root");

if (rootEl) {
  const root = createRoot(rootEl);
  root.render(<CompanionIssuesPage />);
}
