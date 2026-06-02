import { useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { Select } from "../../components/common/FormControls";
import LoadingSpinner from "../../components/common/LoadingSpinner";
import Table from "../../components/common/Table";
import api from "../../utils/api";

const REFRESH_MS = 5000;

export default function TokensPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [isWorking, setIsWorking] = useState(false);
  const [doctors, setDoctors] = useState([]);
  const [doctorId, setDoctorId] = useState("");
  const [tokens, setTokens] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [candidatePatientId, setCandidatePatientId] = useState("");

  const doctorOptions = useMemo(
    () => doctors.map((doctor) => ({ value: String(doctor.id), label: doctor.name })),
    [doctors]
  );

  const candidateOptions = useMemo(
    () =>
      candidates.map((patient) => ({
        value: String(patient.id),
        label: `${patient.name} (Patient #${patient.id})`,
      })),
    [candidates]
  );

  const loadDoctors = async () => {
    const response = await api.get("/reception/doctors?include_unavailable=true");
    const rows = response.data || [];
    setDoctors(rows);
    if (!doctorId && rows.length) {
      setDoctorId(String(rows[0].id));
    }
  };

  const loadTokens = async (selectedDoctorId) => {
    if (!selectedDoctorId) return;
    const response = await api.get(`/tokens?doctor_id=${Number(selectedDoctorId)}`);
    setTokens(response.data || []);
  };

  const loadCandidates = async (selectedDoctorId) => {
    if (!selectedDoctorId) return;
    const response = await api.get(`/tokens/generation-candidates?doctor_id=${Number(selectedDoctorId)}`);
    const rows = response.data || [];
    setCandidates(rows);
    if (!rows.length) setCandidatePatientId("");
    else if (!rows.some((row) => String(row.id) === candidatePatientId)) {
      setCandidatePatientId(String(rows[0].id));
    }
  };

  const loadAll = async (selectedDoctorId, initial = false) => {
    if (!selectedDoctorId) return;
    if (initial) setIsLoading(true);
    try {
      await Promise.all([loadTokens(selectedDoctorId), loadCandidates(selectedDoctorId)]);
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to load tokens");
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
    loadAll(doctorId, true);
    const timer = setInterval(() => loadAll(doctorId), REFRESH_MS);
    return () => clearInterval(timer);
  }, [doctorId]);

  const generateToken = async () => {
    if (!doctorId || !candidatePatientId) {
      toast.error("Select doctor and patient");
      return;
    }
    try {
      setIsWorking(true);
      await api.post("/tokens/generate", {
        patient_id: Number(candidatePatientId),
        doctor_id: Number(doctorId),
      });
      toast.success("Token generated");
      await loadAll(doctorId);
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to generate token");
    } finally {
      setIsWorking(false);
    }
  };

  const callNext = async () => {
    if (!doctorId) return;
    try {
      setIsWorking(true);
      await api.post(`/tokens/call-next?doctor_id=${Number(doctorId)}`);
      toast.success("Next token called");
      await loadAll(doctorId);
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to call next");
    } finally {
      setIsWorking(false);
    }
  };

  const completeToken = async (tokenId) => {
    try {
      setIsWorking(true);
      await api.post(`/tokens/${tokenId}/complete`);
      toast.success("Consultation marked complete");
      await loadAll(doctorId);
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to complete token");
    } finally {
      setIsWorking(false);
    }
  };

  if (isLoading) return <LoadingSpinner label="Loading token system..." />;

  return (
    <div className="panel">
      <h2>OPD Tokens</h2>
      <div className="card">
        <div className="grid-3">
          <Select label="Doctor" value={doctorId} onChange={setDoctorId} options={doctorOptions} />
          <Select
            label="Patient (Waiting)"
            value={candidatePatientId}
            onChange={setCandidatePatientId}
            options={candidateOptions.length ? candidateOptions : [{ value: "", label: "No patients waiting" }]}
          />
          <div className="token-actions">
            <button className="primary-btn" onClick={generateToken} disabled={isWorking || !candidatePatientId}>
              Generate Token
            </button>
            <button className="secondary-btn" onClick={callNext} disabled={isWorking}>
              Call Next Token
            </button>
          </div>
        </div>
      </div>

      <div className="card mt-lg">
        <h3>Doctor Token Queue</h3>
        <Table
          rowKey="id"
          columns={[
            { key: "token_number", title: "Token", dataIndex: "token_number" },
            { key: "patient_name", title: "Patient", dataIndex: "patient_name" },
            {
              key: "status",
              title: "Status",
              dataIndex: "status",
              render: (value) => <span className={`status-pill status-${String(value || "").toLowerCase()}`}>{value}</span>,
            },
            { key: "created_at", title: "Created At", dataIndex: "created_at" },
            {
              key: "actions",
              title: "Actions",
              dataIndex: "id",
              render: (_, row) =>
                row.status === "in_progress" ? (
                  <button className="danger-btn" onClick={() => completeToken(row.id)} disabled={isWorking}>
                    Mark Complete
                  </button>
                ) : (
                  "-"
                ),
            },
          ]}
          data={tokens}
        />
      </div>
    </div>
  );
}
