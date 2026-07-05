import { NavLink } from "react-router-dom";
import { Bell, Home, Sparkles, User2, Users } from "lucide-react";
import { TID } from "@/constants/testIds";
import { useAuth } from "@/context/AuthContext";
import { usePollUnreadCount } from "@/hooks/usePollUnreadCount";

const ITEMS = [
  { to: "/app/home", label: "Home", icon: Home, tid: TID.navHome },
  { to: "/app/programs", label: "Programs", icon: Sparkles, tid: TID.navPrograms },
  { to: "/app/refer", label: "Refer", icon: Users, tid: TID.navRefer },
  { to: "/app/notifications", label: "Alerts", icon: Bell, tid: TID.navNotifications, badge: true },
  { to: "/app/profile", label: "Profile", icon: User2, tid: TID.navProfile },
];

export default function BottomNav() {
  const { user } = useAuth();
  const { unread } = usePollUnreadCount({ enabled: !!user });

  return (
    <nav className="rw-bottom-nav">
      <div className="rw-phone grid grid-cols-5 gap-1 px-2 pt-2">
        {ITEMS.map(({ to, label, icon: Icon, tid, badge }) => (
          <NavLink
            key={to}
            to={to}
            data-testid={tid}
            className={({ isActive }) =>
              `flex flex-col items-center gap-1 rounded-xl px-2 py-1.5 text-[11px] font-medium transition-all ${
                isActive
                  ? "text-[hsl(var(--rw-royal))]"
                  : "text-[hsl(var(--rw-grey-500))]"
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={`relative grid place-items-center rounded-full transition-all ${
                    isActive
                      ? "h-9 w-9 bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal-deep))]"
                      : "h-8 w-8"
                  }`}
                >
                  <Icon className="h-5 w-5" />
                  {badge && unread > 0 && (
                    <span
                      className="absolute -right-1 -top-1 grid min-h-[16px] min-w-[16px] place-items-center rounded-full bg-red-600 px-1 text-[9px] font-bold leading-none text-white ring-2 ring-white"
                      data-testid="nav-notif-badge"
                    >
                      {unread > 99 ? "99+" : unread}
                    </span>
                  )}
                </span>
                <span>{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
