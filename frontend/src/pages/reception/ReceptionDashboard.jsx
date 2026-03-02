import { useCallback, useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import { Select, TextInput } from "../../components/common/FormControls";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import StatCard from "../../components/common/StatCard";
import Table from "../../components/common/Table";
import api from "../../utils/api";

export default function ReceptionDashboard() {
  const [stats, setStats] = useState(null);
  const [queue, setQueue] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [form, setForm] = useState({
    name: "",
    age: "",
    gender: "male",
    contact_number: "",
    symptoms: "",
    priority: "normal",
    doctor_id: "",
  });
  const [doctorOptions, setDoctorOptions] = useState([]);
  const [filterDoctorOptions, setFilterDoctorOptions] = useState([]);
  const [filterDoctorId, setFilterDoctorId] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const filterDoctorIdRef = useRef("");
  const reconnectRef = useRef(null);

  const handleChange = (field, value) => setForm((prev) => ({ ...prev, [field]: value }));

  const loadStats = async () => {
    const response = await api.get("/reception/dashboard/stats");
    setStats(response.data);
  };

  const loadQueue = async () => {
    const currentFilter = filterDoctorIdRef.current;
    const response = await api.get(
      currentFilter ? `/reception/queue?doctor_id=${Number(currentFilter)}` : "/reception/queue"
    );
    setQueue(response.data);
  };

  const loadAuditLogs = async () => {
    const response = await api.get("/reception/audit-logs?limit=30");
    setAuditLogs(response.data);
  };

  const loadAll = useCallback(async ({ background = false } = {}) => {
    if (background) setIsRefreshing(true);
    else setIsLoading(true);
    try {
      await Promise.all([loadStats(), loadQueue(), loadAuditLogs()]);
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to load reception dashboard");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    filterDoctorIdRef.current = filterDoctorId;
  }, [filterDoctorId]);

  useEffect(() => {
    loadAll();
    (async () => {
      try {
        const response = await api.get("/reception/doctors");
        const registerOpts = response.data.map((doctor) => ({
          value: String(doctor.id),
          label: doctor.is_available ? doctor.name : `${doctor.name} (Unavailable)`,
          disabled: !doctor.is_available,
        }));
        const firstAvailableDoctor = registerOpts.find((opt) => !opt.disabled)?.value ?? "";
        setDoctorOptions(registerOpts);
        setForm((prev) => ({
          ...prev,
          doctor_id:
            (prev.doctor_id &&
              registerOpts.some((opt) => opt.value === prev.doctor_id && !opt.disabled) &&
              prev.doctor_id) ||
            firstAvailableDoctor,
        }));
        setFilterDoctorOptions([
          { value: "", label: "All doctors" },
          ...registerOpts.map((opt) => ({ value: opt.value, label: opt.label })),
        ]);
      } catch (error) {
        toast.error(error?.response?.data?.error?.message || "Failed to load doctors");
      }
    })();

    let socket = null;
    let closedByUser = false;
    const connect = () => {
      const wsUrl = import.meta.env.VITE_WS_URL || "ws://127.0.0.1:8000/ws";
      socket = new WebSocket(wsUrl);
      socket.onmessage = (evt) => {
        try {
          const message = JSON.parse(evt.data);
          if (message?.type !== "appointment_update" && message?.type !== "queue_update") return;
          const payload = message?.data;
          if (
            payload?.doctor_id &&
            filterDoctorIdRef.current &&
            Number(filterDoctorIdRef.current) !== Number(payload.doctor_id)
          ) {
            return;
          }
          loadAll({ background: true });
        } catch {
          // ignore bad payloads
        }
      };
      socket.onclose = () => {
        if (closedByUser) return;
        reconnectRef.current = setTimeout(connect, 3000);
      };
    };

    connect();
    return () => {
      closedByUser = true;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (socket && socket.readyState < 2) socket.close();
    };
  }, [loadAll]);

  useEffect(() => {
    loadQueue().catch(() => {});
  }, [filterDoctorId]);

  const handleRegister = async (event) => {
    event.preventDefault();
    if (!form.doctor_id) {
      toast.error("Please select a doctor");
      return;
    }
    try {
      await api.post("/reception/register-patient", {
        ...form,
        patient_name: form.name,
        age: Number(form.age),
        doctor_id: Number(form.doctor_id),
      });
      toast.success("Patient registered");
      setForm({
        name: "",
        age: "",
        gender: "male",
        contact_number: "",
        symptoms: "",
        priority: "normal",
        doctor_id: doctorOptions[0]?.value ?? "",
      });
      await loadAll({ background: true });
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Registration failed");
    }
  };

  const updatePriority = async (id, priority) => {
    try {
      await api.put(`/reception/update-priority/${id}`, { priority });
      toast.success("Priority updated");
      await loadAll({ background: true });
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to update priority");
    }
  };

  const cancel = async (id) => {
    try {
      await api.delete(`/reception/cancel/${id}`);
      toast.success("Appointment cancelled");
      await loadAll({ background: true });
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to cancel appointment");
    }
  };

  const transferPatient = async (id, currentDoctorId, nextDoctorId) => {
    const targetDoctorId = Number(nextDoctorId);
    if (!Number.isFinite(targetDoctorId) || targetDoctorId <= 0) return;
    if (Number(currentDoctorId) === targetDoctorId) return;
    try {
      await api.put(`/reception/transfer/${id}`, { doctor_id: targetDoctorId });
      toast.success("Patient transferred");
      await loadAll({ background: true });
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to transfer patient");
    }
  };

  const chartData = stats
    ? [
        { name: "Today", value: stats.total_patients_today },
        { name: "Avg Wait", value: stats.average_wait_minutes },
        { name: "Emerg %", value: stats.emergency_percentage },
        { name: "Completion %", value: stats.completion_rate },
      ]
    : [];

  if (isLoading) return <LoadingSpinner label="Loading reception dashboard..." />;

  return (
    <div className="panel">
      <div className="row-between">
        <h2>Reception Dashboard</h2>
        {isRefreshing ? <LoadingSpinner label="Refreshing..." /> : null}
      </div>

      <div className="grid-4">
        <StatCard label="Total" value={stats?.total_patients ?? "-"} />
        <StatCard label="Waiting" value={stats?.waiting ?? "-"} />
        <StatCard label="Emergency" value={stats?.emergency ?? "-"} accent="danger" />
        <StatCard label="Completed" value={stats?.completed ?? "-"} accent="success" />
      </div>

      <div className="grid-2 mt-lg">
        <div className="card">
          <h3>Register New Patient</h3>
          <form onSubmit={handleRegister}>
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
              options={doctorOptions}
            />
            <button className="primary-btn">Register</button>
          </form>
        </div>

        <div className="card">
          <h3>Analytics</h3>
          <BarChart width={380} height={220} data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="value" fill="#3182ce" />
          </BarChart>
        </div>
      </div>

      <div className="card mt-lg">
        <div className="row-between">
          <h3>Current Queue</h3>
          <div style={{ width: 260 }}>
            <Select
              label="View queue for"
              value={filterDoctorId}
              onChange={setFilterDoctorId}
              options={filterDoctorOptions}
            />
          </div>
        </div>
        <Table
          className="table-queue"
          rowKey="id"
          columns={[
            { key: "id", title: "ID", dataIndex: "id" },
            { key: "name", title: "Name", dataIndex: "name" },
            {
              key: "priority",
              title: "Priority",
              dataIndex: "priority",
              render: (value, row) => (
                <select value={value} onChange={(event) => updatePriority(row.id, event.target.value)}>
                  <option value="normal">Normal</option>
                  <option value="emergency">Emergency</option>
                </select>
              ),
            },
            {
              key: "waiting_minutes",
              title: "Waiting (min)",
              dataIndex: "waiting_minutes",
              render: (value, row) =>
                row.escalation_required ? <span className="blink-text">{value}</span> : value,
            },
            { key: "queue", title: "Queue #", dataIndex: "queue_number" },
            { key: "wait", title: "Est. Wait", dataIndex: "estimated_wait_minutes" },
            {
              key: "actions",
              title: "Actions",
              dataIndex: "id",
              render: (_, row) => (
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <select
                    value={String(row.doctor_id)}
                    onChange={(event) => transferPatient(row.id, row.doctor_id, event.target.value)}
                  >
                    {doctorOptions.map((opt) => (
                      <option key={`transfer-${row.id}-${opt.value}`} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                  <button className="danger-btn" onClick={() => cancel(row.id)}>
                    Cancel
                  </button>
                </div>
              ),
            },
          ]}
          data={queue}
        />
      </div>

      <div className="card mt-lg">
        <h3>Audit Logs</h3>
        <Table
          rowKey="id"
          columns={[
            { key: "id", title: "Log ID", dataIndex: "id" },
            { key: "user_id", title: "User ID", dataIndex: "user_id" },
            { key: "action", title: "Action", dataIndex: "action" },
            { key: "patient_id", title: "Patient ID", dataIndex: "patient_id" },
            { key: "timestamp", title: "Timestamp", dataIndex: "timestamp" },
          ]}
          data={auditLogs}
        />
      </div>
    </div>
  );
}
