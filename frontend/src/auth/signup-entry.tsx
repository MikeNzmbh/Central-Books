import React from "react";
import { createRoot } from "react-dom/client";
import CloverBooksCreateAccount from "./CloverBooksCreateAccount";
import "../index.css";

type SignupPayload = {
  action?: string;
  csrfToken?: string;
  errors?: string[];
  initialEmail?: string;
  initialBusinessName?: string;
};

const rootEl = document.getElementById("signup-root");
const dataEl = document.getElementById("signup-data");

if (rootEl && dataEl) {
  try {
    const payload = JSON.parse(dataEl.textContent || "{}") as SignupPayload;
    const root = createRoot(rootEl);
    root.render(
      <CloverBooksCreateAccount
        action={payload.action}
        csrfToken={payload.csrfToken}
        errors={payload.errors}
        initialEmail={payload.initialEmail}
        initialBusinessName={payload.initialBusinessName}
      />
    );
  } catch (error) {
    console.error("Unable to parse signup payload", error);
  }
}
