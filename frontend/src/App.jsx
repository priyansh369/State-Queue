import { Navigate, Route, Routes } from "react-router-dom";
import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";
import PatientLayout from "./pages/patient/PatientLayout";
import DoctorLayout from "./pages/doctor/DoctorLayout";
import ReceptionLayout from "./pages/reception/ReceptionLayout";
import { useAuth } from "./state/AuthContext";
import { decodeJwt, isTokenExpired } from "./utils/jwt";

function ProtectedRoute({ children, allowedRoles }) {
  const { user, token } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!token || isTokenExpired(token)) {
    return <Navigate to="/login" replace />;
  }
  const payload = decodeJwt(token);
  if (!payload?.role || payload.role !== user.role) {
    return <Navigate to="/login" replace />;
  }
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return <Navigate to={`/${user.role === "receptionist" ? "reception" : user.role}`} replace />;
  }
  return children;
}

export default function App() {
  return (
    <Routes>
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

