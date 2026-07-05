import { useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, Loader2, Trash2 } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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

/**
 * Three-step confirmation before wiping app data.
 * Step 1: Awareness — lists exactly what will be kept vs wiped.
 * Step 2: Last-chance warning — plain "yes I'm sure".
 * Step 3: Type-to-confirm — must literally type "EMPTY APP DATA".
 */
export default function AdminDangerZone() {
  const [step, setStep] = useState(0); // 0 = closed, 1 | 2 | 3 = dialog stage
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
      // Close dialog first so the step-3 modal doesn't briefly overlap the
      // result card (Radix exit animation).
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
          <h2 className="rw-serif text-2xl text-red-900">Danger zone</h2>
          <p className="mt-1 text-sm text-red-900/80">
            Irreversible operations. Once wiped, data cannot be recovered
            unless you have a backup. Programs and admin credentials are
            preserved — everything user-generated is deleted.
          </p>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div className="rounded-lg border border-emerald-200 bg-white p-4">
              <div className="text-xs font-semibold uppercase tracking-widest text-emerald-800">
                Kept
              </div>
              <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-neutral-700">
                {KEPT.map((k) => (
                  <li key={k}>{k}</li>
                ))}
              </ul>
            </div>
            <div className="rounded-lg border border-red-200 bg-white p-4">
              <div className="text-xs font-semibold uppercase tracking-widest text-red-800">
                Wiped
              </div>
              <ul className="mt-2 list-disc space-y-1 pl-4 text-xs text-neutral-700">
                {WIPED.map((k) => (
                  <li key={k}>{k}</li>
                ))}
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

      {/* Step 1 — Awareness */}
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

      {/* Step 2 — Are you REALLY sure */}
      <Dialog open={step === 2} onOpenChange={(o) => !o && close()}>
        <DialogContent data-testid="danger-empty-step2">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-800">
              <AlertTriangle className="h-5 w-5" /> Are you really sure? — step 2 of 3
            </DialogTitle>
            <DialogDescription className="text-neutral-700">
              Once you proceed there is <b>no undo</b>. All test users,
              transactions, payments, notifications and audit history will be
              gone forever. If you need any of this, download a database
              backup first and try again.
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

      {/* Step 3 — Type-to-confirm */}
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
