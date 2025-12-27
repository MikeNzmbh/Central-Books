import "../index.css";
import React from "react";
import { createRoot } from "react-dom/client";
import Sidebar from "./Sidebar";
import { AuthProvider } from "../contexts/AuthContext";

function mountSidebar(node: HTMLElement) {
    const businessName = node.dataset.businessName || "Your business";
    const businessSubtitle = node.dataset.businessSubtitle || "CLOVER Books";
    const userName = node.dataset.userName || "User";
    const userEmail = node.dataset.userEmail || "";

    const root = createRoot(node);
    root.render(
        <React.StrictMode>
            <AuthProvider>
                <Sidebar
                    brand={{ name: businessName, subtitle: businessSubtitle }}
                    user={{ name: userName, email: userEmail }}
                />
            </AuthProvider>
        </React.StrictMode>
    );
}

document.addEventListener("DOMContentLoaded", () => {
    const sidebarRoot = document.getElementById("sidebar-root");
    if (sidebarRoot) {
        mountSidebar(sidebarRoot);
    }
});
