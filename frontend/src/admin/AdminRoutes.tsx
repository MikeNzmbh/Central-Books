import React from "react";
import {
  BrowserRouter,
  MemoryRouter,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { AuthProvider, useAuth } from "../contexts/AuthContext";
import { AdminApp } from "./AdminApp";
import { InternalAdminLogin } from "./InternalAdminLogin";

const AdminGuard: React.FC<{ children: React.ReactElement }> = ({ children }) => {
  const { auth } = useAuth();
  const location = useLocation();

  if (auth.loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 text-slate-700">
        Checking admin access…
      </div>
    );
  }

  if (!auth.authenticated || !auth.isAdmin) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return children;
};

export const AdminRoutes: React.FC = () => (
  <Routes>
    <Route path="/login" element={<InternalAdminLogin />} />
    <Route
      path="/*"
      element={
        <AdminGuard>
          <AdminApp />
        </AdminGuard>
      }
    />
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>
);

export const AdminRoot: React.FC = () => (
  <AuthProvider>
    <BrowserRouter basename="/internal-admin">
      <AdminRoutes />
    </BrowserRouter>
  </AuthProvider>
);

export const AdminMemoryRouter: React.FC<{ initialEntries?: string[] }> = ({
  initialEntries = ["/"],
}) => (
  <AuthProvider>
    <MemoryRouter initialEntries={initialEntries}>
      <AdminRoutes />
    </MemoryRouter>
  </AuthProvider>
);
