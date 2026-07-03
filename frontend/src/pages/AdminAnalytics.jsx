import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  IndianRupee, TrendingUp, TrendingDown, Users, Layers, Wallet,
  Percent, Activity, Loader2, RefreshCw, Download,
} from "lucide-react";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid, Legend, Area, AreaChart,
} from "recharts";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { analyticsApi } from "@/services/analytics";
import { formatApiError } from "@/lib/api";

const PIE_COLORS = ["#0B1A5B", "#B08A3E", "#4B7BE5", "#E8A93A", "#7FB77E", "#D9534F", "#7C3AED", "#0EA5E9"];

function todayISO(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

const PRESETS = [
  { key: "7d",  label: "7d",  days: 7 },
  { key: "30d", label: "30d", days: 30 },
  { key: "90d", label: "90d", days: 90 },
  { key: "ytd", label: "YTD" },
  { key: "1y",  label: "1y",  days: 365 },
];

function computePreset(preset) {
  if (preset === "ytd") {
    const s = new Date(new Date().getFullYear(), 0, 1);
    return { since: s.toISOString().slice(0, 10), until: todayISO() };
  }
  const p = PRESETS.find((x) => x.key === preset);
  if (!p) return { since: todayISO(-29), until: todayISO() };
  return { since: todayISO(-(p.days - 1)), until: todayISO() };
}

export default function AdminAnalytics() {
  const [preset, setPreset] = useState("30d");
  const [since, setSince] = useState(computePreset("30d").since);
  const [until, setUntil] = useState(computePreset("30d").until);
  const [granularity, setGranularity] = useState("day");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async (opts = {}) => {
    try {
      const params = {
        since: opts.since ?? since,
        until: opts.until ?? until,
        granularity: opts.granularity ?? granularity,
      };
      setRefreshing(true);
      const d = await analyticsApi.dashboard(params);
      setData(d);
    } catch (e) {
      toast.error(formatApiError(e, "Failed to load analytics"));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const applyPreset = (key) => {
    const p = computePreset(key);
    setPreset(key);
    setSince(p.since);
    setUntil(p.until);
    load({ since: p.since, until: p.until });
  };

  const applyRange = () => {
    setPreset("custom");
    load();
  };

  const kpi = data?.kpis;
  const revChangePct = kpi?.revenue_change_pct;

  const revenueMerged = useMemo(() => {
    if (!data?.revenue_series) return [];
    const prev = data.revenue_series_previous || [];
    const map = new Map();
    data.revenue_series.forEach((r, i) => {
      map.set(r.bucket, { bucket: r.bucket, current: r.revenue, count: r.count, previous: prev[i]?.revenue ?? null });
    });
    return Array.from(map.values());
  }, [data]);

  if (loading) {
    return (
      <div className="grid place-items-center py-24 text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="px-6 py-6" data-testid="admin-analytics-page">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="rw-eyebrow">Reports & Analytics</p>
          <h1 className="mt-1 rw-serif text-4xl">Financial Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            {data?.range?.since?.slice(0, 10)} → {data?.range?.until?.slice(0, 10)}
            {revChangePct != null && (
              <span className={`ml-2 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${revChangePct >= 0 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                {revChangePct >= 0 ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                {revChangePct >= 0 ? "+" : ""}{revChangePct}% vs previous
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Tabs value={preset} onValueChange={applyPreset}>
            <TabsList data-testid="analytics-preset-tabs">
              {PRESETS.map((p) => (
                <TabsTrigger key={p.key} value={p.key} data-testid={`preset-${p.key}`}>
                  {p.label}
                </TabsTrigger>
              ))}
              <TabsTrigger value="custom" disabled>Custom</TabsTrigger>
            </TabsList>
          </Tabs>
          <Input type="date" value={since} onChange={(e) => setSince(e.target.value)} className="w-40" data-testid="analytics-since" />
          <span className="text-muted-foreground">→</span>
          <Input type="date" value={until} onChange={(e) => setUntil(e.target.value)} className="w-40" data-testid="analytics-until" />
          <Select value={granularity} onValueChange={(v) => { setGranularity(v); load({ granularity: v }); }}>
            <SelectTrigger className="w-28" data-testid="analytics-granularity"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="day">Daily</SelectItem>
              <SelectItem value="week">Weekly</SelectItem>
              <SelectItem value="month">Monthly</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="secondary" size="sm" onClick={applyRange} data-testid="analytics-apply">Apply</Button>
          <Button variant="ghost" size="icon" onClick={() => load()} data-testid="analytics-refresh">
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {/* KPI cards */}
      <section className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4 xl:grid-cols-6" data-testid="analytics-kpis">
        <Kpi icon={IndianRupee} label="Revenue" value={inr(kpi?.revenue?.revenue)}
          sub={`${kpi?.revenue?.count || 0} txn · avg ${inr(kpi?.revenue?.avg_ticket)}`} accent />
        <Kpi icon={Percent} label="GST Collected" value={inr(kpi?.revenue?.gst)} />
        <Kpi icon={Users} label="Total Users" value={kpi?.users?.total} sub={`${kpi?.users?.active} active`} />
        <Kpi icon={Activity} label="Active Subs" value={kpi?.users?.active_subscribers} />
        <Kpi icon={Wallet} label="Commission Liability"
          value={inr(data?.commissions?.summary?.total_liability)}
          sub={`pending+approved`} />
        <Kpi icon={TrendingUp} label="Net Margin" value={inr(kpi?.net_margin)}
          sub={`revenue − commissions`} />
      </section>

      {/* Revenue trend chart */}
      <Card className="rw-card mt-8 p-5" data-testid="revenue-trend-card">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <p className="rw-eyebrow">Revenue trend</p>
            <h2 className="rw-serif text-2xl">{granularityLabel(granularity)} · current vs previous period</h2>
          </div>
          <Badge variant="secondary">{revenueMerged.length} buckets</Badge>
        </div>
        <div style={{ height: 300 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={revenueMerged} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="curFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#0B1A5B" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#0B1A5B" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
              <XAxis dataKey="bucket" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `₹${v}`} />
              <Tooltip
                formatter={(v, k) => [inr(v), k === "current" ? "Current" : "Previous"]}
                labelStyle={{ fontSize: 12 }}
              />
              <Legend />
              <Area type="monotone" dataKey="current" stroke="#0B1A5B" strokeWidth={2} fill="url(#curFill)" name="Current" />
              <Line type="monotone" dataKey="previous" stroke="#B08A3E" strokeDasharray="4 4" strokeWidth={1.5} dot={false} name="Previous" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Two-column: user growth + programs pie */}
      <section className="mt-8 grid gap-6 lg:grid-cols-2">
        <Card className="rw-card p-5" data-testid="user-growth-card">
          <p className="rw-eyebrow">User growth</p>
          <h2 className="rw-serif text-2xl">New registrations</h2>
          <div className="mt-3" style={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.user_growth || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="bucket" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#B08A3E" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="rw-card p-5" data-testid="program-mix-card">
          <p className="rw-eyebrow">Program mix</p>
          <h2 className="rw-serif text-2xl">Revenue by program</h2>
          <div className="mt-3 flex items-center gap-4">
            <div className="h-48 w-48 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={(data?.programs || []).slice(0, 8)} dataKey="revenue" nameKey="name"
                    innerRadius={40} outerRadius={80} paddingAngle={2}>
                    {(data?.programs || []).slice(0, 8).map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v) => inr(v)} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex-1 space-y-1 text-xs">
              {(data?.programs || []).slice(0, 8).map((p, i) => (
                <div key={p.program_id} className="flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                  <span className="min-w-0 flex-1 truncate">{p.name}</span>
                  <span className="tabular-nums text-muted-foreground">{inr(p.revenue)}</span>
                </div>
              ))}
              {(data?.programs || []).length === 0 && <p className="text-muted-foreground">No sales in period.</p>}
            </div>
          </div>
        </Card>
      </section>

      {/* Commission by level (stacked bar) + subscription health */}
      <section className="mt-8 grid gap-6 lg:grid-cols-2">
        <Card className="rw-card p-5" data-testid="commissions-by-level-card">
          <p className="rw-eyebrow">Commissions by level</p>
          <h2 className="rw-serif text-2xl">L1 · L2 · L3</h2>
          <div className="mt-3" style={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.commissions?.by_level || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="level" tickFormatter={(v) => `L${v}`} tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `₹${v}`} />
                <Tooltip formatter={(v) => inr(v)} />
                <Legend />
                <Bar dataKey="pending" stackId="a" fill="#B08A3E" name="Pending" />
                <Bar dataKey="approved" stackId="a" fill="#0B1A5B" name="Approved" />
                <Bar dataKey="paid" stackId="a" fill="#7FB77E" name="Paid" />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
            <div className="rounded-md bg-neutral-50 p-2">
              <div className="text-muted-foreground">Pending</div>
              <div className="font-semibold tabular-nums">{inr(data?.commissions?.summary?.pending)}</div>
            </div>
            <div className="rounded-md bg-neutral-50 p-2">
              <div className="text-muted-foreground">Approved</div>
              <div className="font-semibold tabular-nums">{inr(data?.commissions?.summary?.approved)}</div>
            </div>
            <div className="rounded-md bg-neutral-50 p-2">
              <div className="text-muted-foreground">Paid</div>
              <div className="font-semibold tabular-nums">{inr(data?.commissions?.summary?.paid)}</div>
            </div>
          </div>
        </Card>

        <Card className="rw-card p-5" data-testid="subs-health-card">
          <p className="rw-eyebrow">Subscription health</p>
          <h2 className="rw-serif text-2xl">Inner Peace cohort</h2>
          <div className="mt-4 grid grid-cols-3 gap-3">
            <HealthTile label="Active" value={data?.subscriptions?.active} tone="royal" />
            <HealthTile label="Expiring 7d" value={data?.subscriptions?.expiring_7d} tone="gold" />
            <HealthTile label="Expired" value={data?.subscriptions?.expired} tone="muted" />
          </div>
          <div className="mt-5">
            <p className="rw-eyebrow">Activity meter</p>
            <div className="mt-2 space-y-2">
              <ActivityBar label="Green (4+ sessions)" value={data?.subscriptions?.activity?.green} total={sumActivity(data)} color="#7FB77E" />
              <ActivityBar label="Yellow (1–3 sessions)" value={data?.subscriptions?.activity?.yellow} total={sumActivity(data)} color="#E8A93A" />
              <ActivityBar label="Red (0 sessions)" value={data?.subscriptions?.activity?.red} total={sumActivity(data)} color="#D9534F" />
            </div>
          </div>
        </Card>
      </section>

      {/* Leaderboards */}
      <section className="mt-8 grid gap-6 lg:grid-cols-2">
        <LeaderboardCard
          title="Top earners" subtitle="Referral commissions"
          items={data?.leaderboard?.top_earners || []} accent="gold"
          testid="lb-earners"
        />
        <LeaderboardCard
          title="Top buyers" subtitle="Program purchases"
          items={data?.leaderboard?.top_buyers || []} accent="royal"
          testid="lb-buyers"
        />
      </section>

      {/* Geo table */}
      <Card className="rw-card mt-8 p-5" data-testid="states-card">
        <p className="rw-eyebrow">Geography</p>
        <h2 className="rw-serif text-2xl">Top states by revenue</h2>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-[11px] uppercase tracking-widest text-muted-foreground">
              <tr>
                <th className="pb-2 pr-4">Rank</th>
                <th className="pb-2 pr-4">State</th>
                <th className="pb-2 pr-4 text-right">Revenue</th>
                <th className="pb-2 pr-4 text-right">Purchases</th>
                <th className="pb-2 pr-4 text-right">Users</th>
                <th className="pb-2 text-right">Share</th>
              </tr>
            </thead>
            <tbody>
              {(data?.states || []).map((s, i) => {
                const total = (data?.kpis?.revenue?.revenue || 0) || 1;
                const share = ((s.revenue / total) * 100).toFixed(1);
                return (
                  <tr key={s.state} className="border-t">
                    <td className="py-2 pr-4 text-muted-foreground">#{i + 1}</td>
                    <td className="py-2 pr-4 font-medium">{s.state}</td>
                    <td className="py-2 pr-4 text-right tabular-nums font-semibold">{inr(s.revenue)}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{s.count}</td>
                    <td className="py-2 pr-4 text-right tabular-nums">{s.users}</td>
                    <td className="py-2 text-right tabular-nums">
                      <div className="inline-flex items-center gap-2">
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-neutral-200">
                          <div className="h-full bg-primary" style={{ width: `${Math.min(100, share)}%` }} />
                        </div>
                        {share}%
                      </div>
                    </td>
                  </tr>
                );
              })}
              {(data?.states || []).length === 0 && (
                <tr><td colSpan={6} className="py-6 text-center text-muted-foreground">No data</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Payouts + GST snapshot */}
      <section className="mt-8 grid gap-6 md:grid-cols-2">
        <Card className="rw-card p-5">
          <p className="rw-eyebrow">Payouts</p>
          <h2 className="rw-serif text-2xl">Cash-out</h2>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <Stat2 label="Pending" value={inr(data?.payouts?.pending_amount)} sub={`${data?.payouts?.pending_count} awaiting`} />
            <Stat2 label="Paid" value={inr(data?.payouts?.paid_amount)} sub={`${data?.payouts?.paid_count} completed`} />
          </div>
        </Card>
        <Card className="rw-card p-5">
          <p className="rw-eyebrow">GST</p>
          <h2 className="rw-serif text-2xl">Tax summary</h2>
          <div className="mt-3 grid grid-cols-3 gap-3">
            <Stat2 label="Taxable" value={inr(data?.gst?.taxable)} />
            <Stat2 label="GST" value={inr(data?.gst?.gst)} />
            <Stat2 label="Total" value={inr(data?.gst?.total)} sub={`${data?.gst?.count} txn`} />
          </div>
        </Card>
      </section>

      <div className="mt-8 flex justify-center">
        <Button asChild variant="secondary" size="lg" data-testid="analytics-open-reports">
          <a href="/admin/reports">
            <Download className="mr-2 h-4 w-4" /> Open detailed reports
          </a>
        </Button>
      </div>
    </div>
  );
}

/* ---------- Helper components ---------- */

function Kpi({ icon: Icon, label, value, sub, accent }) {
  return (
    <Card className={`p-4 ${accent ? "border-primary" : ""}`}>
      <div className="flex items-center justify-between">
        <div className={`grid h-9 w-9 place-items-center rounded-lg ${accent ? "bg-primary text-white" : "bg-primary/10 text-primary"}`}>
          <Icon className="h-4 w-4" />
        </div>
        <span className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</span>
      </div>
      <div className="mt-3 rw-serif text-2xl">{value ?? "—"}</div>
      {sub && <div className="text-[11px] text-muted-foreground">{sub}</div>}
    </Card>
  );
}

function Stat2({ label, value, sub }) {
  return (
    <div className="rounded-lg bg-neutral-50 p-3">
      <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="mt-1 rw-serif text-xl">{value}</div>
      {sub && <div className="text-[10px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

function HealthTile({ label, value, tone }) {
  const toneClass = {
    royal: "bg-primary/10 text-primary",
    gold: "bg-[hsl(var(--rw-gold-soft))] text-[hsl(35_60%_38%)]",
    muted: "bg-neutral-100 text-neutral-500",
  }[tone];
  return (
    <div className={`rounded-lg p-3 ${toneClass}`}>
      <div className="text-[10px] uppercase tracking-widest">{label}</div>
      <div className="mt-1 rw-serif text-2xl">{value ?? "—"}</div>
    </div>
  );
}

function ActivityBar({ label, value, total, color }) {
  const pct = total > 0 ? (value / total) * 100 : 0;
  return (
    <div>
      <div className="flex justify-between text-[11px]">
        <span>{label}</span>
        <span className="font-semibold">{value ?? 0}</span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-neutral-200">
        <div className="h-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

function LeaderboardCard({ title, subtitle, items, accent, testid }) {
  const dot = accent === "gold" ? "bg-[hsl(var(--rw-gold-soft))] text-[hsl(35_60%_38%)]" : "bg-primary/10 text-primary";
  return (
    <Card className="rw-card p-5" data-testid={testid}>
      <p className="rw-eyebrow">Leaderboard</p>
      <h2 className="rw-serif text-2xl">{title}</h2>
      <p className="text-xs text-muted-foreground">{subtitle}</p>
      <div className="mt-3 space-y-2">
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No data in period.</p>
        ) : items.map((r, i) => (
          <div key={r.membership_id + i} className="flex items-center gap-3">
            <div className={`grid h-8 w-8 place-items-center rounded-full font-semibold ${dot}`}>
              {i + 1}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold">{r.full_name}</div>
              <div className="font-mono text-[11px] text-muted-foreground">
                {r.membership_id} · {r.count} {accent === "gold" ? "commissions" : "purchases"}
              </div>
            </div>
            <div className="text-sm font-semibold tabular-nums">{inr(r.amount)}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function granularityLabel(g) {
  return { day: "Daily", week: "Weekly", month: "Monthly" }[g] || "Daily";
}

function sumActivity(d) {
  const a = d?.subscriptions?.activity;
  if (!a) return 0;
  return (a.green || 0) + (a.yellow || 0) + (a.red || 0);
}

function inr(v) {
  if (v === null || v === undefined) return "—";
  return `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}
