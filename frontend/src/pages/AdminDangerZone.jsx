import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  AlertTriangle,
  Loader2,
  Trash2,
  UserX,
  Search,
} from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";

import { adminApi } from "@/services/admin";
import { formatApiError } from "@/lib/api";

export default function AdminDangerZone() {
  return (
    <div className="space-y-6" data-testid="danger-zone-wrapper">
      <EmptyAppDataCard />
      <DeleteUserCard />
    </div>
  );
}

// ────────────────────────── Empty app data ───────────────────────────────

const CONFIRM_PHRASE = "EMPTY APP DATA";
const KEPT = [
  "Admin login account",
  "Company / referral root (RW000000)",
  "Programs, modules and categories",
  "Banners, policies and CMS pages",
  "QR / manual-payment settings + system settings",
];
const WIPED = [
  "All user accounts (non-admin)",
  "Referral tree, memberships, profiles",
  "Purchases, progress, assessment results, certificates",
  "Commissions, payouts, bank details, subscriptions",
  "Notifications, OTP records, refresh sessions, audit logs",
  "Manual-payment requests + login lockouts",
];

function EmptyAppDataCard() {
  const [step, setStep] = useState(0);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastReport, setLastReport] = useState(null);

  const open = () => {
    setLastReport(null);
    setTyped("");
    setStep(1);
  };
  const close = () => {
    setStep(0);
    setTyped("");
  };

  const doWipe = async () => {
    if (typed.trim() !== CONFIRM_PHRASE) {
      toast.error(`You must type exactly "${CONFIRM_PHRASE}"`);
      return;
    }
    setBusy(true);
    try {
      const res = await adminApi.emptyAppData(typed.trim());
      setStep(0);
      setTyped("");
      setLastReport(res);
      toast.success("App data cleared successfully");
    } catch (e) {
      toast.error(formatApiError(e, "Wipe failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      className="rw-card border-red-200 bg-red-50/30 p-6"
      data-testid="danger-zone-card"
    >
      <div className="flex items-start gap-3">
        <div className="rounded-full bg-red-100 p-2">
          <AlertTriangle className="h-5 w-5 text-red-700" />
        </div>
        <div className="flex-1">
          <h2 className="rw-serif text-2xl text-red-900">Empty app data</h2>
          <p className="mt-1 text-sm text-red-900/80">
            Wipes every user account and all user-generated data. Programs,
            banners, policies and admin credentials are preserved. Once
            wiped, data cannot be recovered unless you have a database
            backup.
          </p>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-emerald-200 bg-white p-4">
              <div className="text-xs font-semibold uppercase tracking-widest text-emerald-800">
                Kept
              </div>
              <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-neutral-700">
                {KEPT.map((k) => <li key={k}>{k}</li>)}
              </ul>
            </div>
            <div className="rounded-lg border border-red-200 bg-white p-4">
              <div className="text-xs font-semibold uppercase tracking-widest text-red-800">
                Wiped
              </div>
              <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-neutral-700">
                {WIPED.map((k) => <li key={k}>{k}</li>)}
              </ul>
            </div>
          </div>

          <Button
            variant="destructive"
            className="mt-5"
            onClick={open}
            data-testid="danger-empty-open"
          >
            <Trash2 className="mr-2 h-4 w-4" /> Empty app data
          </Button>

          {lastReport && (
            <div
              className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-900"
              data-testid="danger-empty-result"
            >
              <div className="font-semibold">Last wipe report</div>
              <ul className="mt-2 grid gap-x-6 gap-y-1 sm:grid-cols-2">
                {Object.entries(lastReport.cleared || {}).map(([k, v]) => (
                  <li key={k} className="flex items-center justify-between gap-3">
                    <span className="capitalize">{k.replace(/_/g, " ")}</span>
                    <span className="font-mono font-semibold">{v}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      <Dialog open={step === 1} onOpenChange={(o) => !o && close()}>
        <DialogContent data-testid="danger-empty-step1">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-800">
              <AlertTriangle className="h-5 w-5" /> Confirm — step 1 of 3
            </DialogTitle>
            <DialogDescription className="text-neutral-700">
              You are about to permanently delete every user account and all
              user-generated data. Programs, banners, and admin credentials
              stay intact. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={close} data-testid="danger-empty-cancel-1">
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => setStep(2)}
              data-testid="danger-empty-next-1"
            >
              I understand, continue
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={step === 2} onOpenChange={(o) => !o && close()}>
        <DialogContent data-testid="danger-empty-step2">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-800">
              <AlertTriangle className="h-5 w-5" /> Are you really sure? — step 2 of 3
            </DialogTitle>
            <DialogDescription className="text-neutral-700">
              Once you proceed there is <b>no undo</b>. All test users,
              transactions, payments, notifications and audit history will
              be gone forever.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={close} data-testid="danger-empty-cancel-2">
              Take me back
            </Button>
            <Button
              variant="destructive"
              onClick={() => setStep(3)}
              data-testid="danger-empty-next-2"
            >
              Yes, I&rsquo;m sure
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={step === 3} onOpenChange={(o) => !o && close()}>
        <DialogContent data-testid="danger-empty-step3">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-800">
              <AlertTriangle className="h-5 w-5" /> Final confirmation — step 3 of 3
            </DialogTitle>
            <DialogDescription className="text-neutral-700">
              Type <span className="font-mono font-semibold">EMPTY APP DATA</span>{" "}
              exactly (case sensitive) to enable the wipe button.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label htmlFor="empty-confirm">Confirmation phrase</Label>
            <Input
              id="empty-confirm"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder="EMPTY APP DATA"
              autoComplete="off"
              autoFocus
              data-testid="danger-empty-input"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={close} disabled={busy} data-testid="danger-empty-cancel-3">
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={doWipe}
              disabled={busy || typed.trim() !== CONFIRM_PHRASE}
              data-testid="danger-empty-confirm"
            >
              {busy ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="mr-2 h-4 w-4" />
              )}
              Empty app data now
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

// ────────────────────────── Delete individual user ──────────────────────

const USER_CONFIRM = "DELETE USER";

const SCOPES = [
  { key: "wipe_profile", label: "Profile", desc: "Basic profile row (email/dob/photo/etc.)", danger: false, defaultOn: true },
  { key: "wipe_notifications", label: "Notifications", desc: "In-app notifications sent to this user", danger: false, defaultOn: true },
  { key: "wipe_purchases", label: "Purchases & transactions", desc: "Program purchases, progress, payment requests, orders", danger: false, defaultOn: false },
  { key: "wipe_certificates", label: "Certificates", desc: "Certificates issued to this user", danger: false, defaultOn: false },
  { key: "wipe_assessments", label: "Assessment results", desc: "Historical assessment scores", danger: false, defaultOn: false },
  { key: "wipe_bank_details", label: "Bank details", desc: "Payout bank / UPI details on file", danger: false, defaultOn: false },
  { key: "wipe_commissions", label: "Commissions earned", desc: "Historical commission ledger for this user (impacts payout audit trail)", danger: true, defaultOn: false },
  { key: "wipe_referral_tree", label: "Referral-tree entry", desc: "Removes their node from the referral tree. Their DOWNLINE loses lineage — commissions for future sponsors of that downline will re-route to the closest surviving upline. Leave unchecked to preserve sponsor history.", danger: true, defaultOn: false },
];

const defaultOptions = () =>
  Object.fromEntries(SCOPES.map((s) => [s.key, s.defaultOn]));

function DeleteUserCard() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState(null); // user obj
  const [opts, setOpts] = useState(defaultOptions);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [lastReport, setLastReport] = useState(null);

  const runSearch = async () => {
    const query = q.trim();
    if (!query) {
      toast.error("Type a name, mobile or membership id to search");
      return;
    }
    setSearching(true);
    try {
      const r = await adminApi.listUsers({ q: query, page: 1, page_size: 10 });
      setResults(r.items || []);
      if ((r.items || []).length === 0) toast.info("No users match");
    } catch (e) {
      toast.error(formatApiError(e, "Search failed"));
    } finally {
      setSearching(false);
    }
  };

  useEffect(() => {
    // Debounced auto-search on typing
    if (!q.trim()) {
      setResults([]);
      return undefined;
    }
    const id = setTimeout(runSearch, 400);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  const pick = (u) => {
    setSelected(u);
    setOpts(defaultOptions());
    setTyped("");
  };

  const submit = async () => {
    if (!selected) return;
    if (typed.trim() !== USER_CONFIRM) {
      toast.error(`Type "${USER_CONFIRM}" exactly to confirm`);
      return;
    }
    setBusy(true);
    try {
      const res = await adminApi.softDeleteUser(
        selected.membership_id,
        typed.trim(),
        opts,
      );
      setLastReport({ user: selected, wiped: res.wiped || {} });
      toast.success(`Deleted ${selected.full_name}. Mobile freed.`);
      setSelected(null);
      setTyped("");
      setQ("");
      setResults([]);
    } catch (e) {
      toast.error(formatApiError(e, "Delete failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card
      className="rw-card border-amber-200 bg-amber-50/30 p-6"
      data-testid="danger-delete-user-card"
    >
      <div className="flex items-start gap-3">
        <div className="rounded-full bg-amber-100 p-2">
          <UserX className="h-5 w-5 text-amber-800" />
        </div>
        <div className="flex-1">
          <h2 className="rw-serif text-2xl text-amber-900">Delete individual user</h2>
          <p className="mt-1 text-sm text-amber-900/80">
            Soft-deletes the account, revokes all sessions, and frees the
            mobile number so it can register again. You choose exactly
            which additional data to purge.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <div className="relative flex-1 min-w-[220px]">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search by name, mobile or RW membership id"
                className="pl-9"
                data-testid="danger-user-search"
              />
            </div>
            <Button
              onClick={runSearch}
              disabled={searching}
              variant="outline"
              data-testid="danger-user-search-btn"
            >
              {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : "Search"}
            </Button>
          </div>

          {results.length > 0 && (
            <div className="mt-3 divide-y rounded-lg border bg-white" data-testid="danger-user-results">
              {results.map((u) => (
                <button
                  key={u.membership_id}
                  onClick={() => pick(u)}
                  className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-neutral-50"
                  data-testid={`danger-user-pick-${u.membership_id}`}
                >
                  <div>
                    <div className="text-sm font-medium">{u.full_name}</div>
                    <div className="font-mono text-[11px] text-muted-foreground">
                      {u.membership_id} · +91 {u.mobile}
                    </div>
                  </div>
                  <Badge variant={u.is_active ? "default" : "secondary"}>
                    {u.status || (u.is_active ? "active" : "inactive")}
                  </Badge>
                </button>
              ))}
            </div>
          )}

          {lastReport && !selected && (
            <div
              className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-xs text-emerald-900"
              data-testid="danger-delete-result"
            >
              <div className="font-semibold">
                Deleted: {lastReport.user.full_name} ({lastReport.user.membership_id})
              </div>
              {Object.keys(lastReport.wiped).length > 0 ? (
                <ul className="mt-2 grid gap-x-6 gap-y-1 sm:grid-cols-2">
                  {Object.entries(lastReport.wiped).map(([k, v]) => (
                    <li key={k} className="flex items-center justify-between gap-3">
                      <span className="capitalize">{k.replace(/_/g, " ")}</span>
                      <span className="font-mono font-semibold">{v}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1">Account soft-deleted. No extra data purged.</p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Delete-user configuration dialog */}
      <Dialog open={!!selected} onOpenChange={(o) => !o && !busy && setSelected(null)}>
        <DialogContent className="max-w-lg" data-testid="danger-delete-user-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-800">
              <UserX className="h-5 w-5" /> Delete user
            </DialogTitle>
            <DialogDescription>
              {selected ? (
                <>
                  Removing{" "}
                  <span className="font-semibold">{selected.full_name}</span>
                  {" "}(<span className="font-mono text-xs">{selected.membership_id}</span>
                  {" "}· +91 {selected.mobile}).
                </>
              ) : (
                "Select a user to configure the delete scope."
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div className="text-xs font-semibold uppercase tracking-widest text-neutral-600">
              What to also delete
            </div>
            {SCOPES.map((s) => (
              <label
                key={s.key}
                className={`flex items-start gap-3 rounded-lg border p-3 text-sm ${
                  s.danger ? "border-red-200 bg-red-50/40" : "border-neutral-200 bg-white"
                }`}
              >
                <Checkbox
                  checked={!!opts[s.key]}
                  onCheckedChange={(v) => setOpts((o) => ({ ...o, [s.key]: !!v }))}
                  data-testid={`danger-scope-${s.key}`}
                  className="mt-0.5"
                />
                <div>
                  <div className={`font-medium ${s.danger ? "text-red-900" : ""}`}>
                    {s.label}
                    {s.danger && (
                      <span className="ml-2 rounded-full bg-red-200 px-2 py-0.5 text-[10px] font-semibold uppercase text-red-800">
                        risky
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-neutral-600">{s.desc}</div>
                </div>
              </label>
            ))}

            <div>
              <Label htmlFor="del-user-typed">
                Type <span className="font-mono font-semibold">DELETE USER</span> to confirm
              </Label>
              <Input
                id="del-user-typed"
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                placeholder="DELETE USER"
                autoComplete="off"
                data-testid="danger-user-confirm-input"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setSelected(null)} disabled={busy} data-testid="danger-user-cancel">
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={submit}
              disabled={busy || typed.trim() !== USER_CONFIRM}
              data-testid="danger-user-confirm"
            >
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
              Delete user
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
