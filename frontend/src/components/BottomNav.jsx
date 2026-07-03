import { NavLink } from "react-router-dom";
import { Bell, Home, Sparkles, User2, Users } from "lucide-react";
import { TID } from "@/constants/testIds";

const ITEMS = [
  { to: "/app/home", label: "Home", icon: Home, tid: TID.navHome },
  { to: "/app/programs", label: "Programs", icon: Sparkles, tid: TID.navPrograms },
  { to: "/app/refer", label: "Refer", icon: Users, tid: TID.navRefer },
  { to: "/app/notifications", label: "Alerts", icon: Bell, tid: TID.navNotifications },
  { to: "/app/profile", label: "Profile", icon: User2, tid: TID.navProfile },
];

export default function BottomNav() {
  return (
    <nav className="rw-bottom-nav">
      <div className="rw-phone grid grid-cols-5 gap-1 px-2 pt-2">
        {ITEMS.map(({ to, label, icon: Icon, tid }) => (
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
                  className={`grid place-items-center rounded-full transition-all ${
                    isActive
                      ? "h-9 w-9 bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal-deep))]"
                      : "h-8 w-8"
                  }`}
                >
                  <Icon className="h-5 w-5" />
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
