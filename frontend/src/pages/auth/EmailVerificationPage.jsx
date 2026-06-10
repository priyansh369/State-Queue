import { useState, useEffect } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import toast from "react-hot-toast";
import api from "../../utils/api";

export default function EmailVerificationPage() {
  const navigate = useNavigate();
  const { token } = useParams();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState(searchParams.get("email") || "");
  const [loading, setLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [verified, setVerified] = useState(false);

  useEffect(() => {
    if (token) {
      verifyEmailWithToken();
    }
  }, [token]);

  useEffect(() => {
    if (cooldown > 0) {
      const timer = setTimeout(() => setCooldown(cooldown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [cooldown]);

  const verifyEmailWithToken = async () => {
    try {
      setLoading(true);
      await api.post(`/auth/verify-email/${token}`);
      setVerified(true);
      toast.success("Email verified successfully!");
      setTimeout(() => navigate("/login"), 2000);
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to verify email");
      setVerified(false);
    } finally {
      setLoading(false);
    }
  };

  const onResendEmail = async (e) => {
    e.preventDefault();
    if (!email) {
      toast.error("Please enter your email address");
      return;
    }

    try {
      setLoading(true);
      await api.post("/auth/resend-verification-email", { email });
      toast.success("Verification email sent! Check your inbox.");
      setCooldown(60);
    } catch (error) {
      toast.error(error?.response?.data?.error?.message || "Failed to resend email");
    } finally {
      setLoading(false);
    }
  };

  if (token) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100 flex items-center justify-center px-4 py-10">
        <div className="w-full max-w-md">
          <div className="text-center mb-6">
            <div className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-blue-600 text-white font-bold">
              {verified ? "✓" : "⏳"}
            </div>
            <h1 className="mt-4 text-2xl font-semibold tracking-tight text-slate-900">
              {verified ? "Email verified" : "Verifying email"}
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              {verified ? "You can now login" : "Please wait..."}
            </p>
          </div>

          {loading && (
            <div className="bg-white/80 backdrop-blur rounded-2xl shadow-xl shadow-slate-900/5 border border-slate-200 p-6 sm:p-8 text-center">
              <p className="text-slate-600">Verifying your email...</p>
            </div>
          )}

          {verified && (
            <div className="bg-white/80 backdrop-blur rounded-2xl shadow-xl shadow-slate-900/5 border border-slate-200 p-6 sm:p-8">
              <div className="p-4 bg-green-50 rounded-lg border border-green-200 text-center">
                <p className="text-sm text-green-800">Your email has been verified successfully!</p>
                <p className="text-xs text-green-700 mt-2">Redirecting to login...</p>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

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
          <p className="mt-1 text-sm text-slate-600">We sent you a verification link</p>
        </div>

        <div className="bg-white/80 backdrop-blur rounded-2xl shadow-xl shadow-slate-900/5 border border-slate-200 p-6 sm:p-8">
          <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
            <p className="text-sm text-slate-700">
              We've sent a verification link to <strong>{email || "your email"}</strong>
            </p>
            <p className="text-xs text-slate-600 mt-2">Click the link in the email to verify your account.</p>
          </div>

          <form onSubmit={onResendEmail} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700">Email Address</label>
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
              disabled={loading || cooldown > 0}
              className="w-full rounded-xl bg-blue-600 text-white py-2.5 font-semibold shadow hover:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed transition"
            >
              {loading ? "Sending..." : cooldown > 0 ? `Resend in ${cooldown}s` : "Resend Email"}
            </button>
          </form>

          <div className="mt-5 text-center text-sm text-slate-600">
            Already verified?{" "}
            <button
              type="button"
              className="font-semibold text-blue-700 hover:text-blue-800"
              onClick={() => navigate("/login")}
            >
              Go to login
            </button>
          </div>
        </div>

        <p className="text-center text-xs text-slate-500 mt-6">
          Didn't receive the email? Check your spam folder or contact support.
        </p>
      </div>
    </div>
  );
}

