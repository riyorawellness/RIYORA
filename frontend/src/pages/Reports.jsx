import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Download, FileText, FileSpreadsheet, Loader2, TrendingUp, Users, IndianRupee, Activity } from "lucide-react";
import {
  AreaChart, Area, BarChart, Bar, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid,
} from "recharts";

import TopBar from "@/components/TopBar";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { analyticsApi, userReportsApi, downloadBlob } from "@/services/analytics";
import { formatApiError } from "@/lib/api";

const REPORTS = [
  { key: "referral",     title: "Referral Report",     body: "3-level downline with join dates and status." },
  { key: "income",       title: "Income Report",       body: "Commission ledger + summary buckets." },
  { key: "downline",     title: "Downline Report",     body: "Pure hierarchy tree by level." },
  { key: "subscription", title: "Subscription Report", body: "Inner Peace cycles + activity counts." },
  { key: "transaction",  title: "Transaction Report",  body: "All payments with GST breakdown." },
];

export default function Reports() {
  const [downloading, setDownloading] = useState(null);
  const [personal, setPersonal] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const d = await analyticsApi.me();
        setPersonal(d);
      } catch (e) {
        toast.error(formatApiError(e, "Failed to load personal analytics"));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const download = async (type, fmt) => {
    const key = `${type}.${fmt}`;
    setDownloading(key);
    try {
      const blob = await userReportsApi.downloadReport(type, fmt);
      const ext = { pdf: "pdf", csv: "csv", excel: "xlsx" }[fmt];
      downloadBlob(blob, `riyora-${type}-report.${ext}`);
      toast.success(`${type} report downloaded`);
    } catch (e) {
      toast.error(formatApiError(e, "Download failed"));
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="px-4 pt-3 pb-24">
      <TopBar title="Reports & Analytics" subtitle="Your personal insights" />

      {/* Summary tiles */}
      <section className="mt-4 grid grid-cols-2 gap-3" data-testid="user-analytics-kpis">
        <PersonalTile
          icon={IndianRupee} label="Lifetime earnings"
          value={inr(personal?.earnings?.lifetime)} accent
        />
        <PersonalTile
          icon={TrendingUp} label="This month"
          value={inr(personal?.earnings?.current_month)}
        />
        <PersonalTile
          icon={Users} label="Downline (3 lvls)"
          value={loading ? "…" : (
            (personal?.downline_counts?.L1 || 0) +
            (personal?.downline_counts?.L2 || 0) +
            (personal?.downline_counts?.L3 || 0)
          )}
          sub={personal ? `L1 ${personal.downline_counts.L1} · L2 ${personal.downline_counts.L2} · L3 ${personal.downline_counts.L3}` : ""}
        />
        <PersonalTile
          icon={Activity} label="Activity status"
          value={statusLabel(personal?.activity_meter?.status)}
          sub={personal?.activity_meter ? `${personal.activity_meter.completed}/${personal.activity_meter.required} sessions` : ""}
        />
      </section>

      {/* Earnings chart */}
      <Card className="rw-card mt-4 p-4" data-testid="user-earnings-chart">
        <div className="flex items-center justify-between">
          <div>
            <p className="rw-eyebrow">Last 90 days</p>
            <h2 className="rw-serif text-xl">Earnings trend</h2>
          </div>
          <Badge variant="secondary">{personal?.earnings_series?.length ?? 0} days</Badge>
        </div>
        <div className="mt-3" style={{ height: 160 }}>
          {loading ? (
            <div className="grid h-full place-items-center text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin" /></div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={personal?.earnings_series || []}>
                <defs>
                  <linearGradient id="uear" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#B08A3E" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#B08A3E" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="bucket" tick={{ fontSize: 9 }} tickFormatter={(v) => v?.slice(5)} />
                <YAxis tick={{ fontSize: 9 }} tickFormatter={(v) => `₹${v}`} />
                <Tooltip formatter={(v) => inr(v)} />
                <Area type="monotone" dataKey="amount" stroke="#B08A3E" fill="url(#uear)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>

      {/* Downline growth chart */}
      <Card className="rw-card mt-4 p-4" data-testid="user-downline-chart">
        <div className="flex items-center justify-between">
          <div>
            <p className="rw-eyebrow">Direct joins</p>
            <h2 className="rw-serif text-xl">Team growth</h2>
          </div>
          <Badge variant="secondary">L1 only</Badge>
        </div>
        <div className="mt-3" style={{ height: 140 }}>
          {loading ? (
            <div className="grid h-full place-items-center text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin" /></div>
          ) : (personal?.downline_series?.length || 0) === 0 ? (
            <div className="grid h-full place-items-center text-xs text-muted-foreground">No joins in the last 90 days.</div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={personal?.downline_series || []}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
                <XAxis dataKey="bucket" tick={{ fontSize: 9 }} tickFormatter={(v) => v?.slice(5)} />
                <YAxis tick={{ fontSize: 9 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#0B1A5B" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>

      <h2 className="rw-eyebrow mt-6">Downloadable reports</h2>
      <div className="mt-2 space-y-3" data-testid="reports-list">
        {REPORTS.map((r) => (
          <div key={r.key} className="rw-card p-4" data-testid={`report-${r.key}`}>
            <div className="flex items-start gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-full bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal))]">
                <FileText className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="rw-serif text-lg">{r.title}</h3>
                <p className="text-xs text-muted-foreground">{r.body}</p>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <FmtBtn label="PDF" fmt="pdf" typeKey={r.key} downloading={downloading} onClick={download} icon={FileText} />
              <FmtBtn label="Excel" fmt="excel" typeKey={r.key} downloading={downloading} onClick={download} icon={FileSpreadsheet} />
              <FmtBtn label="CSV" fmt="csv" typeKey={r.key} downloading={downloading} onClick={download} icon={Download} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FmtBtn({ label, fmt, typeKey, downloading, onClick, icon: Icon }) {
  const busy = downloading === `${typeKey}.${fmt}`;
  return (
    <button
      onClick={() => onClick(typeKey, fmt)}
      disabled={downloading !== null}
      className="flex items-center justify-center gap-1.5 rounded-md border border-neutral-200 bg-white py-2 text-xs font-medium hover:bg-neutral-50 disabled:opacity-50"
      data-testid={`report-download-${typeKey}-${fmt}`}
    >
      {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
      {label}
    </button>
  );
}

function PersonalTile({ icon: Icon, label, value, sub, accent }) {
  return (
    <Card className={`p-3 ${accent ? "border-primary" : ""}`}>
      <div className="flex items-center justify-between">
        <div className={`grid h-8 w-8 place-items-center rounded-lg ${accent ? "bg-primary text-white" : "bg-primary/10 text-primary"}`}>
          <Icon className="h-4 w-4" />
        </div>
        <span className="text-[9px] uppercase tracking-widest text-muted-foreground">{label}</span>
      </div>
      <div className="mt-2 rw-serif text-xl">{value ?? "—"}</div>
      {sub && <div className="text-[10px] text-muted-foreground">{sub}</div>}
    </Card>
  );
}

function statusLabel(s) {
  return { green: "Green", yellow: "Yellow", red: "Red", no_subscription: "No sub" }[s] || "—";
}

function inr(v) {
  if (v === null || v === undefined) return "—";
  return `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}
