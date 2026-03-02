import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
});

// Always attach JWT from localStorage if present
api.interceptors.request.use((config) => {
  try {
    const stored = localStorage.getItem("smarthospital_auth");
    if (stored) {
      const parsed = JSON.parse(stored);
      if (parsed?.token) {
        // eslint-disable-next-line no-param-reassign
        config.headers = config.headers || {};
        // eslint-disable-next-line no-param-reassign
        config.headers.Authorization = `Bearer ${parsed.token}`;
      }
    }
  } catch {
    // ignore parse errors, send request without auth header
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error);
  }
);

export default api;
