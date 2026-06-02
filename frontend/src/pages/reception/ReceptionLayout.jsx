import { Route, Routes } from "react-router-dom";
import AppShell from "../../components/layout/AppShell";
import ReceptionDashboard from "./ReceptionDashboard";
import TokensPage from "./TokensPage";
import WaitingScreenPage from "./WaitingScreenPage";

export default function ReceptionLayout() {
  const links = [
    { to: "/reception", label: "Queue & Registration" },
    { to: "/reception/tokens", label: "Tokens" },
    { to: "/reception/waiting-screen", label: "Waiting Screen" },
  ];
  return (
    <AppShell links={links}>
      <Routes>
        <Route index element={<ReceptionDashboard />} />
        <Route path="tokens" element={<TokensPage />} />
        <Route path="waiting-screen" element={<WaitingScreenPage />} />
      </Routes>
    </AppShell>
  );
}

