import { useEffect, useMemo, useRef, useState } from "react";
import toast from "react-hot-toast";
import { Link } from "react-router-dom";
import { Select } from "../../components/common/FormControls";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import { subscribeQueueUpdates } from "../../utils/realtime";
import api from "../../utils/api";

const REFRESH_MS = 5000;

export default function WaitingScreenPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [doctors, setDoctors] = useState([]);
  const [doctorId, setDoctorId] = useState("");
  const [screen, setScreen] = useState(null);
  const shownErrorRef = useRef(false);

  const doctorOptions = useMemo(
    () => doctors.map((doctor) => ({ value: String(doctor.id), label: doctor.name })),
    [doctors]
  );

  const loadDoctors = async () => {
    const response = await api.get("/auth/doctors");
    const rows = response.data || [];
    setDoctors(rows);
    if (!doctorId && rows.length) setDoctorId(String(rows[0].id));
  };

  const loadScreen = async (selectedDoctorId, initial = false) => {
    if (!selectedDoctorId) return;
    if (initial) setIsLoading(true);
    try {
      const response = await api.get(`/tokens/waiting-screen/${Number(selectedDoctorId)}`);
      setScreen(response.data);
      shownErrorRef.current = false;
    } catch (error) {
      if (!shownErrorRef.current) {
        toast.error(error?.response?.data?.error?.message || "Failed to load waiting screen");
        shownErrorRef.current = true;
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    (async () => {
      try {
        await loadDoctors();
      } catch (error) {
        toast.error(error?.response?.data?.error?.message || "Failed to load doctors");
        setIsLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!doctorId) return;
    loadScreen(doctorId, true);
    const timer = setInterval(() => loadScreen(doctorId), REFRESH_MS);
    return () => clearInterval(timer);
  }, [doctorId]);

  useEffect(() => {
    if (!doctorId) return undefined;
    const unsubscribe = subscribeQueueUpdates((event) => {
      if (event?.type === "appointment_update" || event?.type === "queue_update") {
        loadScreen(doctorId);
      }
    });
    return () => unsubscribe();
  }, [doctorId]);

  if (isLoading) return <LoadingSpinner label="Loading waiting screen..." />;

  return (
    <div className="panel waiting-screen-wrap">
      <div className="row-between">
        <h2>Waiting Screen</h2>
        <div style={{ width: 300, display: "flex", gap: 10, alignItems: "end" }}>
          <div style={{ flex: 1 }}>
            <Select label="Doctor" value={doctorId} onChange={setDoctorId} options={doctorOptions} />
          </div>
          <Link className="secondary-btn" to={`/waiting-screen/${doctorId}`} target="_blank" rel="noreferrer">
            Open TV View
          </Link>
        </div>
      </div>

      <div className="waiting-screen-board">
        <div className="waiting-screen-header">
          <h1>{screen?.doctor_name || "Doctor"}</h1>
          <p>Auto refresh: every 5 seconds</p>
        </div>

        <div className="waiting-screen-metrics">
          <div className="waiting-metric">
            <span className="waiting-metric-label">Now Serving</span>
            <span className="waiting-metric-value">
              {screen?.now_serving ? `Token ${screen.now_serving.token_number}` : "-"}
            </span>
          </div>
          <div className="waiting-metric">
            <span className="waiting-metric-label">Next Token</span>
            <span className="waiting-metric-value">
              {screen?.next_token ? `Token ${screen.next_token.token_number}` : "-"}
            </span>
          </div>
        </div>

        <div className="waiting-upcoming">
          <h3>Upcoming Tokens</h3>
          <div className="waiting-upcoming-list">
            {(screen?.upcoming_tokens || []).map((token) => (
              <div className="waiting-upcoming-item" key={token.id}>
                <span className="waiting-upcoming-token">#{token.token_number}</span>
                <span className="waiting-upcoming-name">{token.patient_name || "Patient"}</span>
              </div>
            ))}
            {!screen?.upcoming_tokens?.length ? <div className="waiting-empty">No upcoming tokens</div> : null}
          </div>
        </div>
      </div>
    </div>
  );
}
