import { useState } from "react";
import Header from "./Header";
import Sidebar from "./Sidebar";

export default function AppShell({ links, children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="app-shell">
      <Sidebar links={links} open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="app-main">
        <Header onMenuToggle={() => setSidebarOpen((prev) => !prev)} />
        <div className="app-content">{children}</div>
      </main>
    </div>
  );
}
