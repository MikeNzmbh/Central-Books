import React from "react";
import { createRoot } from "react-dom/client";
import AccountSettingsPage, { AccountSettingsPayload } from "./AccountSettingsPage";

const el = document.getElementById("account-settings-root");

function parsePayload(): AccountSettingsPayload | null {
  const script = document.getElementById("account-settings-data");
  if (!script || !script.textContent) {
    return null;
  }
  try {
    return JSON.parse(script.textContent) as AccountSettingsPayload;
  } catch (error) {
    console.error("Unable to parse account settings payload", error);
    return null;
  }
}

if (el) {
  const data = parsePayload();
  if (data) {
    const root = createRoot(el);
    root.render(<AccountSettingsPage data={data} />);
  }
}
