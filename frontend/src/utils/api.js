import axios from "axios";

const api = axios.create({
  baseURL: "http://localhost:8000",
});

let unauthorizedHandler = null;

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

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
    const status = error?.response?.status;
    const requestUrl = error?.config?.url || "";
    const isAuthEndpoint = requestUrl.includes("/auth/login") || requestUrl.includes("/auth/register");
    if ((status === 401 || status === 403) && unauthorizedHandler && !isAuthEndpoint) {
      unauthorizedHandler(error);
    }
    return Promise.reject(error);
  }
);

export default api;

