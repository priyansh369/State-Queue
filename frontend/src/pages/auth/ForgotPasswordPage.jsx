import { useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import api from "../../utils/api";

export default function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();
    try {
      setLoading(true);
      await api.post("/auth/request-password-reset", { email });
      setSubmitted(true);
      toast.success("If email exists, reset link will be sent");
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to send reset email");
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-md">
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-blue-600 text-white font-bold">
              ✓
            </div>
            <h1 className="mt-4 text-2xl font-semibold tracking-tight text-slate-900">
              Check your email
            </h1>
            <p className="mt-1 text-sm text-slate-600">Password reset link sent</p>
          </div>

          <div className="bg-white/80 backdrop-blur rounded-2xl shadow-xl shadow-slate-900/5 border border-slate-200 p-6 sm:p-8">
            <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <p className="text-sm text-slate-700">
                We've sent a password reset link to <strong>{email}</strong>
              </p>
              <p className="text-xs text-slate-600 mt-2">
                Click the link in the email to reset your password. The link will expire in 30 minutes.
              </p>
            </div>

            <button
              type="button"
              onClick={() => navigate("/login")}
              className="w-full rounded-xl bg-blue-600 text-white py-2.5 font-semibold shadow hover:bg-blue-700 transition"
            >
              Back to login
            </button>
          </div>

          <p className="text-center text-xs text-slate-500 mt-6">
            Didn't receive the email? Check your spam folder.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-blue-600 text-white font-bold">
            🔑
          </div>
          <h1 className="mt-4 text-2xl font-semibold tracking-tight text-slate-900">
            Reset password
          </h1>
          <p className="mt-1 text-sm text-slate-600">Enter your email to receive a reset link</p>
        </div>

        <div className="bg-white/80 backdrop-blur rounded-2xl shadow-xl shadow-slate-900/5 border border-slate-200 p-6 sm:p-8">
          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700">Email</label>
              <input
                className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/60"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your@hospital.com"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-blue-600 text-white py-2.5 font-semibold shadow hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition"
            >
              {loading ? "Sending..." : "Send reset link"}
            </button>
          </form>

          <div className="mt-5 text-center text-sm text-slate-600">
            Remember your password?{" "}
            <button
              type="button"
              className="font-semibold text-blue-700 hover:text-blue-800"
              onClick={() => navigate("/login")}
            >
              Sign in
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
