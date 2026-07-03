import { useState } from "react";
import { toast } from "sonner";
import { Landmark, Loader2, ShieldCheck } from "lucide-react";
import TopBar from "@/components/TopBar";
import api, { formatApiError } from "@/lib/api";
import { TID } from "@/constants/testIds";

export default function BankDetails() {
  const [form, setForm] = useState({
    account_holder: "",
    bank_name: "",
    account_number: "",
    ifsc: "",
    upi_id: "",
  });
  const [loading, setLoading] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const save = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.put("/bank-details/me", { ...form, ifsc: form.ifsc.toUpperCase() });
      toast.success("Bank details saved");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="px-4 pt-3">
      <TopBar title="Bank details" subtitle="For future payouts" />

      <div className="rw-card mt-4 p-4">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-full bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal-deep))]">
            <Landmark className="h-4 w-4" />
          </div>
          <div className="text-xs text-muted-foreground">
            Encrypted at rest. Payouts and withdrawals will unlock in a later phase.
          </div>
        </div>
      </div>

      <form className="mt-4 space-y-4" onSubmit={save}>
        <F label="Account holder">
          <input className="rw-input" data-testid={TID.bankAccountHolder} value={form.account_holder} onChange={set("account_holder")} />
        </F>
        <F label="Bank name">
          <input className="rw-input" data-testid={TID.bankName} value={form.bank_name} onChange={set("bank_name")} />
        </F>
        <F label="Account number">
          <input className="rw-input" data-testid={TID.bankAccountNumber} inputMode="numeric" value={form.account_number} onChange={set("account_number")} />
        </F>
        <F label="IFSC">
          <input className="rw-input" data-testid={TID.bankIfsc} value={form.ifsc} onChange={set("ifsc")} placeholder="e.g. HDFC0001234" />
        </F>
        <F label="UPI ID (optional)">
          <input className="rw-input" data-testid={TID.bankUpi} value={form.upi_id} onChange={set("upi_id")} placeholder="you@upi" />
        </F>

        <button type="submit" className="rw-btn-pill rw-btn-primary w-full" disabled={loading} data-testid={TID.bankSave}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
          Save
        </button>
      </form>
    </div>
  );
}
function F({ label, children }) {
  return (
    <div>
      <label className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">{label}</label>
      <div className="mt-1">{children}</div>
    </div>
  );
}
