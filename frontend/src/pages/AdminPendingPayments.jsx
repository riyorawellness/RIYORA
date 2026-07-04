import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  CheckCircle2, XCircle, Eye, Download, Loader2, Search, Filter, RefreshCw,
  Clock, User, Calendar, IndianRupee, HashIcon,
} from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { manualPaymentsApi, resolveUploadUrl } from "@/services/manualPayments";
import { formatApiError } from "@/lib/api";

const TABS = [
  { key: "pending",  label: "Pending",  tone: "text-amber-700" },
  { key: "approved", label: "Approved", tone: "text-emerald-700" },
  { key: "rejected", label: "Rejected", tone: "text-red-700" },
  { key: "all",      label: "All",      tone: "text-neutral-700" },
];

export default function AdminPendingPayments() {
  const [status, setStatus] = useState("pending");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState({ items: [], total: 0, total_pages: 1 });
  const [summary, setSummary] = useState({ pending: { count: 0 }, approved: { count: 0 }, rejected: { count: 0 } });
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null); // { row, action }
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [viewer, setViewer] = useState(null); // { url }

  const load = async () => {
    setLoading(true);
    try {
      const [d, s] = await Promise.all([
        manualPaymentsApi.adminList({ status, page, page_size: 25, ...(q ? { q } : {}) }),
        manualPaymentsApi.adminSummary(),
      ]);
      setData(d);
      setSummary(s);
    } catch (e) {
      toast.error(formatApiError(e, "Load failed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [status, page]);

  const openAction = (row, action) => {
    setModal({ row, action });
    setReason("");
  };

  const doAction = async () => {
    if (modal.action === "reject" && !reason.trim()) {
      return toast.error("Please provide a rejection reason");
    }
    setBusy(true);
    try {
      await manualPaymentsApi.adminAction(modal.row.id, modal.action, {
        rejection_reason: modal.action === "reject" ? reason : undefined,
        remarks: modal.action === "approve" ? reason : undefined,
      });
      toast.success(modal.action === "approve" ? "Payment approved · program unlocked" : "Payment rejected");
      setModal(null);
      await load();
    } catch (e) {
      toast.error(formatApiError(e, "Action failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="px-6 py-6" data-testid="admin-pending-payments-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="rw-eyebrow">Payments · Manual QR</p>
          <h1 className="mt-1 rw-serif text-4xl">Payment Verification</h1>
          <p className="text-sm text-muted-foreground">
            Review, approve or reject user-submitted manual UPI payments.
          </p>
        </div>
        <div className="flex gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && (setPage(1), load())}
              className="w-64 pl-9"
              placeholder="UTR, name, membership ID…"
              data-testid="pv-search-input"
            />
          </div>
          <Button variant="ghost" onClick={() => { setPage(1); load(); }} disabled={loading} data-testid="pv-refresh-btn">
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {/* Summary tiles */}
      <section className="mt-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <SumTile label="Pending" count={summary.pending?.count} amount={summary.pending?.amount} tone="amber" testid="sum-pending" />
        <SumTile label="Approved" count={summary.approved?.count} amount={summary.approved?.amount} tone="emerald" testid="sum-approved" />
        <SumTile label="Rejected" count={summary.rejected?.count} amount={summary.rejected?.amount} tone="red" testid="sum-rejected" />
        <SumTile label="Total" count={
          (summary.pending?.count || 0) + (summary.approved?.count || 0) + (summary.rejected?.count || 0)
        } amount={
          (summary.pending?.amount || 0) + (summary.approved?.amount || 0) + (summary.rejected?.amount || 0)
        } tone="royal" testid="sum-total" />
      </section>

      <Tabs value={status} onValueChange={(v) => { setStatus(v); setPage(1); }} className="mt-6">
        <TabsList data-testid="pv-status-tabs">
          {TABS.map((t) => (
            <TabsTrigger key={t.key} value={t.key} data-testid={`pv-tab-${t.key}`}>{t.label}</TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Table */}
      <Card className="mt-4 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-primary/5 text-left text-[11px] uppercase tracking-widest text-primary">
              <tr>
                <th className="px-3 py-2">User</th>
                <th className="px-3 py-2">Program</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2">UTR</th>
                <th className="px-3 py-2">Txn date</th>
                <th className="px-3 py-2">Submitted</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody data-testid="pv-table-body">
              {loading ? (
                <tr><td colSpan={8} className="py-16 text-center"><Loader2 className="mx-auto h-5 w-5 animate-spin text-muted-foreground" /></td></tr>
              ) : data.items.length === 0 ? (
                <tr><td colSpan={8} className="py-12 text-center text-muted-foreground">No records for this filter.</td></tr>
              ) : data.items.map((r) => (
                <tr key={r.id} className="border-t align-top hover:bg-neutral-50" data-testid={`pv-row-${r.id}`}>
                  <td className="px-3 py-3">
                    <div className="font-medium">{r.user_name || "—"}</div>
                    <div className="font-mono text-[10px] text-muted-foreground">{r.user_membership_id}</div>
                  </td>
                  <td className="px-3 py-3">
                    <div className="text-sm">{r.program_name}</div>
                    <div className="text-[10px] text-muted-foreground">Level {r.program_level ?? "—"}</div>
                  </td>
                  <td className="px-3 py-3 text-right font-semibold tabular-nums">₹{Number(r.total).toLocaleString("en-IN")}</td>
                  <td className="px-3 py-3 font-mono text-[11px]">{r.utr}</td>
                  <td className="px-3 py-3 text-[11px] text-muted-foreground">{r.transaction_date?.slice(0, 10)}</td>
                  <td className="px-3 py-3 text-[11px] text-muted-foreground">{new Date(r.submitted_at).toLocaleString()}</td>
                  <td className="px-3 py-3">
                    <StatusPill status={r.status} />
                    {r.status === "rejected" && r.rejection_reason && (
                      <div className="mt-1 max-w-[180px] truncate text-[10px] text-red-700" title={r.rejection_reason}>{r.rejection_reason}</div>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex justify-end gap-1">
                      {r.screenshot_url && (
                        <>
                          <Button size="icon" variant="ghost" onClick={() => setViewer({ url: r.screenshot_url })} data-testid={`pv-view-${r.id}`}>
                            <Eye className="h-3.5 w-3.5" />
                          </Button>
                          <a href={resolveUploadUrl(r.screenshot_url)} download target="_blank" rel="noreferrer">
                            <Button size="icon" variant="ghost" data-testid={`pv-download-${r.id}`}>
                              <Download className="h-3.5 w-3.5" />
                            </Button>
                          </a>
                        </>
                      )}
                      {r.status === "pending" && (
                        <>
                          <Button size="sm" variant="secondary" onClick={() => openAction(r, "reject")} data-testid={`pv-reject-${r.id}`}>
                            <XCircle className="mr-1 h-3.5 w-3.5" /> Reject
                          </Button>
                          <Button size="sm" onClick={() => openAction(r, "approve")} data-testid={`pv-approve-${r.id}`}>
                            <CheckCircle2 className="mr-1 h-3.5 w-3.5" /> Approve
                          </Button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data.total > 25 && (
          <div className="flex items-center justify-between border-t px-4 py-3 text-sm">
            <div className="text-muted-foreground">Page {page} of {data.total_pages}</div>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)} data-testid="pv-prev">Prev</Button>
              <Button size="sm" variant="secondary" disabled={page >= data.total_pages} onClick={() => setPage(page + 1)} data-testid="pv-next">Next</Button>
            </div>
          </div>
        )}
      </Card>

      {/* Approve/Reject dialog */}
      <Dialog open={!!modal} onOpenChange={(o) => !o && setModal(null)}>
        <DialogContent data-testid="pv-action-dialog">
          <DialogHeader>
            <DialogTitle>
              {modal?.action === "approve" ? "Approve payment" : "Reject payment"}
            </DialogTitle>
          </DialogHeader>
          {modal?.row && (
            <div className="space-y-3 text-sm">
              <Detail k="User" v={<><User className="mr-1 inline h-3 w-3" />{modal.row.user_name} · {modal.row.user_membership_id}</>} />
              <Detail k="Program" v={modal.row.program_name} />
              <Detail k="Amount" v={<><IndianRupee className="mr-0.5 inline h-3 w-3" />{Number(modal.row.total).toLocaleString("en-IN")}</>} />
              <Detail k="UTR" v={<span className="font-mono">{modal.row.utr}</span>} />
              <Detail k="Txn date" v={<><Calendar className="mr-1 inline h-3 w-3" />{modal.row.transaction_date?.slice(0, 10)}</>} />
              {modal.row.remarks && <Detail k="User remarks" v={<span className="italic">{modal.row.remarks}</span>} />}

              {modal.action === "approve" ? (
                <div className="rounded-lg bg-emerald-50 p-3 text-emerald-900">
                  <div className="text-xs font-semibold">On approve</div>
                  <ul className="mt-1 list-inside list-disc text-xs">
                    <li>Program will be unlocked immediately</li>
                    <li>Purchase record + invoice will be generated</li>
                    <li>3-level referral commissions will be created</li>
                    <li>User will be notified</li>
                  </ul>
                  <div className="mt-2">
                    <label className="text-[10px] font-semibold uppercase tracking-widest">Optional remarks</label>
                    <Textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Internal note (optional)" data-testid="pv-approve-remarks" />
                  </div>
                </div>
              ) : (
                <div>
                  <label className="text-[10px] font-semibold uppercase tracking-widest">Rejection reason *</label>
                  <Textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Explain why this payment is being rejected — the user will see this." data-testid="pv-reject-reason" required />
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setModal(null)}>Cancel</Button>
            <Button
              onClick={doAction}
              disabled={busy}
              variant={modal?.action === "reject" ? "destructive" : "default"}
              data-testid="pv-confirm-btn"
            >
              {busy && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Confirm {modal?.action}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Screenshot viewer */}
      <Dialog open={!!viewer} onOpenChange={(o) => !o && setViewer(null)}>
        <DialogContent className="max-w-2xl" data-testid="pv-viewer-dialog">
          <DialogHeader><DialogTitle>Payment screenshot</DialogTitle></DialogHeader>
          {viewer?.url && (
            <img src={resolveUploadUrl(viewer.url)} alt="Screenshot" className="w-full rounded-lg object-contain" />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function SumTile({ label, count, amount, tone, testid }) {
  const tones = {
    amber: "bg-amber-50 text-amber-800",
    emerald: "bg-emerald-50 text-emerald-800",
    red: "bg-red-50 text-red-800",
    royal: "bg-primary/5 text-primary",
  };
  return (
    <Card className={`p-4 ${tones[tone]}`} data-testid={testid}>
      <div className="rw-eyebrow">{label}</div>
      <div className="mt-2 flex items-baseline justify-between">
        <div className="rw-serif text-3xl">{count ?? 0}</div>
        <div className="text-xs tabular-nums opacity-80">₹{Number(amount || 0).toLocaleString("en-IN")}</div>
      </div>
    </Card>
  );
}

function StatusPill({ status }) {
  const meta = {
    pending:  { label: "Pending",  cls: "bg-amber-100 text-amber-800" },
    approved: { label: "Approved", cls: "bg-emerald-100 text-emerald-800" },
    rejected: { label: "Rejected", cls: "bg-red-100 text-red-800" },
  }[status] || { label: status, cls: "bg-neutral-100" };
  return <Badge className={meta.cls}>{meta.label}</Badge>;
}

function Detail({ k, v }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b pb-1 text-xs">
      <span className="text-muted-foreground">{k}</span>
      <span className="text-right font-medium">{v}</span>
    </div>
  );
}
