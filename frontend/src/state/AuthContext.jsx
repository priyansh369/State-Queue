import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import toast from "react-hot-toast";
import { useLocation, useNavigate } from "react-router-dom";
import Modal from "../components/common/Modal";
import api, { setUnauthorizedHandler } from "../utils/api";
import { decodeJwt, isTokenExpired } from "../utils/jwt";

const STORAGE_KEY = "smarthospital_auth";
const IDLE_TIMEOUT_MS = 10 * 60 * 1000;
const WARNING_MS = 60 * 1000;
const ACTIVITY_EVENTS = ["mousemove", "mousedown", "click", "keydown", "touchstart"];

const AuthContext = createContext(null);

function readStoredAuth() {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (!stored) return null;
  try {
    return JSON.parse(stored);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [warningOpen, setWarningOpen] = useState(false);
  const [countdown, setCountdown] = useState(60);
  const warningTimerRef = useRef(null);
  const logoutTimerRef = useRef(null);
  const countdownTimerRef = useRef(null);

  const clearInactivityTimers = () => {
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current);
    if (countdownTimerRef.current) clearInterval(countdownTimerRef.current);
    warningTimerRef.current = null;
    logoutTimerRef.current = null;
    countdownTimerRef.current = null;
  };

  const logout = (reason = "Logged out") => {
    clearInactivityTimers();
    setWarningOpen(false);
    setUser(null);
    setToken(null);
    localStorage.removeItem(STORAGE_KEY);
    delete api.defaults.headers.common.Authorization;
    if (reason) toast(reason);
    if (location.pathname !== "/login") {
      navigate("/login", { replace: true });
    }
  };

  const resetInactivityTimers = () => {
    if (!token) return;
    clearInactivityTimers();
    setWarningOpen(false);
    warningTimerRef.current = setTimeout(() => {
      setWarningOpen(true);
      setCountdown(60);
      countdownTimerRef.current = setInterval(() => {
        setCountdown((prev) => (prev <= 1 ? 0 : prev - 1));
      }, 1000);
    }, IDLE_TIMEOUT_MS - WARNING_MS);

    logoutTimerRef.current = setTimeout(() => {
      logout("Session expired due to inactivity");
    }, IDLE_TIMEOUT_MS);
  };

  useEffect(() => {
    const stored = readStoredAuth();
    if (!stored?.token || !stored?.user) return;
    if (isTokenExpired(stored.token)) {
      localStorage.removeItem(STORAGE_KEY);
      return;
    }
    setUser(stored.user);
    setToken(stored.token);
  }, []);

  useEffect(() => {
    if (token) {
      api.defaults.headers.common.Authorization = `Bearer ${token}`;
      resetInactivityTimers();
    } else {
      clearInactivityTimers();
      setWarningOpen(false);
      delete api.defaults.headers.common.Authorization;
    }
  }, [token]);

  useEffect(() => {
    if (!token) return undefined;
    const activityHandler = () => resetInactivityTimers();
    ACTIVITY_EVENTS.forEach((eventName) => window.addEventListener(eventName, activityHandler));
    return () => {
      ACTIVITY_EVENTS.forEach((eventName) =>
        window.removeEventListener(eventName, activityHandler)
      );
    };
  }, [token]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      logout("Session expired. Please log in again.");
    });
    return () => setUnauthorizedHandler(null);
  }, [location.pathname]);

  const login = async (email, password) => {
    const formData = new FormData();
    formData.append("username", email);
    formData.append("password", password);
    const res = await api.post("/auth/login", formData);
    const { access_token, user_id, role, name } = res.data;
    const decoded = decodeJwt(access_token);
    if (!decoded?.sub || !decoded?.role || decoded.role !== role || isTokenExpired(access_token)) {
      throw new Error("Invalid token payload");
    }
    const u = { id: user_id, role, name, email };
    setUser(u);
    setToken(access_token);
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: u, token: access_token }));
    toast.success("Logged in");
    return u;
  };

  const register = async ({ name, email, password, role }) => {
    await api.post("/auth/register", { name, email, password, role });
    toast.success("Registered successfully");
  };

  const stayLoggedIn = () => {
    toast.success("Session extended");
    resetInactivityTimers();
  };

  const contextValue = useMemo(() => ({ user, token, login, register, logout }), [user, token]);

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
      <Modal open={warningOpen} title="Session expiring" onClose={stayLoggedIn}>
        <p>Your session will expire in {countdown} seconds due to inactivity.</p>
        <div className="modal-actions">
          <button className="primary-btn" onClick={stayLoggedIn}>
            Stay Logged In
          </button>
          <button className="danger-btn" onClick={() => logout("Logged out")}>
            Logout Now
          </button>
        </div>
      </Modal>
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
