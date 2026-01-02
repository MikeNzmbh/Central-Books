import React from "react";
import ReactDOM from "react-dom/client";
import BusinessSkipLandingPage from "./BusinessSkipLandingPage";
import "../setup";

const rootEl = document.getElementById("workspace-home-root");

if (!rootEl) {
  throw new Error("Workspace home root element not found");
}

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <BusinessSkipLandingPage />
  </React.StrictMode>
);
