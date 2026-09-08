import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  authApi,
  getStoredToken,
  setStoredToken,
  getStoredUser,
  setStoredUser,
  setUnauthorizedHandler,
  isTokenExpired,
} from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const logout = useCallback(async () => {
    setToken(null);
    setUser(null);
    await setStoredToken(null);
    await setStoredUser(null);
  }, []);

  // Check and refresh profile on mount
  useEffect(() => {
    async function verifySession() {
      try {
        const existingToken = await getStoredToken();

        if (existingToken) {
          if (isTokenExpired(existingToken)) {
            await logout();
          } else {
            try {
              const profile = await authApi.getMe(existingToken);
              if (profile?.role && profile.role !== 'field_officer') {
                await logout();
              } else {
                setToken(existingToken);
                setUser(profile);
                await setStoredUser(profile);
              }
            } catch (err) {
              if (err.message && (err.message.includes('Authentication required') || err.message.includes('Session expired'))) {
                await logout();
              }
            }
          }
        }
      } catch (e) {
        console.warn('Session verification error:', e);
      } finally {
        setIsLoading(false);
      }
    }

    verifySession();
    setUnauthorizedHandler(() => {
      logout();
    });
  }, [logout]);

  const login = async (username, password) => {
    const res = await authApi.login({ username, password });
    const accessToken = res.access_token;

    let profile;
    try {
      profile = await authApi.getMe(accessToken);
    } catch {
      profile = { username, role: 'field_officer' };
    }

    if (profile?.role && profile.role !== 'field_officer') {
      await setStoredToken(null);
      await setStoredUser(null);
      throw new Error('This mobile app is for field officers only. Please use the web dashboard.');
    }

    setToken(accessToken);
    await setStoredToken(accessToken);
    setUser(profile);
    await setStoredUser(profile);
    return profile;
  };

  const register = async (payload) => {
    const newUser = await authApi.register(payload);
    return newUser;
  };

  const value = {
    token,
    user,
    isAuthenticated: Boolean(token && user && user.role === 'field_officer'),
    isLoading,
    login,
    register,
    logout,
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

export default AuthContext;
