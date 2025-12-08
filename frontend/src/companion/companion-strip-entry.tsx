import "../index.css";
import React from "react";
import { createRoot } from "react-dom/client";

import CompanionStrip from "./CompanionStrip";
import type { CompanionContext } from "./api";

function mountStrip(node: HTMLElement) {
  const ctx = (node.dataset.companionContext as CompanionContext) || "dashboard";
  const userName = node.dataset.userName || undefined;
  const root = createRoot(node);
  root.render(
    <React.StrictMode>
      <CompanionStrip context={ctx} userName={userName} />
    </React.StrictMode>
  );
}

document.addEventListener("DOMContentLoaded", () => {
  const targets = Array.from(document.querySelectorAll<HTMLElement>("[data-companion-context]"));
  targets.forEach(mountStrip);
});
