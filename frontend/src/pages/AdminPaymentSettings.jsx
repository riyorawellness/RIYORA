import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Save, Trash2, Upload, Loader2, ImageIcon, ShieldCheck, RefreshCw,
} from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { manualPaymentsApi, resolveUploadUrl } from "@/services/manualPayments";
import { formatApiError } from "@/lib/api";

const MODES = [
  { key: "manual_qr", label: "Manual QR Payment", desc: "Users pay via UPI QR and submit UTR. Admin verifies manually.", enabled: true },
  { key: "razorpay",  label: "Razorpay",           desc: "Automated online payments.", enabled: false },
  { key: "both",       label: "Both (Manual + Razorpay)", desc: "Offer users a choice.", enabled: false },
];

export default function AdminPaymentSettings() {
  const [data, setData] = useState({ payment_mode: "manual_qr", active_qr: null });
  const [form, setForm] = useState(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const d = await manualPaymentsApi.adminGetSettings();
      setData(d);
      setForm({ ...EMPTY, ...(d.active_qr || {}) });
    } catch (e) {
      toast.error(formatApiError(e, "Could not load settings"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const setMode = async (payment_mode) => {
    try {
      await manualPaymentsApi.adminSetMode(payment_mode);
      setData((d) => ({ ...d, payment_mode }));
      toast.success(`Payment mode: ${payment_mode.replace("_", " ")}`);
    } catch (e) {
      toast.error(formatApiError(e, "Could not update mode"));
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      const d = await manualPaymentsApi.adminPutSettings({
        company_name: form.company_name || null,
        account_holder_name: form.account_holder_name || null,
        bank_name: form.bank_name || null,
        upi_id: form.upi_id || null,
        account_number: form.account_number || null,
        ifsc: form.ifsc || null,
        payment_instructions: form.payment_instructions || null,
        is_active: true,
      });
      setData(d);
      setForm({ ...EMPTY, ...(d.active_qr || {}) });
      toast.success("Settings saved");
    } catch (e) {
      toast.error(formatApiError(e, "Save failed"));
    } finally {
      setSaving(false);
    }
  };

  const uploadQR = async (file) => {
    if (!file) return;
    setUploading(true);
    try {
      await manualPaymentsApi.adminUploadQR(file);
      toast.success("QR uploaded");
      await load();
    } catch (e) {
      toast.error(formatApiError(e, "Upload failed"));
    } finally {
      setUploading(false);
    }
  };

  const deleteQR = async () => {
    if (!window.confirm("Delete the active QR image?")) return;
    try {
      await manualPaymentsApi.adminDeleteQR();
      toast.success("QR deleted");
      await load();
    } catch (e) {
      toast.error(formatApiError(e, "Delete failed"));
    }
  };

  return (
    <div className="px-6 py-6" data-testid="admin-payment-settings-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="rw-eyebrow">Payments</p>
          <h1 className="mt-1 rw-serif text-4xl">Payment Settings</h1>
          <p className="text-sm text-muted-foreground">
            Configure the active payment provider and the company QR code for manual UPI payments.
          </p>
        </div>
        <Button variant="ghost" onClick={load} disabled={loading} data-testid="settings-refresh-btn">
          <RefreshCw className={`mr-1 h-4 w-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </Button>
      </div>

      {/* Payment mode */}
      <Card className="mt-6 p-5" data-testid="payment-mode-card">
        <div className="flex items-center justify-between">
          <div>
            <p className="rw-eyebrow">Active provider</p>
            <h2 className="rw-serif text-2xl">Payment mode</h2>
            <p className="text-xs text-muted-foreground">
              Choose which payment method is offered to users. Only Manual QR is enabled at this stage;
              additional providers can be enabled here once configured.
            </p>
          </div>
          <div className="w-64">
            <Select value={data.payment_mode} onValueChange={setMode}>
              <SelectTrigger data-testid="payment-mode-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                {MODES.map((m) => (
                  <SelectItem key={m.key} value={m.key} disabled={!m.enabled}>
                    {m.label} {!m.enabled && " (coming soon)"}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <div className="mt-4 grid gap-2 md:grid-cols-3">
          {MODES.map((m) => (
            <div
              key={m.key}
              className={`rounded-lg border p-3 text-xs ${data.payment_mode === m.key ? "border-primary bg-primary/5" : "border-neutral-200"}`}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold">{m.label}</span>
                {data.payment_mode === m.key && <Badge>Active</Badge>}
                {!m.enabled && <Badge variant="secondary">Soon</Badge>}
              </div>
              <p className="mt-1 text-muted-foreground">{m.desc}</p>
            </div>
          ))}
        </div>
      </Card>

      {/* Company QR & bank details */}
      <Card className="mt-6 p-5" data-testid="qr-settings-card">
        <p className="rw-eyebrow">Company QR</p>
        <h2 className="rw-serif text-2xl">Manual UPI QR &amp; bank details</h2>

        <div className="mt-4 grid gap-6 md:grid-cols-2">
          {/* QR image */}
          <div>
            <div className="relative aspect-square w-full max-w-sm overflow-hidden rounded-2xl border-2 border-dashed border-neutral-300 bg-neutral-50">
              {data.active_qr?.qr_image_url ? (
                <img
                  src={resolveUploadUrl(data.active_qr.qr_image_url)}
                  alt="QR"
                  className="h-full w-full object-contain p-4"
                  data-testid="qr-preview-img"
                />
              ) : (
                <div className="grid h-full w-full place-items-center text-muted-foreground">
                  <div className="text-center">
                    <ImageIcon className="mx-auto h-6 w-6" />
                    <p className="mt-1 text-xs">No QR uploaded yet</p>
                  </div>
                </div>
              )}
            </div>
            <div className="mt-3 flex gap-2">
              <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-white hover:opacity-90">
                {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                {data.active_qr?.qr_image_url ? "Replace QR" : "Upload QR"}
                <input
                  type="file"
                  accept="image/*"
                  className="sr-only"
                  onChange={(e) => uploadQR(e.target.files?.[0])}
                  data-testid="qr-upload-input"
                />
              </label>
              {data.active_qr?.qr_image_url && (
                <Button variant="destructive" size="sm" onClick={deleteQR} data-testid="qr-delete-btn">
                  <Trash2 className="mr-1 h-3.5 w-3.5" /> Delete
                </Button>
              )}
            </div>
            <p className="mt-2 text-[10px] text-muted-foreground">
              PNG or JPG, max 5 MB. This QR is shown to every user during checkout.
            </p>
          </div>

          {/* Bank / UPI fields */}
          <div className="space-y-3">
            <Field label="Company name">
              <Input value={form.company_name || ""} onChange={(e) => setForm({ ...form, company_name: e.target.value })} data-testid="qr-company-input" />
            </Field>
            <Field label="Account holder name">
              <Input value={form.account_holder_name || ""} onChange={(e) => setForm({ ...form, account_holder_name: e.target.value })} data-testid="qr-holder-input" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Bank name">
                <Input value={form.bank_name || ""} onChange={(e) => setForm({ ...form, bank_name: e.target.value })} data-testid="qr-bank-input" />
              </Field>
              <Field label="UPI ID">
                <Input value={form.upi_id || ""} onChange={(e) => setForm({ ...form, upi_id: e.target.value })} placeholder="name@bank" data-testid="qr-upi-input" />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Account number (optional)">
                <Input value={form.account_number || ""} onChange={(e) => setForm({ ...form, account_number: e.target.value })} data-testid="qr-account-input" />
              </Field>
              <Field label="IFSC (optional)">
                <Input value={form.ifsc || ""} onChange={(e) => setForm({ ...form, ifsc: e.target.value.toUpperCase() })} data-testid="qr-ifsc-input" />
              </Field>
            </div>
            <Field label="Payment instructions">
              <Textarea rows={4} value={form.payment_instructions || ""} onChange={(e) => setForm({ ...form, payment_instructions: e.target.value })} placeholder="e.g. Please use any UPI app to scan the QR. Send the UTR / transaction reference for verification." data-testid="qr-instructions-input" />
            </Field>
            <Button className="w-full" onClick={save} disabled={saving} data-testid="qr-save-btn">
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
              Save settings
            </Button>
          </div>
        </div>
      </Card>

      <p className="mt-6 text-center text-[11px] text-muted-foreground">
        <ShieldCheck className="mr-1 inline h-3 w-3" />
        These settings apply immediately across the app. Only one QR is active at a time.
      </p>
    </div>
  );
}

const EMPTY = {
  company_name: "", account_holder_name: "", bank_name: "",
  upi_id: "", account_number: "", ifsc: "", payment_instructions: "",
};

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
