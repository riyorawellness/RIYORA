import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Download, Loader2, Search, FileText, FileSpreadsheet, FileType } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { adminReportsApi, downloadBlob } from "@/services/analytics";
import { formatApiError } from "@/lib/api";

const REPORT_TYPES = [
  { key: "users",         label: "Users" },
  { key: "programs",      label: "Programs" },
  { key: "subscriptions", label: "Subscriptions" },
  { key: "payments",      label: "Payments" },
  { key: "referrals",     label: "Referrals" },
  { key: "activity",      label: "Activity" },
  { key: "assessments",   label: "Assessments" },
];

const STATUS_OPTIONS = {
  users:         ["active", "suspended", "deactivated"],
  programs:      ["active", "inactive"],
  subscriptions: ["active", "expired", "cancelled"],
  payments:      ["active", "expired", "refunded"],
  referrals:     ["pending", "approved", "paid", "rejected"],
  activity:      [],
  assessments:   [],
};

function todayISO(offset = 0) {
  const d = new Date(); d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}

export default function AdminReports() {
  const [type, setType] = useState("payments");
  const [since, setSince] = useState(todayISO(-89));
  const [until, setUntil] = useState(todayISO());
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [level, setLevel] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(null);

  const load = async (opts = {}) => {
    setLoading(true);
    try {
      const params = {
        since, until, page: opts.page ?? page, page_size: pageSize,
        ...(q ? { q } : {}),
        ...(status ? { status } : {}),
        ...(level ? { level } : {}),
      };
      const d = await adminReportsApi.list(opts.type ?? type, params);
      setData(d);
    } catch (e) {
      toast.error(formatApiError(e, "Failed to load report"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load({ type });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const changeType = (v) => {
    setType(v);
    setStatus("");
    setLevel("");
    setPage(1);
    load({ type: v, page: 1 });
  };

  const doSearch = () => {
    setPage(1);
    load({ page: 1 });
  };

  const exportFile = async (fmt) => {
    setExporting(fmt);
    try {
      const params = {
        since, until,
        ...(q ? { q } : {}),
        ...(status ? { status } : {}),
        ...(level ? { level } : {}),
      };
      const blob = await adminReportsApi.exportBlob(type, fmt, params);
      const ext = { csv: "csv", excel: "xlsx", pdf: "pdf" }[fmt];
      downloadBlob(blob, `riyora-${type}-${todayISO()}.${ext}`);
      toast.success(`${type}.${ext} downloaded`);
    } catch (e) {
      toast.error(formatApiError(e, "Export failed"));
    } finally {
      setExporting(null);
    }
  };

  const columns = data?.columns || [];
  const items = data?.items || [];
  const total = data?.total ?? 0;
  const totalPages = data?.total_pages ?? 1;

  return (
    <div className="px-6 py-6" data-testid="admin-reports-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="rw-eyebrow">Reports & Exports</p>
          <h1 className="mt-1 rw-serif text-4xl">Detailed Reports</h1>
          <p className="text-sm text-muted-foreground">
            Filter, preview, export to CSV / Excel / PDF.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" disabled={exporting !== null} onClick={() => exportFile("csv")} data-testid="export-csv">
            {exporting === "csv" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="mr-1 h-4 w-4" />} CSV
          </Button>
          <Button variant="secondary" size="sm" disabled={exporting !== null} onClick={() => exportFile("excel")} data-testid="export-excel">
            {exporting === "excel" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSpreadsheet className="mr-1 h-4 w-4" />} Excel
          </Button>
          <Button size="sm" disabled={exporting !== null} onClick={() => exportFile("pdf")} data-testid="export-pdf">
            {exporting === "pdf" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileType className="mr-1 h-4 w-4" />} PDF
          </Button>
        </div>
      </div>

      {/* Report type tabs */}
      <Tabs value={type} onValueChange={changeType} className="mt-6">
        <TabsList className="flex flex-wrap justify-start" data-testid="reports-type-tabs">
          {REPORT_TYPES.map((r) => (
            <TabsTrigger key={r.key} value={r.key} data-testid={`report-tab-${r.key}`}>
              {r.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Filters */}
      <Card className="mt-4 p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="text-[10px] uppercase tracking-widest text-muted-foreground">Search</label>
            <div className="mt-1 flex items-center gap-2">
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, ID, mobile…"
                className="w-56" data-testid="reports-search" onKeyDown={(e) => e.key === "Enter" && doSearch()} />
            </div>
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-widest text-muted-foreground">Since</label>
            <Input type="date" value={since} onChange={(e) => setSince(e.target.value)} className="mt-1 w-40" data-testid="reports-since" />
          </div>
          <div>
            <label className="text-[10px] uppercase tracking-widest text-muted-foreground">Until</label>
            <Input type="date" value={until} onChange={(e) => setUntil(e.target.value)} className="mt-1 w-40" data-testid="reports-until" />
          </div>
          {STATUS_OPTIONS[type]?.length > 0 && (
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted-foreground">Status</label>
              <Select value={status || "all"} onValueChange={(v) => setStatus(v === "all" ? "" : v)}>
                <SelectTrigger className="mt-1 w-36" data-testid="reports-status"><SelectValue placeholder="All" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  {STATUS_OPTIONS[type].map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}
          {type === "referrals" && (
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted-foreground">Level</label>
              <Select value={level || "all"} onValueChange={(v) => setLevel(v === "all" ? "" : v)}>
                <SelectTrigger className="mt-1 w-28" data-testid="reports-level"><SelectValue placeholder="All" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="1">L1</SelectItem>
                  <SelectItem value="2">L2</SelectItem>
                  <SelectItem value="3">L3</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
          <Button onClick={doSearch} data-testid="reports-apply">
            <Search className="mr-1 h-4 w-4" /> Apply
          </Button>
          <Badge variant="secondary" className="ml-auto" data-testid="reports-total">
            {total} row(s)
          </Badge>
        </div>
      </Card>

      {/* Table */}
      <Card className="mt-4 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-primary/5 text-left text-[11px] uppercase tracking-widest text-primary">
              <tr>
                {columns.map((c) => <th key={c.key} className="whitespace-nowrap px-3 py-2">{c.label}</th>)}
              </tr>
            </thead>
            <tbody data-testid="reports-table-body">
              {loading ? (
                <tr><td colSpan={columns.length} className="py-16 text-center text-muted-foreground">
                  <Loader2 className="mx-auto h-5 w-5 animate-spin" />
                </td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={columns.length || 1} className="py-12 text-center text-muted-foreground">
                  No records found for the current filters.
                </td></tr>
              ) : items.map((row, i) => (
                <tr key={i} className="border-t hover:bg-neutral-50">
                  {columns.map((c) => (
                    <td key={c.key} className="whitespace-nowrap px-3 py-2">
                      {renderCell(row[c.key], c.type)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* Pagination */}
        {total > pageSize && (
          <div className="flex items-center justify-between border-t px-4 py-3 text-sm">
            <div className="text-muted-foreground">Page {page} of {totalPages}</div>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={page <= 1}
                onClick={() => { const p = page - 1; setPage(p); load({ page: p }); }}
                data-testid="reports-prev">
                Prev
              </Button>
              <Button size="sm" variant="secondary" disabled={page >= totalPages}
                onClick={() => { const p = page + 1; setPage(p); load({ page: p }); }}
                data-testid="reports-next">
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      <div className="mt-6 flex items-center justify-center gap-4 text-xs text-muted-foreground">
        <Download className="h-3 w-3" />
        Exports include ALL matching rows (up to 20,000), not just the current page.
      </div>
    </div>
  );
}

function renderCell(value, type) {
  if (value === null || value === undefined || value === "") return <span className="text-muted-foreground">—</span>;
  if (type === "money") {
    return <span className="tabular-nums font-medium">₹{Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>;
  }
  if (type === "int") return <span className="tabular-nums">{Number(value).toLocaleString("en-IN")}</span>;
  if (type === "bool") {
    return <Badge variant={value ? "default" : "secondary"} className="text-[10px]">{value ? "Yes" : "No"}</Badge>;
  }
  if (type === "date" || type === "datetime") {
    try {
      const d = new Date(value);
      return <span className="text-muted-foreground">{type === "date"
        ? d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "2-digit" })
        : d.toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
      </span>;
    } catch { return value; }
  }
  return String(value);
}
