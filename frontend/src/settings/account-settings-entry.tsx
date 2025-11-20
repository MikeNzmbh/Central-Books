import React from "react";
import { createRoot } from "react-dom/client";
import AccountSettingsPage, { AccountSettingsProps } from "./AccountSettingsPage";
import "../index.css";

const rootEl = document.getElementById("account-settings-root");
const dataEl = document.getElementById("account-settings-data");

if (rootEl && dataEl) {
  try {
    const payload = JSON.parse(dataEl.textContent || "{}") as AccountSettingsProps;
    const root = createRoot(rootEl);
    root.render(<AccountSettingsPage {...payload} />);
  } catch (error) {
    console.error("Unable to parse account settings payload", error);
  }
}
