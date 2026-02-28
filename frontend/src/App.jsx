import { Navigate, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import PatientLayout from "./pages/patient/PatientLayout";
import DoctorLayout from "./pages/doctor/DoctorLayout";
import ReceptionLayout from "./pages/reception/ReceptionLayout";
import LoadingSpinner from "./components/common/LoadingSpinner";
import { useAuth } from "./state/AuthContext";
import { decodeJwt } from "./utils/jwt";

const STORAGE_KEY = "smarthospital_auth";

function readStoredAuth() {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (!stored) return null;
  try {
    return JSON.parse(stored);
  } catch {
    return null;
  }
}

function ProtectedRoute({ children, allowedRoles }) {
  const { user, token, isInitializing } = useAuth();
  if (isInitializing) return <LoadingSpinner label="Restoring session..." />;

  const stored = readStoredAuth();
  const effectiveUser = user || stored?.user || null;
  const effectiveToken = token || stored?.token || null;

  if (!effectiveUser) return <Navigate to="/login" replace />;
  if (!effectiveToken) {
    localStorage.removeItem(STORAGE_KEY);
    return <Navigate to="/login" replace />;
  }
  const payload = decodeJwt(effectiveToken);
  if (!payload?.role || payload.role !== effectiveUser.role) {
    localStorage.removeItem(STORAGE_KEY);
    return <Navigate to="/login" replace />;
  }
  if (allowedRoles && !allowedRoles.includes(effectiveUser.role)) {
    return (
      <Navigate
        to={`/${effectiveUser.role === "receptionist" ? "reception" : effectiveUser.role}`}
        replace
      />
    );
  }
  return children;
}

function RoleHomeRedirect() {
  const stored = readStoredAuth();
  const payload = decodeJwt(stored?.token);
  if (payload?.role === "doctor") return <Navigate to="/doctor" replace />;
  if (payload?.role === "receptionist") return <Navigate to="/reception" replace />;
  if (payload?.role === "patient") return <Navigate to="/patient" replace />;
  return <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RoleHomeRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        path="/patient/*"
        element={
          <ProtectedRoute allowedRoles={["patient"]}>
            <PatientLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/doctor/*"
        element={
          <ProtectedRoute allowedRoles={["doctor"]}>
            <DoctorLayout />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reception/*"
        element={
          <ProtectedRoute allowedRoles={["receptionist"]}>
            <ReceptionLayout />
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

