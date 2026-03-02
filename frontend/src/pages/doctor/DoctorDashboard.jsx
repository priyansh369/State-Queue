import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import toast from "react-hot-toast";
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from "recharts";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import Modal from "../../components/common/Modal";
import StatCard from "../../components/common/StatCard";
import Table from "../../components/common/Table";
import { useAuth } from "../../state/AuthContext";
import api from "../../utils/api";

export default function DoctorDashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [queue, setQueue] = useState([]);
  const [selected, setSelected] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isAvailable, setIsAvailable] = useState(true);
  const [isUpdatingAvailability, setIsUpdatingAvailability] = useState(false);
  const [clockMs, setClockMs] = useState(Date.now());
  const [queueSyncedAtMs, setQueueSyncedAtMs] = useState(Date.now());

  const formatWait = (seconds, minutesFallback = 0) => {
    const base = Number.isFinite(Number(seconds))
      ? Number(seconds)
      : Number(minutesFallback || 0) * 60;
    const elapsed = Math.max(0, Math.floor((clockMs - queueSyncedAtMs) / 1000));
    const total = base + elapsed;
    const mm = Math.floor(total / 60);
    const ss = total % 60;
    return `${mm}:${String(ss).padStart(2, "0")}`;
  };

  const reconnectRef = useRef(null);

  const loadAll = useCallback(async ({ background = false } = {}) => {
    if (background) setIsRefreshing(true);
    else setIsLoading(true);
    try {
      const [statsRes, queueRes, availabilityRes] = await Promise.all([
        api.get("/doctor/dashboard/stats"),
        api.get("/doctor/queue"),
        api.get("/doctor/availability"),
      ]);
      setStats(statsRes.data);
      setQueue(queueRes.data);
      setQueueSyncedAtMs(Date.now());
      setIsAvailable(Boolean(availabilityRes.data?.is_available));
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to load doctor dashboard");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  useEffect(() => {
    const interval = setInterval(() => setClockMs(Date.now()), 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
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
          if (!payload) return;
          if (payload.doctor_id && Number(payload.doctor_id) !== Number(user?.id)) return;
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
  }, [loadAll, user?.id]);

  const startServing = async (id) => {
    try {
      await api.put(`/doctor/start/${id}`);
      toast.success("Started serving");
      await loadAll({ background: true });
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to start patient");
    }
  };

  const markCompleted = async (id) => {
    try {
      await api.put(`/doctor/complete/${id}`);
      toast.success("Marked as completed");
      setSelected(null);
      await loadAll({ background: true });
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to complete patient");
    }
  };

  const nowServing = queue.length ? queue[0] : null;
  const toggleAvailability = async () => {
    try {
      setIsUpdatingAvailability(true);
      const response = await api.put("/doctor/availability", { is_available: !isAvailable });
      setIsAvailable(Boolean(response.data?.is_available));
      toast.success(
        response.data?.is_available ? "You are marked available" : "You are marked unavailable"
      );
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to update availability");
    } finally {
      setIsUpdatingAvailability(false);
    }
  };
  const chartData = useMemo(
    () =>
      stats
        ? [
            { name: "Today", value: stats.total_patients_today },
            { name: "Avg Wait", value: stats.average_wait_minutes },
            { name: "Emerg %", value: stats.emergency_percentage },
            { name: "Completion %", value: stats.completion_rate },
          ]
        : [],
    [stats]
  );

  if (isLoading) return <LoadingSpinner label="Loading doctor dashboard..." />;

  return (
    <div className="panel">
      <div className="row-between">
        <h2>Doctor Dashboard</h2>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span className={isAvailable ? "pill" : "pill pill-danger"}>
            {isAvailable ? "Available" : "Unavailable"}
          </span>
          <button className="secondary-btn" onClick={toggleAvailability} disabled={isUpdatingAvailability}>
            {isUpdatingAvailability
              ? "Updating..."
              : isAvailable
              ? "Go Unavailable"
              : "Go Available"}
          </button>
          {isRefreshing ? <LoadingSpinner label="Refreshing..." /> : null}
        </div>
      </div>

      {stats?.overdue_emergencies > 0 ? (
        <div className="alert-banner">
          Emergency Alert: {stats.overdue_emergencies} emergency patient(s) waiting over 10 minutes
        </div>
      ) : null}

      <div className="grid-4">
        <StatCard label="Total Patients" value={stats?.total_patients ?? "-"} />
        <StatCard label="Waiting" value={stats?.waiting ?? "-"} />
        <StatCard label="Emergency" value={stats?.emergency ?? "-"} accent="danger" />
        <StatCard label="Completed" value={stats?.completed ?? "-"} accent="success" />
      </div>

      <div className="grid-2 mt-lg">
        <div className="card">
          <h3>Now Serving</h3>
          {nowServing ? (
            <div className="token-now">
              <div className="token-now-main">
                <div className="token-number">#{nowServing.queue_number}</div>
                <div>
                  <div className="token-name">{nowServing.name}</div>
                  <div className="token-meta">
                    <span
                      className={
                        nowServing.priority === "emergency" ? "pill pill-danger" : "pill"
                      }
                    >
                      {nowServing.priority}
                    </span>
                    <span className="token-wait">Est: {nowServing.estimated_wait_minutes} min</span>
                  </div>
                </div>
              </div>
              <div style={{ marginLeft: "auto" }}>
                <button className="primary-btn" onClick={() => startServing(nowServing.id)}>
                  Start
                </button>{" "}
                <button className="danger-btn" onClick={() => markCompleted(nowServing.id)}>
                  Complete
                </button>
              </div>
            </div>
          ) : (
            <p>No waiting patients.</p>
          )}
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
        <h3>Queue</h3>
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
                <span
                  className={
                    row.escalation_required
                      ? "pill pill-danger blink"
                      : value === "emergency"
                      ? "pill pill-danger"
                      : "pill"
                  }
                >
                  {value}
                </span>
              ),
            },
            { key: "queue_number", title: "Queue #", dataIndex: "queue_number" },
            { key: "wait", title: "Est. Wait", dataIndex: "estimated_wait_minutes" },
            {
              key: "waiting_seconds",
              title: "Waiting",
              dataIndex: "waiting_seconds",
              render: (value, row) => formatWait(value, row.waiting_minutes),
            },
            {
              key: "actions",
              title: "Actions",
              dataIndex: "id",
              render: (_, row) => (
                <button className="secondary-btn" onClick={() => setSelected(row)}>
                  View
                </button>
              ),
            },
          ]}
          data={queue}
        />
      </div>

      <Modal open={!!selected} title={selected ? `Patient #${selected.id}` : ""} onClose={() => setSelected(null)}>
        {selected ? (
          <>
            <p>
              <strong>Name:</strong> {selected.name}
            </p>
            <p>
              <strong>Symptoms:</strong> {selected.symptoms}
            </p>
            <p>
              <strong>Priority:</strong> {selected.priority}
            </p>
            <p>
              <strong>Queue #:</strong> {selected.queue_number}
            </p>
            <p>
              <strong>Waiting:</strong> {formatWait(selected.waiting_seconds, selected.waiting_minutes)}
            </p>
            <button className="primary-btn" onClick={() => startServing(selected.id)}>
              Start Serving
            </button>{" "}
            <button className="danger-btn" onClick={() => markCompleted(selected.id)}>
              Mark Completed
            </button>
          </>
        ) : null}
      </Modal>
    </div>
  );
}
