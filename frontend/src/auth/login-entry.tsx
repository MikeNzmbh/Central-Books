import React from "react";
import { createRoot } from "react-dom/client";
import CentralBooksLoginPage from "./LoginPage";
import "../index.css";

type Payload = {
  action?: string;
  csrfToken?: string;
  nextUrl?: string;
  next?: string;
  errors?: string[];
};

function readPayload(): Payload | null {
  const script = document.getElementById("login-data");
  if (!script || !script.textContent) {
    return null;
  }
  try {
    return JSON.parse(script.textContent) as Payload;
  } catch (error) {
    console.error("Failed to parse login payload", error);
    return null;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("login-root");
  if (!container) {
    return;
  }

  const payload = readPayload();
  if (!payload) {
    return;
  }

  const root = createRoot(container);
  root.render(
    <CentralBooksLoginPage
      action={payload.action}
      csrfToken={payload.csrfToken}
      nextUrl={payload.nextUrl || payload.next}
      errors={payload.errors || []}
    />
  );

  window.dispatchEvent(new Event("login-app-mounted"));
});
