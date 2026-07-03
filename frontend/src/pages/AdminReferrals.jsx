import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  LogOut,
  Loader2,
  Search,
  Check,
  X,
  Wallet,
  Settings2,
  Users,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import Logo from "@/components/Logo";

import { useAuth } from "@/context/AuthContext";
import {
  commissionsApi,
  payoutsApi,
  referralsApi,
} from "@/services/referrals";
import { formatApiError } from "@/lib/api";

const TABS = [
  { key: "commissions", label: "Commissions", icon: Wallet },
  { key: "payouts", label: "Payouts", icon: Users },
  { key: "settings", label: "Settings", icon: Settings2 },
];

export default function AdminReferrals() {
  const nav = useNavigate();
  const { admin, logout } = useAuth();
  const [tab, setTab] = useState("commissions");

  const doLogout = async () => {
    await logout();
    nav("/", { replace: true });
  };

  return (
    <div className="min-h-screen rw-hero-radial rw-grain">
      <header className="rw-container flex items-center justify-between py-6">
        <div className="flex items-center gap-3">
          <Logo size="sm" />
          <Badge variant="secondary">Admin</Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            onClick={() => nav("/admin/dashboard")}
            data-testid="admin-nav-dashboard"
          >
            Dashboard
          </Button>
          <Button
            variant="secondary"
            onClick={() => nav("/admin/payments")}
            data-testid="admin-nav-payments"
          >
            Payments
          </Button>
          <Button
            variant="secondary"
            onClick={doLogout}
            data-testid="admin-ref-logout"
          >
            <LogOut className="mr-1 h-4 w-4" /> Sign out
          </Button>
        </div>
      </header>

      <main className="rw-container pb-16">
        <p className="rw-eyebrow">Refer &amp; Earn</p>
        <h1 className="mt-2 rw-serif text-5xl text-foreground">
          Referrals · <span className="text-primary">{admin?.name}</span>
        </h1>

        <div className="mt-6 flex gap-2 border-b border-neutral-200">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-semibold ${
                tab === t.key
                  ? "border-b-2 border-primary text-primary"
                  : "text-muted-foreground"
              }`}
              data-testid={`admin-ref-tab-${t.key}`}
            >
              <t.icon className="h-4 w-4" />
              {t.label}
            </button>
          ))}
        </div>

        <div className="mt-6">
          {tab === "commissions" && <CommissionsTab />}
          {tab === "payouts" && <PayoutsTab />}
          {tab === "settings" && <SettingsTab />}
        </div>
      </main>
    </div>
  );
}

// -------- Commissions Tab --------
function CommissionsTab() {
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(new Set());
  const [reasonDialog, setReasonDialog] = useState(null); // { id, action }
  const [reason, setReason] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [list, sum] = await Promise.all([
        commissionsApi.adminList({
          q: q || undefined,
          status: status || undefined,
          page_size: 200,
        }),
        commissionsApi.adminSummary(),
      ]);
      setItems(list.items || []);
      setSummary(sum);
    } catch (e) {
      toast.error(formatApiError(e, "Load failed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggle = (id) => {
    setSelected((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const bulkApprove = async () => {
    if (!selected.size) return;
    try {
      const res = await commissionsApi.adminBulkApprove(Array.from(selected));
      toast.success(`Approved ${res.approved} commission(s)`);
      setSelected(new Set());
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Bulk approve failed"));
    }
  };

  const doAction = async () => {
    if (!reasonDialog) return;
    try {
      if (reasonDialog.action === "approve") {
        await commissionsApi.adminApprove(reasonDialog.id, reason);
        toast.success("Commission approved");
      } else {
        await commissionsApi.adminReject(reasonDialog.id, reason);
        toast.success("Commission rejected");
      }
      setReasonDialog(null);
      setReason("");
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Action failed"));
    }
  };

  return (
    <>
      <section className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Pending" value={summary?.buckets?.pending?.amount} count={summary?.buckets?.pending?.count} />
        <Stat label="Approved · payable" value={summary?.payable_now} count={summary?.buckets?.approved?.count} accent />
        <Stat label="Paid" value={summary?.buckets?.paid?.amount} count={summary?.buckets?.paid?.count} />
        <Stat label="Rejected" value={summary?.buckets?.rejected?.amount} count={summary?.buckets?.rejected?.count} />
      </section>

      <section className="mt-6 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search buyer / sponsor / membership id"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="pl-9"
            data-testid="admin-comm-search"
          />
        </div>
        <select
          className="h-10 rounded-md border bg-white px-3 text-sm"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          data-testid="admin-comm-status"
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="paid">Paid</option>
          <option value="rejected">Rejected</option>
        </select>
        <Button onClick={load} data-testid="admin-comm-apply">Apply</Button>
        <Button
          onClick={bulkApprove}
          disabled={!selected.size}
          variant="outline"
          data-testid="admin-comm-bulk-approve"
        >
          <Check className="mr-1 h-4 w-4" /> Bulk approve ({selected.size})
        </Button>
      </section>

      <Card className="rw-card mt-4 overflow-x-auto p-0">
        {loading ? (
          <div className="grid place-items-center py-14 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : (
          <Table data-testid="admin-comm-table">
            <TableHeader>
              <TableRow>
                <TableHead className="w-8"></TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Buyer</TableHead>
                <TableHead>Sponsor</TableHead>
                <TableHead>Program</TableHead>
                <TableHead>Level</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((c) => (
                <TableRow key={c.id}>
                  <TableCell>
                    <input
                      type="checkbox"
                      checked={selected.has(c.id)}
                      onChange={() => toggle(c.id)}
                      disabled={c.status !== "pending"}
                      data-testid={`admin-comm-select-${c.id}`}
                    />
                  </TableCell>
                  <TableCell>{formatDate(c.created_at)}</TableCell>
                  <TableCell>
                    <div className="font-medium">{c.buyer_name || "—"}</div>
                    <div className="font-mono text-xs text-muted-foreground">
                      {c.buyer_membership_id}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="font-medium">{c.sponsor_name || "—"}</div>
                    <div className="font-mono text-xs text-muted-foreground">
                      {c.sponsor_membership_id}
                    </div>
                  </TableCell>
                  <TableCell className="max-w-[160px] truncate">
                    {c.program_name}
                  </TableCell>
                  <TableCell>L{c.level}</TableCell>
                  <TableCell>₹{Number(c.amount).toLocaleString("en-IN")}</TableCell>
                  <TableCell>
                    <Badge variant={c.status === "approved" ? "default" : "secondary"}>
                      {c.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    {c.status === "pending" && (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => setReasonDialog({ id: c.id, action: "approve" })}
                          data-testid={`admin-comm-approve-${c.id}`}
                        >
                          <Check className="h-3 w-3" />
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="ml-1"
                          onClick={() => setReasonDialog({ id: c.id, action: "reject" })}
                          data-testid={`admin-comm-reject-${c.id}`}
                        >
                          <X className="h-3 w-3" />
                        </Button>
                      </>
                    )}
                  </TableCell>
                </TableRow>
              ))}
              {items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="py-14 text-center text-muted-foreground">
                    No commissions.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </Card>

      <Dialog
        open={!!reasonDialog}
        onOpenChange={(o) => !o && setReasonDialog(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {reasonDialog?.action === "approve" ? "Approve commission" : "Reject commission"}
            </DialogTitle>
          </DialogHeader>
          <Input
            placeholder="Reason (optional)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            data-testid="admin-comm-reason"
          />
          <Button onClick={doAction} data-testid="admin-comm-confirm">
            Confirm
          </Button>
        </DialogContent>
      </Dialog>
    </>
  );
}

// -------- Payouts Tab --------
function PayoutsTab() {
  const [queue, setQueue] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [payDialog, setPayDialog] = useState(null); // payout row
  const [payRef, setPayRef] = useState("");
  const [payNotes, setPayNotes] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [q, list] = await Promise.all([
        payoutsApi.adminPendingByUser(),
        payoutsApi.adminList({ page_size: 200 }),
      ]);
      setQueue(q.items || []);
      setPayouts(list.items || []);
    } catch (e) {
      toast.error(formatApiError(e, "Load failed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const createPayout = async (row) => {
    try {
      await payoutsApi.adminCreate({
        user_membership_id: row.user_membership_id,
        commission_ids: row.commission_ids,
        method: row.bank_details ? "bank" : "manual",
      });
      toast.success(`Payout created for ${row.user_membership_id}`);
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Payout creation failed"));
    }
  };

  const markPaid = async () => {
    if (!payDialog || !payRef.trim()) {
      toast.error("Reference required");
      return;
    }
    try {
      await payoutsApi.adminMarkPaid(payDialog.id, {
        reference: payRef,
        notes: payNotes,
      });
      toast.success("Payout marked paid");
      setPayDialog(null);
      setPayRef("");
      setPayNotes("");
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Mark paid failed"));
    }
  };

  return (
    <>
      <h2 className="rw-serif text-2xl">Payout queue</h2>
      <p className="text-sm text-muted-foreground">
        Members with approved commissions ready to be paid out.
      </p>

      <Card className="rw-card mt-3 overflow-x-auto p-0">
        {loading ? (
          <div className="grid place-items-center py-14 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : (
          <Table data-testid="admin-payout-queue">
            <TableHeader>
              <TableRow>
                <TableHead>Member</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Commissions</TableHead>
                <TableHead>Bank</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {queue.map((r) => (
                <TableRow key={r.user_membership_id}>
                  <TableCell>
                    <div className="font-medium">{r.sponsor_name}</div>
                    <div className="font-mono text-xs text-muted-foreground">
                      {r.user_membership_id}
                    </div>
                  </TableCell>
                  <TableCell>₹{Number(r.amount).toLocaleString("en-IN")}</TableCell>
                  <TableCell>{r.commission_count}</TableCell>
                  <TableCell className="text-xs">
                    {r.bank_details ? (
                      <span className="font-mono">
                        {r.bank_details.bank_name} · {mask(r.bank_details.account_number)}
                      </span>
                    ) : (
                      <span className="text-amber-600">Missing bank details</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      onClick={() => createPayout(r)}
                      data-testid={`admin-payout-create-${r.user_membership_id}`}
                    >
                      Create payout
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {queue.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">
                    No approved commissions awaiting payout.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </Card>

      <h2 className="mt-8 rw-serif text-2xl">Recent payouts</h2>
      <Card className="rw-card mt-3 overflow-x-auto p-0">
        <Table data-testid="admin-payout-list">
          <TableHeader>
            <TableRow>
              <TableHead>Date</TableHead>
              <TableHead>Member</TableHead>
              <TableHead>Amount</TableHead>
              <TableHead>Method</TableHead>
              <TableHead>Reference</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {payouts.map((p) => (
              <TableRow key={p.id}>
                <TableCell>{formatDate(p.created_at)}</TableCell>
                <TableCell className="font-mono text-xs">
                  {p.user_membership_id}
                </TableCell>
                <TableCell>₹{Number(p.amount).toLocaleString("en-IN")}</TableCell>
                <TableCell>{p.method}</TableCell>
                <TableCell className="font-mono text-xs">
                  {p.reference || "—"}
                </TableCell>
                <TableCell>
                  <Badge variant={p.status === "paid" ? "default" : "secondary"}>
                    {p.status}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  {p.status === "pending" && (
                    <Button
                      size="sm"
                      onClick={() => setPayDialog(p)}
                      data-testid={`admin-payout-markpaid-${p.id}`}
                    >
                      Mark paid
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {payouts.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="py-10 text-center text-muted-foreground">
                  No payouts issued.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </Card>

      <Dialog open={!!payDialog} onOpenChange={(o) => !o && setPayDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Mark payout as paid</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="text-sm">
              Amount: ₹{Number(payDialog?.amount || 0).toLocaleString("en-IN")}
            </div>
            <div>
              <Label>Bank / UPI reference</Label>
              <Input
                value={payRef}
                onChange={(e) => setPayRef(e.target.value)}
                placeholder="UTR / txn id"
                data-testid="admin-payout-reference"
              />
            </div>
            <div>
              <Label>Notes (optional)</Label>
              <Input
                value={payNotes}
                onChange={(e) => setPayNotes(e.target.value)}
                data-testid="admin-payout-notes"
              />
            </div>
            <Button
              onClick={markPaid}
              className="w-full"
              data-testid="admin-payout-confirm"
            >
              Confirm paid
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

// -------- Settings Tab --------
function SettingsTab() {
  const [s, setS] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        setS(await referralsApi.adminGetSettings());
      } catch (e) {
        toast.error(formatApiError(e, "Load failed"));
      }
    })();
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        commission_l1_percent: num(s.commission_l1_percent),
        commission_l2_percent: num(s.commission_l2_percent),
        commission_l3_percent: num(s.commission_l3_percent),
        commission_l1_fixed: num(s.commission_l1_fixed),
        commission_l2_fixed: num(s.commission_l2_fixed),
        commission_l3_fixed: num(s.commission_l3_fixed),
        commission_mode: s.commission_mode,
        grace_period_days: num(s.grace_period_days),
        activity_sessions_required: num(s.activity_sessions_required),
      };
      const updated = await referralsApi.adminUpdateSettings(payload);
      setS(updated);
      toast.success("Settings saved");
    } catch (e) {
      toast.error(formatApiError(e, "Save failed"));
    } finally {
      setSaving(false);
    }
  };

  if (!s)
    return (
      <div className="grid place-items-center py-14 text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );

  return (
    <Card className="rw-card p-6">
      <h2 className="rw-serif text-2xl">Referral rules</h2>
      <p className="text-sm text-muted-foreground">
        Applies to all programs unless a program-level override exists.
      </p>

      <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <Label>Commission mode</Label>
          <select
            className="mt-1 h-10 w-full rounded-md border bg-white px-3 text-sm"
            value={s.commission_mode || "percent"}
            onChange={(e) => setS({ ...s, commission_mode: e.target.value })}
            data-testid="admin-settings-mode"
          >
            <option value="percent">Percent</option>
            <option value="fixed">Fixed</option>
            <option value="both">Both (percent + fixed)</option>
          </select>
        </div>

        <div>
          <Label>Activity sessions required per cycle</Label>
          <Input
            type="number"
            value={s.activity_sessions_required ?? 4}
            onChange={(e) => setS({ ...s, activity_sessions_required: e.target.value })}
            data-testid="admin-settings-sessions"
          />
        </div>
        <div>
          <Label>Grace period (days)</Label>
          <Input
            type="number"
            value={s.grace_period_days ?? 3}
            onChange={(e) => setS({ ...s, grace_period_days: e.target.value })}
            data-testid="admin-settings-grace"
          />
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
        {[1, 2, 3].map((l) => (
          <Card key={l} className="p-4">
            <h3 className="rw-serif text-lg">Level {l}</h3>
            <div className="mt-3 space-y-2">
              <div>
                <Label>Percent (%)</Label>
                <Input
                  type="number"
                  value={s[`commission_l${l}_percent`] ?? ""}
                  onChange={(e) =>
                    setS({ ...s, [`commission_l${l}_percent`]: e.target.value })
                  }
                  data-testid={`admin-settings-l${l}-percent`}
                />
              </div>
              <div>
                <Label>Fixed (₹)</Label>
                <Input
                  type="number"
                  value={s[`commission_l${l}_fixed`] ?? ""}
                  onChange={(e) =>
                    setS({ ...s, [`commission_l${l}_fixed`]: e.target.value })
                  }
                  data-testid={`admin-settings-l${l}-fixed`}
                />
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Button
        onClick={save}
        disabled={saving}
        className="mt-6"
        data-testid="admin-settings-save"
      >
        {saving ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : null}
        Save settings
      </Button>
    </Card>
  );
}

function Stat({ label, value, count, accent }) {
  return (
    <Card className={`p-4 ${accent ? "border-primary" : ""}`}>
      <div className="text-[11px] uppercase tracking-widest text-muted-foreground">
        {label}
      </div>
      <div className="mt-2 rw-serif text-3xl">
        ₹{Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}
      </div>
      <div className="mt-1 text-xs text-muted-foreground">{count || 0} txn</div>
    </Card>
  );
}

function num(v) {
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(v);
  return isNaN(n) ? null : n;
}

function mask(s) {
  if (!s) return "";
  const str = String(s);
  return str.length > 4 ? `${"•".repeat(str.length - 4)}${str.slice(-4)}` : str;
}

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}
