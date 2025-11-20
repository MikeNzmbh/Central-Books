import React from "react";
import { createRoot } from "react-dom/client";
import LoginPage, { LoginPayload } from "./LoginPage";

const el = document.getElementById("login-root");

function parsePayload(): LoginPayload | null {
  const script = document.getElementById("login-data");
  if (!script || !script.textContent) {
    return null;
  }
  try {
    return JSON.parse(script.textContent) as LoginPayload;
  } catch (err) {
    console.error("Unable to parse login payload", err);
    return null;
  }
}

if (el) {
  const payload = parsePayload();
  if (payload) {
    const root = createRoot(el);
    root.render(<LoginPage data={payload} />);
    window.dispatchEvent(new CustomEvent("login-app-mounted"));
  }
}
