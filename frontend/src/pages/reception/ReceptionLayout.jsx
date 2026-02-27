import { Route, Routes } from "react-router-dom";
import AppShell from "../../components/layout/AppShell";
import ReceptionDashboard from "./ReceptionDashboard";

export default function ReceptionLayout() {
  const links = [{ to: "/reception", label: "Queue & Registration" }];
  return (
    <AppShell links={links}>
      <Routes>
        <Route path="/" element={<ReceptionDashboard />} />
      </Routes>
    </AppShell>
  );
}

