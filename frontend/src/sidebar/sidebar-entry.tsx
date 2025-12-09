import "../index.css";
import React from "react";
import { createRoot } from "react-dom/client";
import Sidebar from "./Sidebar";
import { AuthProvider } from "../contexts/AuthContext";

function mountSidebar(node: HTMLElement) {
    const businessName = node.dataset.businessName || "Your business";
    const businessInitials = node.dataset.businessInitials || "CB";
    const userName = node.dataset.userName || "User";
    const userEmail = node.dataset.userEmail || "";
    const activeRoute = node.dataset.activeRoute || "";

    const root = createRoot(node);
    root.render(
        <React.StrictMode>
            <AuthProvider>
                <Sidebar
                    businessName={businessName}
                    businessInitials={businessInitials}
                    userName={userName}
                    userEmail={userEmail}
                    activeRoute={activeRoute}
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
