import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import api from "../../utils/api";
import { Select, TextInput } from "../../components/common/FormControls";
import StatCard from "../../components/common/StatCard";
import Table from "../../components/common/Table";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";

export default function ReceptionDashboard() {
  const [stats, setStats] = useState(null);
  const [queue, setQueue] = useState([]);
  const [form, setForm] = useState({
    name: "",
    age: "",
    gender: "male",
    symptoms: "",
    priority: "normal",
    doctor_id: "",
  });
  const [doctors, setDoctors] = useState([]);

  const handleChange = (field, value) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const loadStats = async () => {
    const res = await api.get("/reception/dashboard/stats");
    setStats(res.data);
  };

  const loadQueue = async () => {
    const res = await api.get("/reception/queue");
    setQueue(res.data);
  };

  useEffect(() => {
    loadStats();
    loadQueue();

    // fetch doctors for dropdown
    (async () => {
      try {
        const res = await api.get("/auth/doctors");
        setDoctors(res.data.map((d) => ({ value: d.id, label: d.name })));
      } catch (e) {
        console.error("Failed to load doctors", e);
      }
    })();
  }, []);

  const handleRegister = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        ...form,
        age: Number(form.age),
        doctor_id: Number(form.doctor_id),
      };
      await api.post("/reception/register-patient", payload);
      toast.success("Patient registered");
      setForm({
        name: "",
        age: "",
        gender: "male",
        symptoms: "",
        priority: "normal",
        doctor_id: "",
      });
      await loadStats();
      await loadQueue();
    } catch (e) {
      console.error(e);
      toast.error("Registration failed");
    }
  };

  const updatePriority = async (id, priority) => {
    try {
      await api.put(`/reception/update-priority/${id}`, { priority });
      toast.success("Priority updated");
      await loadStats();
      await loadQueue();
    } catch (e) {
      console.error(e);
      toast.error("Failed to update");
    }
  };

  const cancel = async (id) => {
    try {
      await api.delete(`/reception/cancel/${id}`);
      toast.success("Cancelled");
      await loadStats();
      await loadQueue();
    } catch (e) {
      console.error(e);
      toast.error("Failed to cancel");
    }
  };

  const chartData = stats
    ? [
        { name: "Total", value: stats.total_patients },
        { name: "Waiting", value: stats.waiting },
        { name: "Emergency", value: stats.emergency },
        { name: "Completed", value: stats.completed },
      ]
    : [];

  return (
    <div className="panel">
      <h2>Reception Dashboard</h2>
      <div className="grid-3">
        <StatCard
          label="Total Patients"
          value={stats ? stats.total_patients : "-"}
        />
        <StatCard label="Waiting" value={stats ? stats.waiting : "-"} />
        <StatCard
          label="Emergency"
          value={stats ? stats.emergency : "-"}
          accent="danger"
        />
      </div>

      <div className="grid-2 mt-lg">
        <div className="card">
          <h3>Register New Patient</h3>
          <form onSubmit={handleRegister}>
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
            <button className="primary-btn">Register</button>
          </form>
        </div>

        <div className="card">
          <h3>Overview</h3>
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
        <h3>Current Queue</h3>
        <Table
          rowKey="id"
          columns={[
            { key: "id", title: "ID", dataIndex: "id" },
            { key: "name", title: "Name", dataIndex: "name" },
            {
              key: "priority",
              title: "Priority",
              dataIndex: "priority",
              render: (val, row) => (
                <select
                  value={val}
                  onChange={(e) =>
                    updatePriority(row.id, e.target.value)
                  }
                >
                  <option value="normal">Normal</option>
                  <option value="emergency">Emergency</option>
                </select>
              ),
            },
            {
              key: "queue",
              title: "Queue #",
              dataIndex: "queue_number",
            },
            {
              key: "wait",
              title: "Est. Wait (min)",
              dataIndex: "estimated_wait_minutes",
            },
            {
              key: "actions",
              title: "Actions",
              dataIndex: "id",
              render: (_, row) => (
                <button className="danger-btn" onClick={() => cancel(row.id)}>
                  Cancel
                </button>
              ),
            },
          ]}
          data={queue}
        />
      </div>
    </div>
  );
}

