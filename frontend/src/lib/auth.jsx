import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { api, getToken, onUnauthorized, setToken } from './api';

const AuthContext = createContext(null);

export const ROLE_LABELS = {
  admin: 'Administrator',
  staff: 'Staff',
  customer: 'Customer',
};

/** Which roles may use each capability. Mirrors the backend permissions. */
export const PERMISSIONS = {
  viewCustomers: ['admin', 'staff'],
  manageCustomers: ['admin', 'staff'],
  deleteCustomers: ['admin'],
  manageSubscriptions: ['admin', 'staff'],
  renewSubscriptions: ['admin', 'staff'],
  viewPayments: ['admin', 'staff', 'customer'],
  managePayments: ['admin', 'staff'],
  viewReports: ['admin'],
  manageUsers: ['admin'],
};

/** The permission needed to open each section of the app (anything not listed is open to all roles). */
const PATH_PERMISSIONS = {
  '/customers': 'viewCustomers',
  '/payments': 'viewPayments',
  '/reports': 'viewReports',
};

/** True if a user with this role may open `path`. Used to avoid redirecting people to dead ends. */
export function roleCanOpenPath(role, path) {
  const pathname = String(path || '/').split('?')[0];
  const section = Object.keys(PATH_PERMISSIONS).find((p) => pathname === p || pathname.startsWith(`${p}/`));
  return !section || Boolean(PERMISSIONS[PATH_PERMISSIONS[section]]?.includes(role));
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(getToken()));

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    onUnauthorized(logout);
    if (!getToken()) return;
    api
      .get('/auth/me')
      .then(setUser)
      .catch(() => logout())
      .finally(() => setLoading(false));
  }, [logout]);

  const login = useCallback(async (email, password) => {
    const result = await api.post('/auth/login', { email, password });
    setToken(result.token);
    setUser(result.user);
    return result.user;
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      login,
      logout,
      setUser,
      can: (permission) => Boolean(user && PERMISSIONS[permission]?.includes(user.role)),
    }),
    [user, loading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
