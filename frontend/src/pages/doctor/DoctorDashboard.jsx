import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import api from "../../utils/api";
import StatCard from "../../components/common/StatCard";
import Table from "../../components/common/Table";
import Modal from "../../components/common/Modal";

export default function DoctorDashboard() {
  const [stats, setStats] = useState(null);
  const [queue, setQueue] = useState([]);
  const [selected, setSelected] = useState(null);

  const loadStats = async () => {
    const res = await api.get("/doctor/dashboard/stats");
    setStats(res.data);
  };

  const loadQueue = async () => {
    const res = await api.get("/doctor/queue");
    setQueue(res.data);
  };

  useEffect(() => {
    loadStats();
    loadQueue();
  }, []);

  // Keep dashboard in sync with actions from reception/patient by polling
  // and reloading when the window regains focus.
  useEffect(() => {
    const interval = setInterval(() => {
      loadStats().catch(() => {});
      loadQueue().catch(() => {});
    }, 8000); // refresh every 8s

    const onFocus = () => {
      loadStats().catch(() => {});
      loadQueue().catch(() => {});
    };
    window.addEventListener("focus", onFocus);

    return () => {
      clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, []);

  const markCompleted = async (id) => {
    try {
      await api.put(`/doctor/complete/${id}`);
      toast.success("Marked as completed");
      setSelected(null);
      await loadStats();
      await loadQueue();
    } catch (e) {
      console.error(e);
      toast.error("Failed to update");
    }
  };

  return (
    <div className="panel">
      <h2>Doctor Dashboard</h2>
      <div className="grid-4">
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
        <StatCard
          label="Completed"
          value={stats ? stats.completed : "-"}
          accent="success"
        />
      </div>

      <div className="card mt-lg">
        <h3>Today's Queue</h3>
        <Table
          rowKey="id"
          columns={[
            { key: "id", title: "ID", dataIndex: "id" },
            { key: "name", title: "Name", dataIndex: "name" },
            {
              key: "priority",
              title: "Priority",
              dataIndex: "priority",
              render: (val) => (
                <span className={val === "emergency" ? "pill pill-danger" : "pill"}>
                  {val}
                </span>
              ),
            },
            {
              key: "queue_number",
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
                <button onClick={() => setSelected(row)}>View</button>
              ),
            },
          ]}
          data={queue}
        />
      </div>

      <Modal
        open={!!selected}
        title={selected ? `Patient #${selected.id}` : ""}
        onClose={() => setSelected(null)}
      >
        {selected && (
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
              <strong>Est. Wait:</strong> {selected.estimated_wait_minutes} min
            </p>
            <button
              className="primary-btn"
              onClick={() => markCompleted(selected.id)}
            >
              Mark Completed
            </button>
          </>
        )}
      </Modal>
    </div>
  );
}

