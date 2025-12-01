// Authentication Context for CERN Books
// Provides user authentication state across the React application

import React, { createContext, useContext, useState, useEffect } from "react";

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
        ((user.isStaff ?? user.is_staff) ||
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
      const csrfToken = document.querySelector<HTMLInputElement>("[name=csrfmiddlewaretoken]")?.value;

      await fetch("/logout/", {
        method: "POST",
        credentials: "same-origin",
        headers: csrfToken
          ? {
              "X-CSRFToken": csrfToken,
            }
          : {},
      });

      setAuth({
        authenticated: false,
        user: null,
        loading: false,
        isAdmin: false,
      });

      window.location.href = "/login/";
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
