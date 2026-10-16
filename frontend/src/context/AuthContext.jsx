import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [adminUser, setAdminUser] = useState(null);
  const [customerSession, setCustomerSession] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check admin session on mount
  useEffect(() => {
    async function checkAuth() {
      try {
        if (api.token) {
          const res = await api.get('/auth/me');
          if (res && res.user) {
            setAdminUser(res.user);
          }
        }
      } catch (err) {
        console.warn('Admin session check expired or not found:', err.message);
        api.setToken(null);
        setAdminUser(null);
      } finally {
        setLoading(false);
      }
    }
    checkAuth();
  }, []);

  const adminLogin = async (email, password) => {
    const res = await api.post('/auth/login', { email, password });
    if (res && res.token) {
      api.setToken(res.token);
      setAdminUser(res.user);
    }
    return res;
  };

  const adminLogout = async () => {
    try {
      await api.post('/auth/logout', {});
    } catch (e) {
      console.error(e);
    } finally {
      api.setToken(null);
      setAdminUser(null);
    }
  };

  const customerLogin = (token, data) => {
    api.setCustomerToken(token);
    setCustomerSession({ token, ...data });
  };

  const customerLogout = async () => {
    try {
      await api.post('/customer/logout', {});
    } catch (e) {
      console.error(e);
    } finally {
      api.setCustomerToken(null);
      setCustomerSession(null);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        adminUser,
        customerSession,
        loading,
        adminLogin,
        adminLogout,
        customerLogin,
        customerLogout,
        setCustomerSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
