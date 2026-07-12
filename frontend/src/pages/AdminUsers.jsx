import { useEffect, useState } from "react";
import { Loader2, Search, Download, Ban, RefreshCcw, Eye, KeyRound, CheckCircle2, Trash2, FileSpreadsheet, UserPlus, TestTube } from "lucide-react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { adminApi } from "@/services/admin";
import { formatApiError } from "@/lib/api";

export default function AdminUsers() {
  const nav = useNavigate();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [state, setState] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [pwDialog, setPwDialog] = useState(null);
  const [pwValue, setPwValue] = useState("");
  const [deleteDialog, setDeleteDialog] = useState(null); // { membership_id, full_name, mobile }
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [page, setPage] = useState(1);
  const [dummyOpen, setDummyOpen] = useState(false);
  const [dummyForm, setDummyForm] = useState({ full_name: "", mobile: "", password: "" });
  const [dummyBusy, setDummyBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const params = { page, page_size: 20 };
      if (q) params.q = q;
      if (state) params.state = state;
      if (activeFilter !== "") params.is_active = activeFilter === "true";
      const d = await adminApi.listUsers(params);
      setItems(d.items || []);
      setTotal(d.total);
    } catch (e) {
      toast.error(formatApiError(e, "Load failed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const openDetail = async (mid) => {
    try {
      const d = await adminApi.getUser(mid);
      setDetail(d);
    } catch (e) {
      toast.error(formatApiError(e, "Load failed"));
    }
  };

  const setStatus = async (mid, status) => {
    try {
      await adminApi.updateUserStatus(mid, { status });
      toast.success(`User ${status}`);
      load();
      if (detail?.user?.membership_id === mid) openDetail(mid);
    } catch (e) {
      toast.error(formatApiError(e, "Update failed"));
    }
  };

  const resetPassword = async () => {
    if (!pwDialog || pwValue.length < 8) {
      toast.error("Password must be at least 8 chars");
      return;
    }
    try {
      await adminApi.resetUserPassword(pwDialog, pwValue);
      toast.success("Password reset. User sessions revoked.");
      setPwDialog(null);
      setPwValue("");
    } catch (e) {
      toast.error(formatApiError(e, "Reset failed"));
    }
  };

  const exportCsv = async () => {
    try {
      const blob = await adminApi.exportUsersBlob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "riyora-users.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("CSV downloaded");
    } catch (e) {
      toast.error(formatApiError(e, "Export failed"));
    }
  };

  const softDelete = async () => {
    if (!deleteDialog) return;
    if (deleteConfirm.trim() !== "DELETE USER") {
      toast.error('Type "DELETE USER" exactly to confirm');
      return;
    }
    setDeleteBusy(true);
    try {
      await adminApi.softDeleteUser(deleteDialog.membership_id, deleteConfirm.trim());
      toast.success(`Deleted ${deleteDialog.full_name}. Mobile freed.`);
      setDeleteDialog(null);
      setDeleteConfirm("");
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Delete failed"));
    } finally {
      setDeleteBusy(false);
    }
  };

  const preview = null;  // deprecated — use dummy user instead

  const createDummy = async () => {
    if (!dummyForm.full_name || dummyForm.mobile.length < 10 || dummyForm.password.length < 6) {
      toast.error("Enter name, valid 10-digit mobile and 6+ char password");
      return;
    }
    setDummyBusy(true);
    try {
      const r = await adminApi.createDummyUser(dummyForm);
      toast.success(`Dummy user created: ${r.membership_id}`);
      setDummyOpen(false);
      setDummyForm({ full_name: "", mobile: "", password: "" });
      setPage(1);
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Create failed"));
    } finally {
      setDummyBusy(false);
    }
  };

  const export360 = async (u) => {
    try {
      toast.info(`Building 360 report for ${u.membership_id}…`);
      const blob = await adminApi.export360(u.membership_id);
      const href = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = href;
      a.download = `user-360-${u.membership_id}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(href);
      toast.success(`360 report downloaded`);
    } catch (e) {
      toast.error(formatApiError(e, "Export failed"));
    }
  };

  return (
    <div className="px-6 py-6">
      <p className="rw-eyebrow">Members</p>
      <h1 className="mt-1 rw-serif text-4xl">Users</h1>
      <p className="text-sm text-muted-foreground">
        {total} total · search, filter, suspend, reset password, export CSV
      </p>

      <div className="mt-3 flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-900" data-testid="admin-users-dummy-hint">
        <TestTube className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <strong>Tester (Dummy) users</strong> — create a special tester account that logs in like a real user but can hit <em>Mark as Paid</em> on any program instead of paying. Dummy purchases are excluded from revenue reports and never trigger referral commissions.
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search name / mobile / membership id / sponsor"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="pl-9"
            data-testid="admin-users-search"
          />
        </div>
        <Input placeholder="State" value={state} onChange={(e) => setState(e.target.value)} className="w-32" data-testid="admin-users-state" />
        <select
          className="h-10 rounded-md border bg-white px-3 text-sm"
          value={activeFilter}
          onChange={(e) => setActiveFilter(e.target.value)}
          data-testid="admin-users-active"
        >
          <option value="">All</option>
          <option value="true">Active</option>
          <option value="false">Inactive</option>
        </select>
        <Button onClick={() => { setPage(1); load(); }} data-testid="admin-users-apply">Apply</Button>
        <Button variant="outline" onClick={exportCsv} data-testid="admin-users-export">
          <Download className="mr-1 h-4 w-4" /> Export CSV
        </Button>
        <Button
          onClick={() => setDummyOpen(true)}
          className="bg-emerald-600 text-white hover:bg-emerald-700"
          data-testid="admin-users-create-dummy"
        >
          <UserPlus className="mr-1 h-4 w-4" /> New Dummy User
        </Button>
      </div>

      <Card className="rw-card mt-4 overflow-x-auto p-0">
        {loading ? (
          <div className="grid place-items-center py-14 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : (
          <Table data-testid="admin-users-table">
            <TableHeader>
              <TableRow>
                <TableHead>Member</TableHead>
                <TableHead>Location</TableHead>
                <TableHead>Sponsor</TableHead>
                <TableHead>Joined</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((u) => (
                <TableRow key={u.membership_id}>
                  <TableCell>
                    <div className="font-medium flex items-center gap-2">
                      {u.full_name}
                      {u.is_dummy && (
                        <Badge className="bg-emerald-100 text-emerald-800 hover:bg-emerald-100" data-testid={`admin-user-tester-badge-${u.membership_id}`}>
                          <TestTube className="mr-1 h-2.5 w-2.5" /> Tester
                        </Badge>
                      )}
                    </div>
                    <div className="font-mono text-xs text-muted-foreground">
                      {u.membership_id} · +91 {u.mobile}
                    </div>
                  </TableCell>
                  <TableCell className="text-xs">{u.city}, {u.state}</TableCell>
                  <TableCell className="font-mono text-xs">{u.sponsor_membership_id}</TableCell>
                  <TableCell className="text-xs">{formatDate(u.created_at)}</TableCell>
                  <TableCell>
                    <Badge variant={u.is_active ? "default" : "secondary"}>
                      {u.status || (u.is_active ? "active" : "inactive")}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button size="sm" variant="outline" onClick={() => openDetail(u.membership_id)} data-testid={`admin-user-view-${u.membership_id}`}>
                      <Eye className="h-3 w-3" />
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="ml-1 border-emerald-300 text-emerald-700 hover:bg-emerald-50"
                      onClick={() => export360(u)}
                      title="Download 360° Excel report"
                      data-testid={`admin-user-export-360-${u.membership_id}`}
                    >
                      <FileSpreadsheet className="h-3 w-3" />
                    </Button>
                    <Button size="sm" variant="outline" className="ml-1" onClick={() => setPwDialog(u.membership_id)} data-testid={`admin-user-pw-${u.membership_id}`}>
                      <KeyRound className="h-3 w-3" />
                    </Button>
                    {u.is_active ? (
                      <Button size="sm" variant="outline" className="ml-1" onClick={() => setStatus(u.membership_id, "suspended")} data-testid={`admin-user-suspend-${u.membership_id}`}>
                        <Ban className="h-3 w-3" />
                      </Button>
                    ) : (
                      <Button size="sm" variant="outline" className="ml-1" onClick={() => setStatus(u.membership_id, "active")} data-testid={`admin-user-activate-${u.membership_id}`}>
                        <CheckCircle2 className="h-3 w-3" />
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="outline"
                      className="ml-1 border-red-300 text-red-700 hover:bg-red-50"
                      onClick={() => { setDeleteConfirm(""); setDeleteDialog({ membership_id: u.membership_id, full_name: u.full_name, mobile: u.mobile }); }}
                      data-testid={`admin-user-delete-${u.membership_id}`}
                      title="Delete user"
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="py-14 text-center text-muted-foreground">
                    No users match filters.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </Card>

      <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
        <span>Page {page}</span>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
            Prev
          </Button>
          <Button size="sm" variant="outline" disabled={items.length < 20} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </div>
      </div>

      <Dialog open={!!detail} onOpenChange={(o) => !o && setDetail(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          {detail && <UserDetailTabs data={detail} />}
        </DialogContent>
      </Dialog>

      <Dialog open={dummyOpen} onOpenChange={(o) => !o && !dummyBusy && setDummyOpen(false)}>
        <DialogContent data-testid="admin-users-create-dummy-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-emerald-800">
              <TestTube className="h-5 w-5" /> Create Tester (Dummy) User
            </DialogTitle>
            <DialogDescription>
              Creates a real login account marked as a Tester. They see the full app just like a real user, but can hit <em>Mark as Paid</em> on any program instead of paying. Dummy purchases are excluded from all revenue reports and never trigger commissions.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Full name</Label>
              <Input
                value={dummyForm.full_name}
                onChange={(e) => setDummyForm({ ...dummyForm, full_name: e.target.value })}
                placeholder="e.g. QA Tester 1"
                data-testid="admin-dummy-name"
              />
            </div>
            <div>
              <Label>Mobile (10 digits)</Label>
              <Input
                value={dummyForm.mobile}
                onChange={(e) => setDummyForm({ ...dummyForm, mobile: e.target.value.replace(/\D/g, "").slice(0, 10) })}
                placeholder="9999XXXXXX"
                data-testid="admin-dummy-mobile"
              />
            </div>
            <div>
              <Label>Password (6+ chars)</Label>
              <Input
                type="text"
                value={dummyForm.password}
                onChange={(e) => setDummyForm({ ...dummyForm, password: e.target.value })}
                placeholder="Password the tester will use to log in"
                data-testid="admin-dummy-password"
              />
            </div>
            <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-[11px] text-emerald-900">
              <div>Tester will log in via <strong>/login</strong> using this mobile + password.</div>
              <div>Sponsor is <strong>RW000000</strong> (company root) so it never contaminates real referral trees.</div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDummyOpen(false)} disabled={dummyBusy}>Cancel</Button>
            <Button onClick={createDummy} disabled={dummyBusy} className="bg-emerald-600 text-white hover:bg-emerald-700" data-testid="admin-dummy-submit">
              {dummyBusy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <UserPlus className="mr-2 h-4 w-4" />}
              Create Tester
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!pwDialog} onOpenChange={(o) => !o && setPwDialog(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Reset password · {pwDialog}</DialogTitle></DialogHeader>
          <div>
            <Label>New password (min 8 chars)</Label>
            <Input type="text" value={pwValue} onChange={(e) => setPwValue(e.target.value)} data-testid="admin-user-pw-value" />
          </div>
          <p className="text-xs text-muted-foreground">
            User will be forced to sign in again on all devices.
          </p>
          <Button onClick={resetPassword} data-testid="admin-user-pw-confirm">Reset</Button>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleteDialog} onOpenChange={(o) => !o && setDeleteDialog(null)}>
        <DialogContent data-testid="admin-user-delete-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-800">
              <Trash2 className="h-5 w-5" /> Delete user
            </DialogTitle>
            <DialogDescription className="text-neutral-700">
              You are about to permanently delete
              {" "}
              <span className="font-semibold">{deleteDialog?.full_name}</span>
              {" "}
              (<span className="font-mono text-xs">{deleteDialog?.membership_id}</span>
              {" "}· +91 {deleteDialog?.mobile}).
              <br />
              The account is soft-deleted, all sessions are revoked, and the
              mobile number is freed for re-signup. The user&rsquo;s referral
              tree entry is preserved so downline sponsors are unaffected.
              <br />
              Type <span className="font-mono font-semibold">DELETE USER</span>{" "}
              to confirm.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="del-confirm">Confirmation phrase</Label>
            <Input
              id="del-confirm"
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              placeholder="DELETE USER"
              autoComplete="off"
              autoFocus
              data-testid="admin-user-delete-input"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDialog(null)} disabled={deleteBusy} data-testid="admin-user-delete-cancel">
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={softDelete}
              disabled={deleteBusy || deleteConfirm.trim() !== "DELETE USER"}
              data-testid="admin-user-delete-confirm"
            >
              {deleteBusy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
              Delete user
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function UserDetailTabs({ data }) {
  const { user, purchases, subscriptions, bank_details, downline, earnings, activity } = data;
  return (
    <>
      <DialogHeader>
        <DialogTitle>
          {user.full_name} · <span className="font-mono text-primary">{user.membership_id}</span>
        </DialogTitle>
      </DialogHeader>
      <Tabs defaultValue="profile" className="mt-2">
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="purchases">Purchases ({purchases.length})</TabsTrigger>
          <TabsTrigger value="subs">Subs ({subscriptions.length})</TabsTrigger>
          <TabsTrigger value="tree">Team ({(downline.L1 + downline.L2 + downline.L3)})</TabsTrigger>
          <TabsTrigger value="earnings">Earnings</TabsTrigger>
          <TabsTrigger value="activity">Activity</TabsTrigger>
          <TabsTrigger value="bank">Bank</TabsTrigger>
        </TabsList>
        <TabsContent value="profile">
          <Grid pairs={[
            ["Full name", user.full_name],
            ["Mobile", "+91 " + user.mobile],
            ["Membership ID", user.membership_id],
            ["Sponsor", `${user.sponsor_name || "—"} (${user.sponsor_membership_id})`],
            ["Location", `${user.city}, ${user.state}`],
            ["Status", user.status || (user.is_active ? "active" : "inactive")],
            ["Joined", formatDate(user.created_at)],
          ]} />
        </TabsContent>
        <TabsContent value="purchases">
          <MiniTable columns={["Program", "Invoice", "Total", "Status", "Expiry"]}
            rows={purchases.map((p) => [p.program_name, p.invoice_number, inr(p.total), p.status, formatDate(p.expiry_date)])} />
        </TabsContent>
        <TabsContent value="subs">
          <MiniTable columns={["Plan", "Started", "Next", "Status"]}
            rows={subscriptions.map((s) => [s.plan, formatDate(s.started_at), formatDate(s.next_charge_at), s.status])} />
        </TabsContent>
        <TabsContent value="tree">
          <Grid pairs={[
            ["Direct (L1)", downline.L1],
            ["Level 2", downline.L2],
            ["Level 3", downline.L3],
            ["Total downline", downline.L1 + downline.L2 + downline.L3],
          ]} />
        </TabsContent>
        <TabsContent value="earnings">
          <Grid pairs={[
            ["Lifetime", inr(earnings.lifetime)],
            ["Pending", inr(earnings.pending)],
            ["Approved (payable)", inr(earnings.approved)],
            ["Paid", inr(earnings.paid)],
            ["This month", inr(earnings.current_month)],
            ["Rejected", inr(earnings.rejected)],
          ]} />
        </TabsContent>
        <TabsContent value="activity">
          <Grid pairs={[
            ["Meter status", activity.status],
            ["Sessions completed", `${activity.completed || 0} / ${activity.required || 4}`],
            ["Cycle end", formatDate(activity.cycle_end)],
            ["Days left", activity.days_left ?? "—"],
          ]} />
        </TabsContent>
        <TabsContent value="bank">
          {bank_details ? (
            <Grid pairs={[
              ["Holder", bank_details.account_holder],
              ["Bank", bank_details.bank_name],
              ["Account", bank_details.account_number],
              ["IFSC", bank_details.ifsc_code],
              ["UPI", bank_details.upi_id],
            ]} />
          ) : (
            <p className="text-sm text-muted-foreground">No bank details on file.</p>
          )}
        </TabsContent>
      </Tabs>
    </>
  );
}

function Grid({ pairs }) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      {pairs.map(([k, v], i) => (
        <div key={i} className="rounded-lg bg-neutral-50 p-3">
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">{k}</div>
          <div className="mt-1 font-semibold">{v ?? "—"}</div>
        </div>
      ))}
    </div>
  );
}

function MiniTable({ columns, rows }) {
  if (rows.length === 0) return <p className="text-sm text-muted-foreground">No rows.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b">
            {columns.map((c) => <th key={c} className="py-2 text-left font-semibold">{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b">
              {r.map((v, j) => <td key={j} className="py-2 pr-2">{v ?? "—"}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function inr(v) {
  if (v === null || v === undefined) return "—";
  return `₹${Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}
function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "2-digit" });
  } catch { return iso; }
}
