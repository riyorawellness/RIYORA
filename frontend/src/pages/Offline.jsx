import { WifiOff } from "lucide-react";
import EmptyState from "@/components/EmptyState";

export default function Offline() {
  return (
    <div className="grid min-h-screen place-items-center bg-white">
      <EmptyState
        icon={WifiOff}
        title="You're offline"
        body="Please reconnect to continue your practice. Cached pages will still load."
        actionLabel="Retry"
        onAction={() => window.location.reload()}
      />
    </div>
  );
}
