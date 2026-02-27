import { Route, Routes } from "react-router-dom";
import AppShell from "../../components/layout/AppShell";
import PatientDashboard from "./PatientDashboard";

export default function PatientLayout() {
  const links = [
    { to: "/patient", label: "Dashboard" },
    { to: "/patient/book", label: "Book Appointment" },
  ];

  return (
    <AppShell links={links}>
      <Routes>
        <Route path="/" element={<PatientDashboard />} />
        <Route path="/book" element={<PatientDashboard showBooking />} />
      </Routes>
    </AppShell>
  );
}

