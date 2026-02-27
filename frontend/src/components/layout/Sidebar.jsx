import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../../state/AuthContext";

export default function Sidebar({ links, open, onClose }) {
  const { logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
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
            className={({ isActive }) =>
              "sidebar-link" + (isActive ? " sidebar-link-active" : "")
            }
          >
            {link.label}
          </NavLink>
        ))}
      </nav>
      <button className="sidebar-logout" onClick={handleLogout}>
        Logout
      </button>
      </aside>
    </>
  );
}

