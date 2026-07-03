import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, IndianRupee, TrendingUp, Undo2, Settings2, Search, LogOut } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import Logo from "@/components/Logo";
import { useAuth } from "@/context/AuthContext";
import { paymentsApi } from "@/services/payments";
import { formatApiError } from "@/lib/api";

export default function AdminPayments() {
  const nav = useNavigate();
  const { admin, logout } = useAuth();
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [refundOpen, setRefundOpen] = useState(false);
  const [refundTarget, setRefundTarget] = useState(null);
  const [reason, setReason] = useState("");
  const [settings, setSettings] = useState(null);
  const [showSettings, setShowSettings] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [list, sum, st] = await Promise.all([
        paymentsApi.adminList({ q: q || undefined, status: statusFilter || undefined, page_size: 100 }),
        paymentsApi.adminSummary(),
        paymentsApi.adminGetSettings(),
      ]);
      setItems(list.items || []);
      setSummary(sum);
      setSettings(st);
    } catch (e) {
      toast.error(formatApiError(e, "Failed to load transactions"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const doRefund = async () => {
    if (!refundTarget) return;
    try {
      await paymentsApi.adminRefund(refundTarget.id, reason);
      toast.success("Refund recorded");
      setRefundOpen(false);
      setReason("");
      setRefundTarget(null);
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Refund failed"));
    }
  };

  const saveSettings = async () => {
    try {
      const updated = await paymentsApi.adminUpdateSettings({
        default_gst_percent: Number(settings.default_gst_percent) || 18,
        default_validity_days: Number(settings.default_validity_days) || 365,
        company_gst_number: settings.company_gst_number || null,
        invoice_prefix: settings.invoice_prefix || "INV",
      });
      setSettings(updated);
      toast.success("Settings saved");
      setShowSettings(false);
    } catch (e) {
      toast.error(formatApiError(e, "Save failed"));
    }
  };

  const doLogout = async () => {
    await logout();
    nav("/", { replace: true });
  };

  return (
    <div className="min-h-screen rw-hero-radial rw-grain">
      <header className="rw-container flex items-center justify-between py-6">
        <div className="flex items-center gap-3">
          <Logo size="sm" />
          <Badge variant="secondary" className="ml-1">Admin</Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => nav("/admin/dashboard")} data-testid="admin-nav-dashboard">
            Dashboard
          </Button>
          <Button variant="secondary" onClick={doLogout} data-testid="admin-payments-logout">
            <LogOut className="mr-1 h-4 w-4" /> Sign out
          </Button>
        </div>
      </header>

      <main className="rw-container pb-16">
        <p className="rw-eyebrow">Finance</p>
        <h1 className="mt-2 rw-serif text-5xl text-foreground">
          Payments · <span className="text-primary">{admin?.name}</span>
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Transactions, refunds and GST settings.
        </p>

        <section className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4" data-testid="admin-payment-stats">
          <Stat icon={IndianRupee} label="Net revenue" value={inr(summary?.total_revenue)} />
          <Stat icon={TrendingUp} label="Total transactions" value={summary?.total_transactions ?? "—"} />
          <Stat icon={Undo2} label="Refunds" value={summary?.buckets?.refunded?.count ?? 0} />
          <Stat icon={IndianRupee} label="Active revenue" value={inr(summary?.buckets?.active?.revenue)} />
        </section>

        <section className="mt-8 flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[240px]">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search invoice / membership / order id"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              className="pl-9"
              data-testid="admin-payments-search"
            />
          </div>
          <select
            className="h-10 rounded-md border bg-white px-3 text-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            data-testid="admin-payments-status-filter"
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="expired">Expired</option>
            <option value="refunded">Refunded</option>
            <option value="cancelled">Cancelled</option>
          </select>
          <Button onClick={load} data-testid="admin-payments-apply">Apply</Button>
          <Dialog open={showSettings} onOpenChange={setShowSettings}>
            <DialogTrigger asChild>
              <Button variant="outline" data-testid="admin-payment-settings-btn">
                <Settings2 className="mr-1 h-4 w-4" /> Settings
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Payment settings</DialogTitle>
              </DialogHeader>
              {settings && (
                <div className="grid gap-3">
                  <div>
                    <Label>Default GST %</Label>
                    <Input
                      type="number"
                      value={settings.default_gst_percent ?? ""}
                      onChange={(e) => setSettings({ ...settings, default_gst_percent: e.target.value })}
                      data-testid="settings-default-gst"
                    />
                  </div>
                  <div>
                    <Label>Default validity (days)</Label>
                    <Input
                      type="number"
                      value={settings.default_validity_days ?? ""}
                      onChange={(e) => setSettings({ ...settings, default_validity_days: e.target.value })}
                      data-testid="settings-default-validity"
                    />
                  </div>
                  <div>
                    <Label>Company GST number</Label>
                    <Input
                      value={settings.company_gst_number || ""}
                      onChange={(e) => setSettings({ ...settings, company_gst_number: e.target.value })}
                      data-testid="settings-company-gstin"
                      placeholder="e.g., 29ABCDE1234F1Z5"
                    />
                  </div>
                  <div>
                    <Label>Invoice prefix</Label>
                    <Input
                      value={settings.invoice_prefix || ""}
                      onChange={(e) => setSettings({ ...settings, invoice_prefix: e.target.value })}
                      data-testid="settings-invoice-prefix"
                    />
                  </div>
                  <Button onClick={saveSettings} data-testid="settings-save-btn">Save</Button>
                </div>
              )}
            </DialogContent>
          </Dialog>
        </section>

        <section className="mt-6">
          <Card className="rw-card overflow-x-auto p-0">
            {loading ? (
              <div className="grid place-items-center py-14 text-muted-foreground">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : (
              <Table data-testid="admin-payments-table">
                <TableHeader>
                  <TableRow>
                    <TableHead>Invoice</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Member</TableHead>
                    <TableHead>Program</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((it) => (
                    <TableRow key={it.id}>
                      <TableCell className="font-mono text-xs">{it.invoice_number}</TableCell>
                      <TableCell>{formatDate(it.purchase_date)}</TableCell>
                      <TableCell>
                        <div className="font-medium">{it.user?.full_name || "—"}</div>
                        <div className="font-mono text-xs text-muted-foreground">
                          {it.user?.membership_id}
                        </div>
                      </TableCell>
                      <TableCell>{it.program?.name || "—"}</TableCell>
                      <TableCell>{inr(it.total)}</TableCell>
                      <TableCell>
                        <Badge variant={it.status === "active" ? "default" : "secondary"}>
                          {it.status}
                        </Badge>
                        {it.is_mock && (
                          <Badge className="ml-1" variant="outline">
                            mock
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {it.status !== "refunded" && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setRefundTarget(it);
                              setRefundOpen(true);
                            }}
                            data-testid={`admin-refund-btn-${it.id}`}
                          >
                            Refund
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7} className="py-14 text-center text-muted-foreground">
                        No transactions yet.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </Card>
        </section>
      </main>

      <Dialog open={refundOpen} onOpenChange={setRefundOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Refund transaction</DialogTitle>
          </DialogHeader>
          {refundTarget && (
            <div className="space-y-3 text-sm">
              <div>
                <span className="text-muted-foreground">Invoice:</span>{" "}
                <span className="font-mono">{refundTarget.invoice_number}</span>
              </div>
              <div>
                <span className="text-muted-foreground">Amount:</span>{" "}
                {inr(refundTarget.total)}
              </div>
              <div>
                <Label>Reason (optional)</Label>
                <Input
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Cancellation / duplicate / other"
                  data-testid="refund-reason-input"
                />
              </div>
              <Button
                onClick={doRefund}
                className="w-full"
                data-testid="refund-confirm-btn"
              >
                Confirm refund
              </Button>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Stat({ icon: Icon, label, value }) {
  return (
    <Card className="rw-card">
      <div className="flex items-center justify-between">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <span className="text-[11px] uppercase tracking-[0.2em] text-muted-foreground">
          {label}
        </span>
      </div>
      <div className="mt-4 rw-serif text-4xl text-foreground">{value}</div>
    </Card>
  );
}

function inr(v) {
  if (v === null || v === undefined) return "—";
  return `₹${Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}
