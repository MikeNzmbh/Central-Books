import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { setAccessToken } from '../api/client';

/**
 * OAuth Callback Handler
 * 
 * This page handles the redirect from Google OAuth.
 * It reads the token and user info from URL params,
 * stores them in localStorage, and redirects to dashboard.
 */
const OAuthCallbackPage: React.FC = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();

    useEffect(() => {
        const token = searchParams.get('token');
        const userId = searchParams.get('user_id');
        const email = searchParams.get('email');
        const firstName = searchParams.get('first_name');
        const lastName = searchParams.get('last_name');

        if (token && userId && email) {
            // Store in localStorage
            localStorage.setItem('auth_token', token);
            localStorage.setItem('user', JSON.stringify({
                id: Number(userId),
                email,
                first_name: firstName || '',
                last_name: lastName || '',
            }));

            // Update the API client's access token
            setAccessToken(token);

            // Redirect to dashboard
            navigate('/dashboard', { replace: true });
        } else {
            // Missing params, go to login
            navigate('/login', { replace: true });
        }
    }, [searchParams, navigate]);

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-white to-sky-50">
            <div className="text-center">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-slate-900 mx-auto mb-4"></div>
                <p className="text-slate-600">Logging you in...</p>
            </div>
        </div>
    );
};

export default OAuthCallbackPage;
