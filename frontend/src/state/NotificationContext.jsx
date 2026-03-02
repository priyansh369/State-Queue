import { createContext, useContext, useEffect, useMemo, useState } from "react";
import toast from "react-hot-toast";
import { useAuth } from "./AuthContext";
import { subscribeQueueUpdates } from "../utils/realtime";

const STORAGE_KEY = "smarthospital_notifications";
const MAX_NOTIFICATIONS = 50;

const NotificationContext = createContext(null);

function readStoredNotifications() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function eventToNotification(eventName, data) {
  const patientName = data?.name ? ` (${data.name})` : "";
  switch (eventName) {
    case "NEW_APPOINTMENT":
      return { title: "New appointment", message: `Patient added to queue${patientName}.` };
    case "STATUS_UPDATED":
      return { title: "Status updated", message: `Queue status changed${patientName}.` };
    case "PRIORITY_CHANGED":
      return { title: "Priority changed", message: `Priority updated${patientName}.` };
    case "APPOINTMENT_CANCELLED":
      return { title: "Appointment cancelled", message: `Appointment cancelled${patientName}.` };
    case "PATIENT_TRANSFERRED":
      return { title: "Patient transferred", message: `Patient moved to another doctor${patientName}.` };
    case "DOCTOR_AVAILABILITY_CHANGED":
      return {
        title: "Doctor availability",
        message: data?.is_available
          ? "Doctor is now available."
          : "Doctor is now unavailable.",
      };
    default:
      return { title: "Queue update", message: "Queue has changed." };
  }
}

function shouldNotify(user, payload) {
  if (!user?.role) return false;
  if (user.role === "receptionist") return true;

  if (user.role === "doctor") {
    return Number(payload?.doctor_id) === Number(user.id);
  }

  if (user.role === "patient") {
    const patientId = Number(localStorage.getItem("smarthospital_patient_id"));
    if (!Number.isFinite(patientId) || patientId <= 0) return false;
    return Number(payload?.id) === patientId;
  }

  return false;
}

export function NotificationProvider({ children }) {
  const { user } = useAuth();
  const [items, setItems] = useState(() => readStoredNotifications());
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_NOTIFICATIONS)));
  }, [items]);

  useEffect(() => {
    setUnreadCount(0);
  }, [user?.id, user?.role]);

  useEffect(() => {
    if (!user) return undefined;

    const unsubscribe = subscribeQueueUpdates((message) => {
      if (message?.type !== "appointment_update" && message?.type !== "queue_update") return;
      const payload = message?.data || {};
      if (!shouldNotify(user, payload)) return;

      const mapped = eventToNotification(payload.event, payload);
      const item = {
        id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
        created_at: new Date().toISOString(),
        title: mapped.title,
        message: mapped.message,
      };

      setItems((prev) => [item, ...prev].slice(0, MAX_NOTIFICATIONS));
      setUnreadCount((count) => count + 1);
      toast(mapped.title);
    });

    return () => unsubscribe();
  }, [user]);

  const markAllRead = () => setUnreadCount(0);
  const clearAll = () => {
    setItems([]);
    setUnreadCount(0);
  };

  const value = useMemo(
    () => ({ items, unreadCount, markAllRead, clearAll }),
    [items, unreadCount]
  );

  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>;
}

export function useNotifications() {
  return useContext(NotificationContext);
}
