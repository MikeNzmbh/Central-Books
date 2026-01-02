import React from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { AppShell, CloverSidebar } from "@shared-ui";
import { useAuth } from "../contexts/AuthContext";

export const CustomerLayout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { auth, logout } = useAuth();

  const user = auth.user
    ? {
        name: auth.user.name || auth.user.email,
        email: auth.user.email,
      }
    : { name: "Guest", email: "guest@cloverbooks.local" };

  return (
    <AppShell className="bg-transparent">
      <div className="flex min-h-screen w-full">
        <CloverSidebar
          currentPath={location.pathname}
          onNavigate={navigate}
          onLogout={logout}
          user={user}
          brand={{ name: "CLOVER", subtitle: "Customer Workspace" }}
        />
        <main className="flex-1 min-h-screen overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </AppShell>
  );
};

export default CustomerLayout;
