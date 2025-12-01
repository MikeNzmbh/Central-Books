import React from "react";
import { createRoot } from "react-dom/client";
import { AdminRoot } from "./admin/AdminRoutes";
import "./index.css";

const rootElement = document.getElementById("admin-root");
if (!rootElement) {
    throw new Error("Failed to find the admin-root element");
}

const root = createRoot(rootElement);
root.render(
    <React.StrictMode>
        <AdminRoot />
    </React.StrictMode>
);
