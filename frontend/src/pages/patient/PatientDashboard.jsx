import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import api from "../../utils/api";
import { TextInput, Select } from "../../components/common/FormControls";
import StatCard from "../../components/common/StatCard";
import Table from "../../components/common/Table";
import { useAuth } from "../../state/AuthContext";

export default function PatientDashboard({ showBooking }) {
  const { user } = useAuth();
  const [form, setForm] = useState({
    name: "",
    age: "",
    gender: "male",
    symptoms: "",
    priority: "normal",
    doctor_id: "",
  });
  const [appointments, setAppointments] = useState([]);
  const [currentStatus, setCurrentStatus] = useState(null);

  const handleChange = (field, value) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const loadAppointments = async (patientId) => {
    try {
      const res = await api.get(`/patient/appointments/${patientId}`);
      setAppointments(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  const loadStatus = async (patientId) => {
    try {
      const res = await api.get(`/patient/status/${patientId}`);
      setCurrentStatus(res.data);
    } catch (e) {
      console.error(e);
    }
  };

  const handleBook = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...form,
        age: Number(form.age),
        doctor_id: Number(form.doctor_id),
      };
      const res = await api.post("/patient/book", payload);
      toast.success(
        `Booked. Queue #${res.data.queue_number}, status ${res.data.status}`
      );
      setForm({
        name: "",
        age: "",
        gender: "male",
        symptoms: "",
        priority: "normal",
        doctor_id: "",
      });
      await loadStatus(res.data.id);
      await loadAppointments(res.data.id);
    } catch (e) {
      console.error(e);
      toast.error("Booking failed");
    }
  };

  useEffect(() => {
    if (currentStatus?.id) {
      loadAppointments(currentStatus.id);
    }
  }, []);

  return (
    <div className="panel">
      <h2>Patient Dashboard</h2>
      <div className="grid-2">
        <div>
          <StatCard
            label="Queue Number"
            value={currentStatus ? currentStatus.queue_number : "-"}
          />
          <StatCard
            label="Status"
            value={currentStatus ? currentStatus.status : "-"}
          />
          <StatCard
            label="Estimated Wait (min)"
            value={
              currentStatus ? currentStatus.estimated_wait_minutes : "-"
            }
          />
        </div>
        {showBooking && (
          <div className="card">
            <h3>Book Appointment</h3>
            <form onSubmit={handleBook}>
              <TextInput
                label="Name"
                value={form.name}
                onChange={(v) => handleChange("name", v)}
              />
              <TextInput
                label="Age"
                value={form.age}
                onChange={(v) => handleChange("age", v)}
                type="number"
              />
              <Select
                label="Gender"
                value={form.gender}
                onChange={(v) => handleChange("gender", v)}
                options={[
                  { value: "male", label: "Male" },
                  { value: "female", label: "Female" },
                  { value: "other", label: "Other" },
                ]}
              />
              <TextInput
                label="Symptoms"
                value={form.symptoms}
                onChange={(v) => handleChange("symptoms", v)}
              />
              <Select
                label="Priority"
                value={form.priority}
                onChange={(v) => handleChange("priority", v)}
                options={[
                  { value: "normal", label: "Normal" },
                  { value: "emergency", label: "Emergency" },
                ]}
              />
              <TextInput
                label="Doctor ID"
                value={form.doctor_id}
                onChange={(v) => handleChange("doctor_id", v)}
                type="number"
              />
              <button className="primary-btn">Book Appointment</button>
            </form>
          </div>
        )}
      </div>

      <div className="card mt-lg">
        <h3>Appointments</h3>
        <Table
          rowKey="id"
          columns={[
            { key: "id", title: "ID", dataIndex: "id" },
            {
              key: "date",
              title: "Date",
              dataIndex: "appointment_date",
            },
            { key: "status", title: "Status", dataIndex: "status" },
          ]}
          data={appointments}
        />
      </div>
    </div>
  );
}

