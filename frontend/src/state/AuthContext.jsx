import { createContext, useContext, useEffect, useState } from "react";
import toast from "react-hot-toast";
import api from "../utils/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);

  useEffect(() => {
    const stored = localStorage.getItem("smarthospital_auth");
    if (stored) {
      const parsed = JSON.parse(stored);
      setUser(parsed.user);
      setToken(parsed.token);
    }
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
    const u = { id: user_id, role, name, email };
    setUser(u);
    setToken(access_token);
    localStorage.setItem(
      "smarthospital_auth",
      JSON.stringify({ user: u, token: access_token })
    );
    toast.success("Logged in");
    return u;
  };

  const register = async ({ name, email, password, role }) => {
    await api.post("/auth/register", { name, email, password, role });
    toast.success("Registered successfully");
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    localStorage.removeItem("smarthospital_auth");
    toast.success("Logged out");
  };

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

