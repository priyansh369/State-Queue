import { useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { useAuth } from "../../state/AuthContext";
import { TextInput } from "../../components/common/FormControls";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      const user = await login(email, password);
      if (user.role === "patient") navigate("/patient");
      else if (user.role === "doctor") navigate("/doctor");
      else if (user.role === "receptionist") navigate("/reception");
      else navigate("/");
    } catch (err) {
      console.error(err);
      toast.error("Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h2>Login</h2>
        <form onSubmit={onSubmit}>
          <TextInput label="Email" value={email} onChange={setEmail} type="email" />
          <TextInput
            label="Password"
            value={password}
            onChange={setPassword}
            type="password"
          />
          <button className="primary-btn" disabled={loading}>
            {loading ? "Logging in..." : "Login"}
          </button>
        </form>
        <p className="auth-alt" onClick={() => navigate("/register")}>
          New here? Register
        </p>
      </div>
    </div>
  );
}

