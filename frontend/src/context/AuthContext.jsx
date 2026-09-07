import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  authApi,
  getStoredToken,
  setStoredToken,
  getStoredUser,
  setStoredUser,
} from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(getStoredToken());
  const [user, setUser] = useState(getStoredUser());
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setStoredToken(null);
    setStoredUser(null);
  }, []);

  // Check and refresh profile on mount
  useEffect(() => {
    async function verifySession() {
      const existingToken = getStoredToken();
      if (existingToken) {
        try {
          const profile = await authApi.getMe(existingToken);
          setUser(profile);
          setStoredUser(profile);
        } catch {
          // Token invalid or expired
          logout();
        }
      }
      setIsLoading(false);
    }

    verifySession();

    // Listen for unauthorized 401 events from apiClient
    const handleUnauthorized = () => logout();
    window.addEventListener('bhoomi:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('bhoomi:unauthorized', handleUnauthorized);
  }, [logout]);

  const login = async (username, password) => {
    const res = await authApi.login({ username, password });
    const accessToken = res.access_token;
    setToken(accessToken);
    setStoredToken(accessToken);

    let profile;
    try {
      profile = await authApi.getMe(accessToken);
    } catch {
      profile = { username, role: 'field_officer' };
    }

    setUser(profile);
    setStoredUser(profile);
    return profile;
  };

  const register = async (payload) => {
    const newUser = await authApi.register(payload);
    return newUser;
  };

  const value = {
    token,
    user,
    isAuthenticated: Boolean(token && user),
    isLoading,
    login,
    register,
    logout,
    isAdmin: user?.role === 'admin',
    isVerifier: user?.role === 'verifier' || user?.role === 'admin',
    isFieldOfficer: user?.role === 'field_officer',
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
