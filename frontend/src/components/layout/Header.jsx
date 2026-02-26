import { useAuth } from "../../state/AuthContext";

export default function Header() {
  const { user } = useAuth();
  return (
    <header className="header">
      <div className="header-title">Hospital Management Dashboard</div>
      {user && (
        <div className="header-user">
          <span className="header-user-name">{user.name}</span>
          <span className="header-user-role">{user.role}</span>
        </div>
      )}
    </header>
  );
}

