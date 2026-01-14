import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import {
  login as apiLogin,
  refresh as apiRefresh,
  logout as apiLogout,
  type User,
  type TokenResponse,
} from "../api/client";

export interface AuthState {
  authenticated: boolean;
  user: User | null;
  loading: boolean;
  isAdmin: boolean;
}

interface AuthContextType {
  auth: AuthState;
  login: (email: string, password: string) => Promise<TokenResponse>;
  refresh: () => Promise<AuthState | undefined>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const computeIsAdmin = (user: User | null) => {
  if (!user) return false;
  const role = (user.role || "").toLowerCase();
  return Boolean(
    user.is_admin ||
      user.isStaff ||
      user.is_staff ||
      user.isSuperuser ||
      user.is_superuser ||
      role === "admin" ||
      role === "superadmin" ||
      user.internalAdmin?.adminPanelAccess ||
      user.internalAdmin?.canAccessInternalAdmin
  );
};

const toAuthState = (user: User | null, loading = false): AuthState => ({
  authenticated: Boolean(user),
  user,
  loading,
  isAdmin: computeIsAdmin(user),
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [auth, setAuth] = useState<AuthState>(() => toAuthState(null, true));

  const refresh = async () => {
    try {
      const data = await apiRefresh();
      const nextAuth = toAuthState(data.user, false);
      setAuth(nextAuth);
      return nextAuth;
    } catch {
      setAuth(toAuthState(null, false));
      return undefined;
    }
  };

  const login = async (email: string, password: string) => {
    const data = await apiLogin(email, password);
    setAuth(toAuthState(data.user, false));
    return data;
  };

  const logout = async () => {
    try {
      await apiLogout();
    } finally {
      setAuth(toAuthState(null, false));
    }
  };

  const hydrate = useMemo(() => refresh, []);

  useEffect(() => {
    hydrate().catch(() => undefined);
  }, [hydrate]);

  return (
    <AuthContext.Provider value={{ auth, login, refresh, logout }}>
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
