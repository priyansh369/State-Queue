import { Route, Routes } from "react-router-dom";
import Sidebar from "../../components/layout/Sidebar";
import Header from "../../components/layout/Header";
import ReceptionDashboard from "./ReceptionDashboard";

export default function ReceptionLayout() {
  const links = [{ to: "/reception", label: "Queue & Registration" }];
  return (
    <div className="app-shell">
      <Sidebar links={links} />
      <main className="app-main">
        <Header />
        <div className="app-content">
          <Routes>
            <Route path="/" element={<ReceptionDashboard />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

