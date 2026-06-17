import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { authApi } from "./api";
import type { Me, Role } from "./types";

interface AuthState {
  me: Me | null;
  loading: boolean;
  login: (email: string, password: string, recaptcha?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<void>;
}

const AuthContext = createContext<AuthState>(null as unknown as AuthState);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshMe = useCallback(async () => {
    try {
      setMe(await authApi.me());
    } catch {
      setMe(null);
    }
  }, []);

  useEffect(() => {
    (async () => {
      const token = await authApi.refresh();
      if (token) await refreshMe();
      setLoading(false);
    })();
  }, [refreshMe]);

  const login = useCallback(async (email: string, password: string, recaptcha?: string) => {
    await authApi.login(email, password, recaptcha);
    await refreshMe();
  }, [refreshMe]);

  const logout = useCallback(async () => {
    await authApi.logout();
    setMe(null);
  }, []);

  return (
    <AuthContext.Provider value={{ me, loading, login, logout, refreshMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

// Защита маршрутов по ролям. roles пустой = достаточно быть авторизованным.
export function ProtectedRoute({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { me, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div className="container">Загрузка...</div>;
  if (!me) return <Navigate to="/login" state={{ from: location }} replace />;
  if (roles && roles.length > 0 && !roles.includes(me.user.role)) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
