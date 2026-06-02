import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import toast from "react-hot-toast";
import api from "../../utils/api";
import { subscribeQueueUpdates } from "../../utils/realtime";

const REFRESH_MS = 5000;

export default function WaitingRoomScreen() {
  const { doctorId: routeDoctorId } = useParams();
  const [doctorId, setDoctorId] = useState(routeDoctorId || "");
  const [doctorName, setDoctorName] = useState("");
  const [screen, setScreen] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [clock, setClock] = useState(new Date());
  const shownErrorRef = useRef(false);

  const doctorIdNumber = useMemo(() => Number(doctorId), [doctorId]);

  const resolveDoctor = async () => {
    if (doctorIdNumber > 0) return String(doctorIdNumber);
    const response = await api.get("/auth/doctors");
    const doctors = response.data || [];
    if (!doctors.length) return "";
    return String(doctors[0].id);
  };

  const loadScreen = async (selectedDoctorId, initial = false) => {
    if (!selectedDoctorId) return;
    if (initial) setIsLoading(true);
    try {
      const response = await api.get(`/tokens/waiting-screen/${Number(selectedDoctorId)}`);
      setScreen(response.data);
      setDoctorName(response.data?.doctor_name || "");
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
      const resolved = await resolveDoctor();
      setDoctorId(resolved);
      await loadScreen(resolved, true);
    })();
  }, [routeDoctorId]);

  useEffect(() => {
    if (!doctorId) return undefined;
    const timer = setInterval(() => loadScreen(doctorId), REFRESH_MS);
    return () => clearInterval(timer);
  }, [doctorId]);

  useEffect(() => {
    const timer = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!doctorId) return undefined;
    const unsubscribe = subscribeQueueUpdates((event) => {
      if (event?.type === "appointment_update" || event?.type === "queue_update") {
        loadScreen(doctorId);
      }
    });
    return () => unsubscribe();
  }, [doctorId]);

  if (isLoading) {
    return (
      <div className="waiting-tv-page">
        <div className="waiting-tv-loading">Loading waiting screen...</div>
      </div>
    );
  }

  return (
    <div className="waiting-tv-page">
      <div className="waiting-tv-header">
        <div>
          <h1>{doctorName || "Doctor"}</h1>
          <p>Live Queue Display</p>
        </div>
        <div className="waiting-tv-time">{clock.toLocaleTimeString()}</div>
      </div>

      <div className="waiting-tv-main">
        <div className="waiting-tv-card">
          <span>Now Serving</span>
          <strong>{screen?.now_serving ? `Token ${screen.now_serving.token_number}` : "-"}</strong>
        </div>
        <div className="waiting-tv-card">
          <span>Next Token</span>
          <strong>{screen?.next_token ? `Token ${screen.next_token.token_number}` : "-"}</strong>
        </div>
      </div>

      <div className="waiting-tv-upcoming">
        {(screen?.upcoming_tokens || []).slice(0, 12).map((token) => (
          <div className="waiting-tv-item" key={token.id}>
            <span>#{token.token_number}</span>
            <span>{token.patient_name || "Patient"}</span>
          </div>
        ))}
        {!screen?.upcoming_tokens?.length ? <div className="waiting-tv-empty">No upcoming tokens</div> : null}
      </div>
    </div>
  );
}
