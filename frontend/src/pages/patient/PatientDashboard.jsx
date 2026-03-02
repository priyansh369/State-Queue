import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { Select, TextInput } from "../../components/common/FormControls";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import StatCard from "../../components/common/StatCard";
import Table from "../../components/common/Table";
import { subscribeQueueUpdates } from "../../utils/realtime";
import api from "../../utils/api";

const REFRESH_INTERVAL = 30000;

export default function PatientDashboard({ showBooking }) {
  const [form, setForm] = useState({
    name: "",
    age: "",
    gender: "male",
    contact_number: "",
    symptoms: "",
    priority: "normal",
    doctor_id: "",
  });
  const [doctors, setDoctors] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [currentStatus, setCurrentStatus] = useState(null);
  const [live, setLive] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [clockMs, setClockMs] = useState(Date.now());
  const [statusSyncedAtMs, setStatusSyncedAtMs] = useState(Date.now());

  const handleChange = (field, value) => setForm((prev) => ({ ...prev, [field]: value }));

  const formatWait = (seconds, minutesFallback = 0, mode = "up", active = true) => {
    const base = Number.isFinite(Number(seconds))
      ? Number(seconds)
      : Number(minutesFallback || 0) * 60;
    const elapsed = active ? Math.max(0, Math.floor((clockMs - statusSyncedAtMs) / 1000)) : 0;
    const total = mode === "down" ? Math.max(0, base - elapsed) : base + elapsed;
    const mm = Math.floor(total / 60);
    const ss = total % 60;
    return `${mm}:${String(ss).padStart(2, "0")}`;
  };

  const loadAppointments = async (patientId) => {
    const response = await api.get(`/patient/appointments/${patientId}`);
    setAppointments(response.data);
  };

  const loadLiveStatus = async (patientId) => {
    const response = await api.get(`/patient/live-status/${patientId}`);
    setLive(response.data);
    setCurrentStatus(response.data.patient);
    setStatusSyncedAtMs(Date.now());
  };

  const loadCurrentPatientData = async ({ background = false } = {}) => {
    if (background) setIsRefreshing(true);
    else setIsLoading(true);
    try {
      const storedPatientId = localStorage.getItem("smarthospital_patient_id");
      const patientId = Number(storedPatientId);
      if (!Number.isFinite(patientId) || patientId <= 0) {
        setCurrentStatus(null);
        setLive(null);
        setAppointments([]);
        return;
      }
      await Promise.all([loadLiveStatus(patientId), loadAppointments(patientId)]);
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to refresh patient data");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    const interval = setInterval(() => setClockMs(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const response = await api.get("/auth/doctors");
        const doctorOptions = response.data.map((doctor) => ({
          value: String(doctor.id),
          label: doctor.name,
        }));
        setDoctors(doctorOptions);
        setForm((prev) => ({
          ...prev,
          doctor_id: prev.doctor_id || (doctorOptions[0]?.value ?? ""),
        }));
      } catch (error) {
        toast.error(error?.response?.data?.error?.message || "Failed to load doctors");
      }
    })();
    loadCurrentPatientData();
  }, []);

  useEffect(() => {
    if (!currentStatus?.id) return undefined;
    const interval = setInterval(() => {
      loadCurrentPatientData({ background: true });
    }, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [currentStatus?.id]);

  useEffect(() => {
    if (!currentStatus?.id) return undefined;
    const unsubscribe = subscribeQueueUpdates((event) => {
      if (event?.type === "appointment_update" || event?.type === "queue_update") {
        loadCurrentPatientData({ background: true });
      }
    });
    return () => unsubscribe();
  }, [currentStatus?.id]);

  const handleBook = async (event) => {
    event.preventDefault();
    if (!form.doctor_id) {
      toast.error("Please select a doctor");
      return;
    }
    try {
      const payload = {
        ...form,
        patient_name: form.name,
        age: Number(form.age),
        doctor_id: Number(form.doctor_id),
      };
      const response = await api.post("/patient/book", payload);
      toast.success(`Booked successfully with queue #${response.data.queue_number}`);
      localStorage.setItem("smarthospital_patient_id", String(response.data.id));
      setForm({
        name: "",
        age: "",
        gender: "male",
        contact_number: "",
        symptoms: "",
        priority: "normal",
        doctor_id: doctors[0]?.value ?? "",
      });
      await loadCurrentPatientData({ background: true });
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Booking failed");
    }
  };

  if (isLoading) return <LoadingSpinner label="Loading patient dashboard..." />;
  const isWaiting = currentStatus?.status === "waiting";

  return (
    <div className="panel">
      <div className="row-between">
        <h2>Patient Dashboard</h2>
        {isRefreshing ? <LoadingSpinner label="Refreshing..." /> : null}
      </div>
      <div className="grid-2">
        <div>
          <StatCard label="Queue Number" value={currentStatus ? currentStatus.queue_number : "-"} />
          <StatCard label="Status" value={currentStatus ? currentStatus.status : "-"} />
          <StatCard
            label="Estimated Wait"
            value={
              currentStatus
                ? formatWait(
                    currentStatus.estimated_wait_minutes * 60,
                    currentStatus.estimated_wait_minutes,
                    "down",
                    isWaiting
                  )
                : "0:00"
            }
          />
          <StatCard
            label="Waiting Time"
            value={
              currentStatus
                ? formatWait(currentStatus.waiting_seconds, currentStatus.waiting_minutes, "up", isWaiting)
                : "0:00"
            }
          />
          <StatCard
            label="Now Serving"
            value={live?.current_token_queue_number != null ? live.current_token_queue_number : "-"}
          />
          <StatCard label="Total Waiting (Doctor)" value={live?.waiting_count ?? "-"} />
        </div>
        {showBooking ? (
          <div className="card">
            <h3>Book Appointment</h3>
            <form onSubmit={handleBook}>
              <TextInput label="Name" value={form.name} onChange={(value) => handleChange("name", value)} />
              <TextInput
                label="Age"
                value={form.age}
                onChange={(value) => handleChange("age", value)}
                type="number"
              />
              <TextInput
                label="Contact Number"
                value={form.contact_number}
                onChange={(value) => handleChange("contact_number", value)}
                placeholder="+919876543210"
              />
              <Select
                label="Gender"
                value={form.gender}
                onChange={(value) => handleChange("gender", value)}
                options={[
                  { value: "male", label: "Male" },
                  { value: "female", label: "Female" },
                  { value: "other", label: "Other" },
                ]}
              />
              <TextInput
                label="Symptoms"
                value={form.symptoms}
                onChange={(value) => handleChange("symptoms", value)}
              />
              <Select
                label="Priority"
                value={form.priority}
                onChange={(value) => handleChange("priority", value)}
                options={[
                  { value: "normal", label: "Normal" },
                  { value: "emergency", label: "Emergency" },
                ]}
              />
              <Select
                label="Doctor"
                value={form.doctor_id}
                onChange={(value) => handleChange("doctor_id", value)}
                options={doctors}
              />
              <button className="primary-btn">Book Appointment</button>
            </form>
          </div>
        ) : null}
      </div>

      <div className="card mt-lg">
        <h3>Appointments</h3>
        <Table
          rowKey="id"
          columns={[
            { key: "id", title: "ID", dataIndex: "id" },
            { key: "date", title: "Date", dataIndex: "appointment_date" },
            {
              key: "status",
              title: "Status",
              dataIndex: "status",
              render: (value) => (
                <span className={`status-pill status-${String(value || "").toLowerCase()}`}>
                  {value}
                </span>
              ),
            },
          ]}
          data={appointments}
        />
      </div>
    </div>
  );
}
