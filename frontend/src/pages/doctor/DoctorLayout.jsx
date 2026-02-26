import { Route, Routes } from "react-router-dom";
import Sidebar from "../../components/layout/Sidebar";
import Header from "../../components/layout/Header";
import DoctorDashboard from "./DoctorDashboard";

export default function DoctorLayout() {
  const links = [{ to: "/doctor", label: "Today&apos;s Queue" }];
  return (
    <div className="app-shell">
      <Sidebar links={links} />
      <main className="app-main">
        <Header />
        <div className="app-content">
          <Routes>
            <Route path="/" element={<DoctorDashboard />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

