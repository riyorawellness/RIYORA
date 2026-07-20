import { useEffect, useState } from "react";
import { useNavigate, NavLink, Outlet } from "react-router-dom";
import { LogOut, LayoutDashboard, BarChart3, FileBarChart, ShieldCheck, Users, Wallet, CreditCard, QrCode, ClipboardCheck, FileText, Bell, Image as ImageIcon, ScrollText, Settings2, Layers, BookOpen, FolderOpen, Activity, Mail } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import Logo from "@/components/Logo";
import { useAuth } from "@/context/AuthContext";

const NAV = [
  { to: "/admin/dashboard", label: "Dashboard", icon: LayoutDashboard, testid: "admin-nav-dashboard" },
  { to: "/admin/analytics", label: "Analytics", icon: BarChart3, testid: "admin-nav-analytics" },
  { to: "/admin/reports", label: "Reports", icon: FileBarChart, testid: "admin-nav-reports" },
  { to: "/admin/programs", label: "Programs", icon: BookOpen, testid: "admin-nav-programs" },
  { to: "/admin/media", label: "Media", icon: FolderOpen, testid: "admin-nav-media" },
  { to: "/admin/users", label: "Users", icon: Users, testid: "admin-nav-users" },
  { to: "/admin/change-requests", label: "Change requests", icon: Mail, testid: "admin-nav-change-requests" },
  { to: "/admin/payments", label: "Payments", icon: CreditCard, testid: "admin-nav-payments" },
  { to: "/admin/payment-verifications", label: "Verify Payments", icon: ClipboardCheck, testid: "admin-nav-payment-verify" },
  { to: "/admin/payment-settings", label: "QR & Settings", icon: QrCode, testid: "admin-nav-payment-settings" },
  { to: "/admin/referrals", label: "Referrals", icon: Wallet, testid: "admin-nav-referrals" },
  { to: "/admin/notifications", label: "Notifications", icon: Bell, testid: "admin-nav-notifs" },
  { to: "/admin/banners", label: "Banners", icon: ImageIcon, testid: "admin-nav-banners" },
  { to: "/admin/cms", label: "CMS", icon: FileText, testid: "admin-nav-cms" },
  { to: "/admin/system", label: "System", icon: Settings2, testid: "admin-nav-system" },
  { to: "/admin/audit", label: "Audit log", icon: ScrollText, testid: "admin-nav-audit" },
  { to: "/admin/qa", label: "QA / BRV", icon: ShieldCheck, testid: "admin-nav-qa" },
  { to: "/admin/qa/live-check", label: "Live Check", icon: Activity, testid: "admin-nav-livecheck" },
  { to: "/admin/qa/sub-debug",  label: "Sub Debug",  icon: Activity, testid: "admin-nav-subdebug" },
];

/**
 * AdminShell — persistent left rail + header for every admin page.
 * Wrap each admin page with this via <Route element={<AdminShell/>}>.
 */
export default function AdminShell() {
  const nav = useNavigate();
  const { admin, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  const doLogout = async () => {
    await logout();
    nav("/", { replace: true });
  };

  useEffect(() => {
    // collapse on small screens
    setCollapsed(window.innerWidth < 900);
  }, []);

  return (
    <div className="min-h-screen bg-neutral-50">
      <header className="sticky top-0 z-30 flex items-center justify-between border-b bg-white/95 px-6 py-3 backdrop-blur">
        <div className="flex items-center gap-3">
          <Logo size="sm" />
          <Badge variant="secondary">Admin</Badge>
          <span className="hidden text-sm text-muted-foreground sm:inline">
            {admin?.name}
          </span>
        </div>
        <Button variant="secondary" size="sm" onClick={doLogout} data-testid="admin-shell-logout">
          <LogOut className="mr-1 h-4 w-4" /> Sign out
        </Button>
      </header>

      <div className="flex">
        <aside
          className={`sticky top-[57px] hidden h-[calc(100vh-57px)] shrink-0 border-r bg-white p-2 lg:block ${
            collapsed ? "w-16" : "w-56"
          }`}
        >
          <nav className="flex flex-col gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end
                data-testid={item.testid}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-neutral-50 hover:text-foreground"
                  }`
                }
              >
                <item.icon className="h-4 w-4" />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            ))}
          </nav>
          <button
            className="mt-auto w-full pt-4 text-center text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setCollapsed((c) => !c)}
          >
            {collapsed ? "→" : "← collapse"}
          </button>
        </aside>

        {/* Mobile nav — horizontal scroll */}
        <div className="fixed bottom-0 left-0 right-0 z-20 flex gap-1 overflow-x-auto border-t bg-white px-2 py-1 lg:hidden">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              data-testid={`${item.testid}-mobile`}
              className={({ isActive }) =>
                `flex min-w-max flex-col items-center gap-0.5 rounded-md px-3 py-1 text-[10px] ${
                  isActive ? "text-primary" : "text-muted-foreground"
                }`
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </div>

        <main className="flex-1 pb-24 pt-2 lg:pb-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
