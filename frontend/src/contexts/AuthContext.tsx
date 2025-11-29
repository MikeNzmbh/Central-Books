// Authentication Context for CERN Books
// Provides user authentication state across the React application

import React, { createContext, useContext, useState, useEffect } from 'react';

export interface User {
    id: number;
    email: string;
    username: string;
    firstName: string;
    lastName: string;
    fullName: string;
}

export interface AuthState {
    authenticated: boolean;
    user: User | null;
    loading: boolean;
}

interface AuthContextType {
    auth: AuthState;
    refresh: () => Promise<void>;
    logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [auth, setAuth] = useState<AuthState>({
        authenticated: false,
        user: null,
        loading: true,
    });

    const fetchCurrentUser = async () => {
        try {
            const response = await fetch('/api/auth/me', {
                credentials: 'same-origin', // Include cookies
            });

            if (!response.ok) {
                throw new Error('Failed to fetch user');
            }

            const data = await response.json();

            setAuth({
                authenticated: data.authenticated,
                user: data.user,
                loading: false,
            });
        } catch (error) {
            console.error('Error fetching current user:', error);
            setAuth({
                authenticated: false,
                user: null,
                loading: false,
            });
        }
    };

    const logout = async () => {
        try {
            const csrfToken = document.querySelector<HTMLInputElement>('[name=csrfmiddlewaretoken]')?.value;

            await fetch('/logout/', {
                method: 'POST',
                credentials: 'same-origin',
                headers: csrfToken ? {
                    'X-CSRFToken': csrfToken,
                } : {},
            });

            setAuth({
                authenticated: false,
                user: null,
                loading: false,
            });

            // Redirect to login
            window.location.href = '/login/';
        } catch (error) {
            console.error('Logout failed:', error);
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
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
