import { createContext, useContext, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { useNavigate } from "react-router-dom";
import api from "../utils/api";
import { decodeJwt } from "../utils/jwt";

const STORAGE_KEY = "smarthospital_auth";
const AuthContext = createContext(null);

function readStoredAuth() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function buildUserFromSession(stored) {
  if (!stored?.token) return null;
  const payload = decodeJwt(stored.token);
  if (!payload?.sub || !payload?.role) return null;
  return {
    token: stored.token,
    role: payload.role,
    user: {
      id: Number(stored.user?.id ?? payload.sub),
      role: payload.role,
      name: stored.user?.name ?? stored.name ?? "",
      email: stored.user?.email ?? "",
    },
  };
}

export function AuthProvider({ children }) {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [isInitializing, setIsInitializing] = useState(true);

  const logout = (reason = "Logged out") => {
    setUser(null);
    setToken(null);
    localStorage.removeItem(STORAGE_KEY);
    delete api.defaults.headers.common.Authorization;
    if (reason) toast(reason);
    navigate("/login", { replace: true });
  };

  useEffect(() => {
    const stored = readStoredAuth();
    const restored = buildUserFromSession(stored);
    if (restored) {
      setUser(restored.user);
      setToken(restored.token);
      if (restored.role === "patient") {
        // Reset patient queue session on app re-entry so dashboard starts clean.
        localStorage.removeItem("smarthospital_patient_id");
      }
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          token: restored.token,
          role: restored.role,
          user: restored.user,
        })
      );
    } else if (stored) {
      localStorage.removeItem(STORAGE_KEY);
    }
    setIsInitializing(false);
  }, []);

  useEffect(() => {
    if (token) {
      api.defaults.headers.common.Authorization = `Bearer ${token}`;
    } else {
      delete api.defaults.headers.common.Authorization;
    }
  }, [token]);

  const login = async (email, password) => {
    const formData = new FormData();
    formData.append("username", email);
    formData.append("password", password);
    const res = await api.post("/auth/login", formData);
    const { access_token, user_id, role, name } = res.data;
    const decoded = decodeJwt(access_token);
    if (!decoded?.sub || !decoded?.role || decoded.role !== role) {
      throw new Error("Invalid token payload");
    }
    const restoredRole = decoded.role;
    const u = { id: user_id, role: restoredRole, name, email };
    setUser(u);
    setToken(access_token);
    if (restoredRole === "patient") {
      // Start with no active queue context on each fresh login.
      localStorage.removeItem("smarthospital_patient_id");
    }
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ token: access_token, role: restoredRole, user: u })
    );
    toast.success("Logged in");
    return u;
  };

  const register = async ({ name, email, password, role }) => {
    await api.post("/auth/register", { name, email, password, role });
    toast.success("Registered successfully");
  };

  const contextValue = useMemo(
    () => ({ user, token, isInitializing, login, register, logout }),
    [user, token, isInitializing]
  );

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
