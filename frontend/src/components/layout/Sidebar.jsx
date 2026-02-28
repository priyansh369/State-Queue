import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../state/AuthContext";

function SidebarIcon({ name }) {
  const iconMap = {
    queue: "M4 6h16M4 12h16M4 18h16",
    dashboard: "M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v11h-7zM4 13h7v8H4z",
    book: "M6 4h12a2 2 0 0 1 2 2v14l-4-2-4 2-4-2-4 2V6a2 2 0 0 1 2-2z",
    doctor: "M12 3v18M3 12h18",
    logout: "M10 5H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h4M14 16l5-4-5-4M19 12H9",
  };
  const d = iconMap[name] || iconMap.dashboard;

  return (
    <svg className="sidebar-link-icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d={d} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function Sidebar({ links, open, onClose }) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const getIcon = (link) => {
    const label = String(link.label || "").toLowerCase();
    if (label.includes("queue")) return "queue";
    if (label.includes("book")) return "book";
    if (label.includes("doctor")) return "doctor";
    return "dashboard";
  };

  return (
    <>
      {open && <button className="sidebar-overlay" onClick={onClose} aria-label="Close menu" />}
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="sidebar-header">Smart Hospital</div>
        <nav className="sidebar-nav">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              onClick={onClose}
              className={({ isActive }) => "sidebar-link" + (isActive ? " sidebar-link-active" : "")}
            >
              <span className="sidebar-link-content">
                <SidebarIcon name={getIcon(link)} />
                <span>{link.label}</span>
              </span>
            </NavLink>
          ))}
        </nav>
        <button className="sidebar-logout" onClick={handleLogout}>
          <span className="sidebar-link-content">
            <SidebarIcon name="logout" />
            <span>Logout</span>
          </span>
        </button>
      </aside>
    </>
  );
}

