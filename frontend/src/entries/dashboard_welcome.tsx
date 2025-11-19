import React from "react";
import { createRoot } from "react-dom/client";
import CentralBooksWelcomeOnboarding from "../components/CentralBooksWelcomeOnboarding";

const el = document.getElementById("welcome-onboarding-root");

if (el) {
  const dataset = el.dataset;
  const startBooksUrl = dataset.startBooksUrl || "/customers/new/";
  const createBankUrl = dataset.createBankUrl || "/bank-accounts/new/";
  const importCsvUrl = dataset.importCsvUrl || "/bank/import/";
  const hasBank = dataset.hasBank === "true";

  const onStartBooks = () => {
    window.location.href = startBooksUrl;
  };

  const onUploadSampleCsv = () => {
    if (!hasBank) {
      window.location.href = createBankUrl;
    } else {
      window.location.href = importCsvUrl;
    }
  };

  const root = createRoot(el);
  root.render(
    <CentralBooksWelcomeOnboarding
      onStartBooks={onStartBooks}
      onUploadSampleCsv={onUploadSampleCsv}
    />
  );
}
