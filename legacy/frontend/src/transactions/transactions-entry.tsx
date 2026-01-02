import React from "react";
import ReactDOM from "react-dom/client";
import TransactionsPage from "./TransactionsPage";
import "../setup";

ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
        <TransactionsPage />
    </React.StrictMode>
);
