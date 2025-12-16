// Authentication Context for Clover Books
// Provides user authentication state across the React application

import React, { createContext, useContext, useState, useEffect } from "react";
import { parseCookies } from "../utils/cookies";

export interface InternalAdmin {
  role: string;
  canAccessInternalAdmin: boolean;
}

// RBAC v1: Workspace membership with role and permissions
export interface Workspace {
  businessId: number;
  businessName: string;
  role: string;
  roleLabel: string;
  roleDescription: string;
  roleColor: string;
  permissions: string[];
  permissionLevels?: Record<string, string>;
  isOwner: boolean;
  department: string | null;
  region: string | null;
}

export interface User {
  id: number;
  email: string;
  username: string;
  firstName: string;
  lastName: string;
  fullName: string;
  role?: string;
  isStaff?: boolean;
  isSuperuser?: boolean;
  is_staff?: boolean;
  is_superuser?: boolean;
  internalAdmin?: InternalAdmin | null;
  workspace?: Workspace | null; // RBAC v1
}

export interface AuthState {
  authenticated: boolean;
  user: User | null;
  loading: boolean;
  isAdmin: boolean;
}

interface AuthContextType {
  auth: AuthState;
  refresh: () => Promise<AuthState | undefined>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [auth, setAuth] = useState<AuthState>({
    authenticated: false,
    user: null,
    loading: true,
    isAdmin: false,
  });

  const computeIsAdmin = (user: User | null) =>
    Boolean(
      user &&
      (user.internalAdmin?.canAccessInternalAdmin ||
        (user.isStaff ?? user.is_staff) ||
        (user.isSuperuser ?? user.is_superuser) ||
        user.role === "admin" ||
        user.role === "staff" ||
        user.role === "superadmin")
    );

  const fetchCurrentUser = async () => {
    try {
      const response = await fetch("/api/auth/me", {
        credentials: "same-origin",
      });

      if (!response.ok) {
        throw new Error("Failed to fetch user");
      }

      const data = await response.json();
      const user = data.user as User | null;
      const isAdmin = computeIsAdmin(user);

      const nextAuth: AuthState = {
        authenticated: data.authenticated,
        user,
        loading: false,
        isAdmin,
      };
      setAuth(nextAuth);
      return nextAuth;
    } catch (error) {
      console.error("Error fetching current user:", error);
      const nextAuth: AuthState = {
        authenticated: false,
        user: null,
        loading: false,
        isAdmin: false,
      };
      setAuth(nextAuth);
      return nextAuth;
    }
  };

  const logout = async () => {
    try {
      const cookies = parseCookies(document.cookie || "");
      const csrfToken =
        cookies.csrftoken || document.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")?.value;
      const headers: Record<string, string> = {};
      if (csrfToken) {
        headers["X-CSRFToken"] = csrfToken;
      }

      // Best-effort: end impersonation if active.
      try {
        await fetch("/internal/impersonate/stop/", {
          method: "POST",
          credentials: "same-origin",
          headers,
        });
      } catch (impersonationError) {
        console.warn("Impersonation stop failed (continuing logout):", impersonationError);
      }

      await fetch("/logout/", {
        method: "POST",
        credentials: "same-origin",
        headers,
      });

      setAuth({
        authenticated: false,
        user: null,
        loading: false,
        isAdmin: false,
      });

      if (typeof window !== "undefined" && window.location?.assign) {
        window.location.assign("/login/");
      }
    } catch (error) {
      console.error("Logout failed:", error);
    }
  };

  useEffect(() => {
    fetchCurrentUser();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        auth,
        refresh: fetchCurrentUser,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
