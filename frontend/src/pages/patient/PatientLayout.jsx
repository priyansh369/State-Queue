import { Route, Routes } from "react-router-dom";
import Sidebar from "../../components/layout/Sidebar";
import Header from "../../components/layout/Header";
import PatientDashboard from "./PatientDashboard";

export default function PatientLayout() {
  const links = [
    { to: "/patient", label: "Dashboard" },
    { to: "/patient/book", label: "Book Appointment" },
  ];

  return (
    <div className="app-shell">
      <Sidebar links={links} />
      <main className="app-main">
        <Header />
        <div className="app-content">
          <Routes>
            <Route path="/" element={<PatientDashboard />} />
            <Route path="/book" element={<PatientDashboard showBooking />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

