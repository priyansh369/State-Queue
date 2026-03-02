import { useState } from "react";
import { useAuth } from "../../state/AuthContext";
import { useNotifications } from "../../state/NotificationContext";

export default function Header({ onMenuToggle }) {
  const { user } = useAuth();
  const { items, unreadCount, markAllRead, clearAll } = useNotifications();
  const [open, setOpen] = useState(false);

  return (
    <header className="header">
      <button className="menu-btn" onClick={onMenuToggle} aria-label="Toggle menu">
        Menu
      </button>
      <div className="header-title">Hospital Management Dashboard</div>
      {user && (
        <div className="header-right">
          <div className="header-notifications">
            <button
              type="button"
              className="notification-btn"
              onClick={() => {
                const next = !open;
                setOpen(next);
                if (next) markAllRead();
              }}
              aria-label="Notifications"
            >
              Bell
              {unreadCount > 0 ? <span className="notification-badge">{unreadCount}</span> : null}
            </button>
            {open ? (
              <div className="notification-panel">
                <div className="notification-header">
                  <strong>Notifications</strong>
                  <button type="button" className="secondary-btn" onClick={clearAll}>
                    Clear
                  </button>
                </div>
                <div className="notification-list">
                  {items.length ? (
                    items.slice(0, 10).map((item) => (
                      <div key={item.id} className="notification-item">
                        <div className="notification-item-title">{item.title}</div>
                        <div className="notification-item-message">{item.message}</div>
                      </div>
                    ))
                  ) : (
                    <div className="notification-empty">No notifications yet.</div>
                  )}
                </div>
              </div>
            ) : null}
          </div>
          <div className="header-user">
            <span className="header-user-name">{user.name}</span>
            <span className="header-user-role">{user.role}</span>
          </div>
        </div>
      )}
    </header>
  );
}

