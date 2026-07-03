import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  IndianRupee,
  Users,
  TrendingUp,
  Wallet,
  Layers,
  Activity,
  CalendarClock,
  Loader2,
} from "lucide-react";
import {
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { adminApi } from "@/services/admin";
import { formatApiError } from "@/lib/api";

export default function AdminDashboard() {
  const [ov, setOv] = useState(null);
  const [series, setSeries] = useState([]);
  const [topPrograms, setTopPrograms] = useState([]);
  const [topRefs, setTopRefs] = useState([]);
  const [activity, setActivity] = useState([]);
  const [txns, setTxns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [o, s, tp, tr, a, t] = await Promise.all([
          adminApi.overview(),
          adminApi.revenueSeries(30),
          adminApi.topPrograms(5),
          adminApi.topReferrers(5),
          adminApi.recentActivity(15),
          adminApi.recentTransactions(8),
        ]);
        setOv(o);
        setSeries(s.series || []);
        setTopPrograms(tp.items || []);
        setTopRefs(tr.items || []);
        setActivity(a.items || []);
        setTxns(t.items || []);
      } catch (e) {
        toast.error(formatApiError(e, "Dashboard load failed"));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading || !ov) {
    return (
      <div className="grid place-items-center py-24 text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="px-6 py-6">
      <p className="rw-eyebrow">Overview</p>
      <h1 className="mt-1 rw-serif text-4xl">Admin Dashboard</h1>

      <section className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4" data-testid="admin-dash-stats">
        <Stat icon={IndianRupee} label="Revenue today" value={inr(ov.revenue_today)} accent />
        <Stat icon={IndianRupee} label="Revenue this month" value={inr(ov.revenue_month)} />
        <Stat icon={IndianRupee} label="Revenue this year" value={inr(ov.revenue_year)} />
        <Stat icon={Users} label="Total users" value={ov.total_users} sub={`${ov.todays_registrations} today`} />
        <Stat icon={Activity} label="Active users" value={ov.active_users} sub={`${ov.inactive_users} inactive`} />
        <Stat icon={Layers} label="Programs" value={ov.total_programs} sub={`${ov.total_purchases} purchases`} />
        <Stat icon={TrendingUp} label="Active subscribers" value={ov.active_subscribers} sub={`${ov.expired_subscribers} expired`} />
        <Stat icon={Wallet} label="Pending payout" value={inr(ov.pending_payout_amount)} sub={`paid ${inr(ov.paid_payout_amount)}`} />
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-3">
        <Card className="rw-card p-5 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <p className="rw-eyebrow">Revenue trend</p>
              <h2 className="rw-serif text-2xl">Last 30 days</h2>
            </div>
            <Badge variant="secondary" className="flex items-center gap-1">
              <CalendarClock className="h-3 w-3" /> Daily
            </Badge>
          </div>
          <div style={{ height: 240 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={series} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v) => v.slice(5)} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `₹${v}`} />
                <Tooltip
                  formatter={(v) => [`₹${Number(v).toLocaleString("en-IN")}`, "Revenue"]}
                  labelFormatter={(l) => l}
                />
                <Line type="monotone" dataKey="revenue" stroke="#0B1A5B" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="rw-card p-5">
          <p className="rw-eyebrow">Top programs</p>
          <h2 className="rw-serif text-2xl">Best sellers</h2>
          <div className="mt-3 space-y-3" data-testid="dash-top-programs">
            {topPrograms.length === 0 ? (
              <p className="text-sm text-muted-foreground">No sales yet.</p>
            ) : (
              topPrograms.map((p, i) => (
                <div key={p.program_id} className="flex items-center gap-3">
                  <div className="grid h-8 w-8 place-items-center rounded-full bg-primary/10 font-semibold text-primary">
                    {i + 1}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold">{p.name}</div>
                    <div className="text-[11px] text-muted-foreground">
                      {p.purchases} purchases
                    </div>
                  </div>
                  <div className="text-sm font-semibold text-primary">{inr(p.revenue)}</div>
                </div>
              ))
            )}
          </div>
        </Card>
      </section>

      <section className="mt-8 grid gap-6 lg:grid-cols-2">
        <Card className="rw-card p-5">
          <p className="rw-eyebrow">Top referrers</p>
          <h2 className="rw-serif text-2xl">Champions</h2>
          <div className="mt-3 space-y-2" data-testid="dash-top-referrers">
            {topRefs.length === 0 ? (
              <p className="text-sm text-muted-foreground">No commissions yet.</p>
            ) : (
              topRefs.map((r, i) => (
                <div key={r.membership_id} className="flex items-center gap-3">
                  <div className="grid h-8 w-8 place-items-center rounded-full bg-[hsl(var(--rw-gold-soft))] font-semibold text-[hsl(35_60%_38%)]">
                    {i + 1}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold">{r.full_name}</div>
                    <div className="font-mono text-[11px] text-muted-foreground">
                      {r.membership_id} · {r.commissions} txn
                    </div>
                  </div>
                  <div className="text-sm font-semibold text-[hsl(35_60%_38%)]">{inr(r.amount)}</div>
                </div>
              ))
            )}
          </div>
        </Card>

        <Card className="rw-card p-5">
          <p className="rw-eyebrow">Latest transactions</p>
          <h2 className="rw-serif text-2xl">Recent</h2>
          <div className="mt-3 divide-y" data-testid="dash-recent-txns">
            {txns.length === 0 ? (
              <p className="text-sm text-muted-foreground">No transactions yet.</p>
            ) : (
              txns.map((t) => (
                <div key={t.invoice_number} className="flex items-center gap-3 py-2">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">
                      {t.user_name} · {t.program_name}
                    </div>
                    <div className="font-mono text-[11px] text-muted-foreground">
                      {t.invoice_number} · {formatDate(t.purchase_date)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-semibold">{inr(t.total)}</div>
                    <Badge variant={t.status === "active" ? "default" : "secondary"} className="text-[9px]">
                      {t.status}
                    </Badge>
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      </section>

      <section className="mt-8">
        <Card className="rw-card p-5">
          <p className="rw-eyebrow">System activity</p>
          <h2 className="rw-serif text-2xl">Audit feed</h2>
          <div className="mt-3 max-h-96 divide-y overflow-y-auto" data-testid="dash-audit-feed">
            {activity.length === 0 ? (
              <p className="text-sm text-muted-foreground">No activity yet.</p>
            ) : (
              activity.map((a) => (
                <div key={a.id} className="flex gap-3 py-2 text-sm">
                  <div className="w-40 shrink-0 font-mono text-[11px] text-muted-foreground">
                    {formatDateTime(a.created_at)}
                  </div>
                  <div className="flex-1">
                    <Badge variant="outline" className="mr-2 text-[10px]">
                      {a.action}
                    </Badge>
                    {a.actor_membership_id && (
                      <span className="mr-2 font-mono text-[11px] text-muted-foreground">
                        by {a.actor_membership_id}
                      </span>
                    )}
                    {a.target && (
                      <span className="text-[11px] text-muted-foreground">→ {a.target}</span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </Card>
      </section>
    </div>
  );
}

function Stat({ icon: Icon, label, value, sub, accent }) {
  return (
    <Card className={`p-4 ${accent ? "border-primary" : ""}`}>
      <div className="flex items-center justify-between">
        <div className={`grid h-9 w-9 place-items-center rounded-lg ${accent ? "bg-primary text-white" : "bg-primary/10 text-primary"}`}>
          <Icon className="h-4 w-4" />
        </div>
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</span>
      </div>
      <div className="mt-3 rw-serif text-3xl">{value ?? "—"}</div>
      {sub && <div className="text-[11px] text-muted-foreground">{sub}</div>}
    </Card>
  );
}

function inr(v) {
  if (v === null || v === undefined) return "—";
  return `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}
function formatDate(iso) {
  try {
    return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "2-digit" });
  } catch {
    return iso;
  }
}
function formatDateTime(iso) {
  try {
    return new Date(iso).toLocaleString("en-IN", {
      day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
