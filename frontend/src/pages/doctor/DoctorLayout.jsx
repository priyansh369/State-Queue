import { Route, Routes } from "react-router-dom";
import AppShell from "../../components/layout/AppShell";
import DoctorDashboard from "./DoctorDashboard";

export default function DoctorLayout() {
  const links = [{ to: "/doctor", label: "Today's Queue" }];
  return (
    <AppShell links={links}>
      <Routes>
        <Route index element={<DoctorDashboard />} />
      </Routes>
    </AppShell>
  );
}

