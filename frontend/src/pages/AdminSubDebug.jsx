import { useEffect, useState } from "react";
import { RefreshCw, Loader2, ChevronDown, ChevronRight, CheckCircle2, XCircle } from "lucide-react";

import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const SOURCE_STYLES = {
  backend:  "bg-blue-100 text-blue-800",
  frontend: "bg-purple-100 text-purple-800",
  webhook:  "bg-emerald-100 text-emerald-800",
};

/**
 * AdminSubDebug — chronological trace of a subscription attempt.
 *
 * Data source: GET /api/admin/qa/sub-debug (filterable by subscription_id,
 * membership_id or program_id). Backed by the `sub_debug_events` collection
 * that captures every server-side Razorpay call, every webhook, and every
 * frontend state transition of the SubscriptionCheckoutModal.
 */
export default function AdminSubDebug() {
  const [filter, setFilter] = useState({ subscription_id: "", membership_id: "", program_id: "" });
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState({});

  const load = async () => {
    setLoading(true);
    try {
      const params = Object.entries(filter)
        .filter(([, v]) => v)
        .map(([k, v]) => `${k}=${encodeURIComponent(v)}`)
        .join("&");
      const url = `/admin/qa/sub-debug${params ? `?${params}` : "?limit=200"}`;
      const r = await api.get(url).then((x) => x.data);
      setEvents(r.events || []);
    } catch (e) {
      toast.error(formatApiError(e, "Failed to load sub debug events"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <div className="p-6" data-testid="admin-sub-debug">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-[hsl(var(--rw-royal))]">
            QA · Subscription flow
          </p>
          <h1 className="rw-serif text-2xl">Debug trace</h1>
        </div>
        <Button size="sm" variant="ghost" onClick={load} disabled={loading} data-testid="sub-debug-refresh">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        </Button>
      </div>

      <Card className="rw-card p-4">
        <p className="mb-3 text-xs text-muted-foreground">
          Filter by any single field to isolate one attempt. Blank filters show
          the latest 200 events across all users.
        </p>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
          <Input
            placeholder="subscription_id (e.g. sub_XXXX)"
            value={filter.subscription_id}
            onChange={(e) => setFilter({ ...filter, subscription_id: e.target.value.trim() })}
            data-testid="sub-debug-filter-sid"
          />
          <Input
            placeholder="membership_id (e.g. RW123456)"
            value={filter.membership_id}
            onChange={(e) => setFilter({ ...filter, membership_id: e.target.value.trim() })}
            data-testid="sub-debug-filter-mid"
          />
          <Input
            placeholder="program_id (uuid)"
            value={filter.program_id}
            onChange={(e) => setFilter({ ...filter, program_id: e.target.value.trim() })}
            data-testid="sub-debug-filter-pid"
          />
        </div>
        <div className="mt-3 flex justify-end">
          <Button size="sm" onClick={load} data-testid="sub-debug-apply">
            Apply filter
          </Button>
        </div>
      </Card>

      <Card className="mt-4 rw-card p-4">
        {loading && (
          <div className="grid place-items-center py-8 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        )}
        {!loading && events.length === 0 && (
          <p className="text-sm text-muted-foreground" data-testid="sub-debug-empty">
            No events match this filter. Have the user reproduce the flow — new events land here in real time.
          </p>
        )}
        {!loading && events.length > 0 && (
          <div className="space-y-1 font-mono text-[11px]" data-testid="sub-debug-list">
            {events.map((e) => (
              <EventRow
                key={e.id}
                e={e}
                open={!!expanded[e.id]}
                onToggle={() => setExpanded((x) => ({ ...x, [e.id]: !x[e.id] }))}
              />
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

function EventRow({ e, open, onToggle }) {
  const src = SOURCE_STYLES[e.source] || "bg-neutral-100 text-neutral-800";
  const t = new Date(e.created_at).toLocaleTimeString("en-IN", {
    hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit"
  });
  return (
    <div
      className={`rounded border px-2 py-1.5 ${
        e.ok ? "border-neutral-200 bg-white" : "border-red-200 bg-red-50"
      }`}
      data-testid={`sub-debug-event-${e.id}`}
    >
      <button
        onClick={onToggle}
        className="flex w-full items-start gap-2 text-left"
      >
        {open ? <ChevronDown className="mt-0.5 h-3 w-3 shrink-0" /> : <ChevronRight className="mt-0.5 h-3 w-3 shrink-0" />}
        <span className="text-neutral-500">{t}</span>
        <Badge className={`${src} shrink-0`}>{e.source}</Badge>
        <span className="flex-1 truncate font-semibold">{e.stage}</span>
        {e.ok ? (
          <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-600" />
        ) : (
          <XCircle className="h-3 w-3 shrink-0 text-red-600" />
        )}
      </button>
      {open && (
        <pre className="mt-2 max-h-80 overflow-auto rounded bg-neutral-950 p-2 text-[10px] text-emerald-100">
{JSON.stringify(
  {
    id: e.id,
    subscription_id: e.subscription_id,
    program_id: e.program_id,
    membership_id: e.membership_id,
    message: e.message,
    payload: e.payload,
    error: e.error,
  },
  null,
  2,
)}
        </pre>
      )}
    </div>
  );
}
