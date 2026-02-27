import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import api from "../../utils/api";
import { TextInput, Select } from "../../components/common/FormControls";
import StatCard from "../../components/common/StatCard";
import Table from "../../components/common/Table";
import { useAuth } from "../../state/AuthContext";
import { subscribeQueueUpdates } from "../../utils/realtime";

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
  const [doctors, setDoctors] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [currentStatus, setCurrentStatus] = useState(null);
  const [live, setLive] = useState(null);

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

  const loadLiveStatus = async (patientId) => {
    try {
      const res = await api.get(`/patient/live-status/${patientId}`);
      setLive(res.data);
      setCurrentStatus(res.data.patient);
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
      localStorage.setItem("smarthospital_patient_id", String(res.data.id));
      setForm({
        name: "",
        age: "",
        gender: "male",
        symptoms: "",
        priority: "normal",
        doctor_id: "",
      });
      await loadLiveStatus(res.data.id);
      await loadAppointments(res.data.id);
    } catch (e) {
      console.error(e);
      toast.error("Booking failed");
    }
  };

  useEffect(() => {
    // load doctor list for dropdown
    (async () => {
      try {
        const res = await api.get("/auth/doctors");
        setDoctors(res.data.map((d) => ({ value: d.id, label: d.name })));
      } catch (e) {
        console.error("Failed to load doctors", e);
      }
    })();

    const storedPatientId = localStorage.getItem("smarthospital_patient_id");
    if (storedPatientId) {
      const pid = Number(storedPatientId);
      if (!Number.isNaN(pid) && pid > 0) {
        loadLiveStatus(pid).catch(() => {});
        loadAppointments(pid).catch(() => {});
      }
    }
  }, []);

  // Short polling every 5 seconds (hackathon-safe).
  useEffect(() => {
    if (!currentStatus?.id) return undefined;
    const pid = currentStatus.id;
    const interval = setInterval(() => {
      loadLiveStatus(pid).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [currentStatus?.id]);

  // WebSocket sync: instant refresh when queue changes.
  useEffect(() => {
    if (!currentStatus?.id) return undefined;
    const unsubscribe = subscribeQueueUpdates((evt) => {
      if (evt?.type !== "queue_update") return;
      loadLiveStatus(currentStatus.id).catch(() => {});
    });
    return () => unsubscribe();
  }, [currentStatus?.id]);

  const nowServingToken =
    live?.current_token_queue_number != null ? live.current_token_queue_number : "-";
  const waitingCount = live?.waiting_count != null ? live.waiting_count : "-";

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
          <StatCard label="Now Serving" value={nowServingToken} />
          <StatCard label="Total Waiting (Doctor)" value={waitingCount} />
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
              <Select
                label="Doctor"
                value={form.doctor_id}
                onChange={(v) => handleChange("doctor_id", v)}
                options={doctors}
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

