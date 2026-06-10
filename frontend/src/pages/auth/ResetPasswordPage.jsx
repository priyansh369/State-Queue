import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import toast from "react-hot-toast";
import api from "../../utils/api";

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const { token } = useParams();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const onSubmit = async (e) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }

    if (password.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }

    try {
      setLoading(true);
      await api.post(`/auth/reset-password/${token}`, { new_password: password });
      toast.success("Password reset successfully! You can now login.");
      navigate("/login");
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to reset password");
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-md text-center">
          <h1 className="text-2xl font-semibold text-slate-900">Invalid link</h1>
          <p className="text-sm text-slate-600 mt-2">The password reset link is invalid or has expired.</p>
          <button
            onClick={() => navigate("/forgot-password")}
            className="mt-4 rounded-xl bg-blue-600 text-white py-2.5 px-6 font-semibold hover:bg-blue-700 transition"
          >
            Request new link
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-blue-600 text-white font-bold">
            🔐
          </div>
          <h1 className="mt-4 text-2xl font-semibold tracking-tight text-slate-900">
            Create new password
          </h1>
          <p className="mt-1 text-sm text-slate-600">Enter a strong password to secure your account</p>
        </div>

        <div className="bg-white/80 backdrop-blur rounded-2xl shadow-xl shadow-slate-900/5 border border-slate-200 p-6 sm:p-8">
          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700">New Password</label>
              <div className="relative mt-1">
                <input
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 pr-12 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/60"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Min 8 chars with upper/lower/number/symbol"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 transition"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "👁️‍🗨️" : "👁️"}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">Confirm Password</label>
              <div className="relative mt-1">
                <input
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 pr-12 text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/60"
                  type={showConfirmPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter password"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700 transition"
                  aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                >
                  {showConfirmPassword ? "👁️‍🗨️" : "👁️"}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-xl bg-blue-600 text-white py-2.5 font-semibold shadow hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition"
            >
              {loading ? "Resetting..." : "Reset password"}
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
