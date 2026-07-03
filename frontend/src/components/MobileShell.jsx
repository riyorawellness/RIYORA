import { Outlet } from "react-router-dom";
import BottomNav from "@/components/BottomNav";

export default function MobileShell() {
  return (
    <div className="min-h-screen bg-[hsl(var(--rw-off-white))]">
      <div className="rw-phone rw-safe-top pb-28">
        <Outlet />
      </div>
      <BottomNav />
    </div>
  );
}
