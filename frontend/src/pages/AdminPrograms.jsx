import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import {
  BookOpen,
  CheckCircle2,
  Copy,
  Layers,
  Loader2,
  Pencil,
  Plus,
  Search,
  Sparkles,
  Star,
  Trash2,
  XCircle,
} from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { adminApi } from "@/services/admin";
import { formatApiError } from "@/lib/api";

const emptyForm = () => ({
  name: "",
  slug: "",
  short_description: "",
  description: "",
  thumbnail_url: "",
  banner_url: "",
  price: 0,
  discount: 0,
  gst_percent: 18,
  validity_days: 365,
  category_id: "",
  order_index: 0,
  is_active: true,
  is_subscription: false,
  is_featured: false,
  payment_mode: "",
  payment_type: "one_time",
  level: 0,
  access_mode: "sequential",
});

const slugify = (s) =>
  (s || "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80);

export default function AdminPrograms() {
  const [items, setItems] = useState([]);
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);

  const [dialog, setDialog] = useState(null); // { mode: 'create'|'edit', program? }
  const [form, setForm] = useState(emptyForm());
  const [deleteTarget, setDeleteTarget] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [p, c] = await Promise.all([
        adminApi.listPrograms({ page_size: 100 }),
        adminApi.listCategories({ page_size: 100 }),
      ]);
      setItems(p.items || []);
      setCategories(c.items || []);
    } catch (e) {
      toast.error(formatApiError(e, "Could not load programs"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    if (!term) return items;
    return items.filter(
      (p) =>
        (p.name || "").toLowerCase().includes(term) ||
        (p.slug || "").toLowerCase().includes(term),
    );
  }, [items, q]);

  const openCreate = () => {
    setForm(emptyForm());
    setDialog({ mode: "create" });
  };

  const openEdit = (p) => {
    // Legacy programs may still have payment_type='subscription' — collapse
    // them to one_time so admins can edit without seeing a dead option.
    let paymentType =
      p.payment_type ||
      (Number(p.price) === 0 ? "free" : "one_time");
    if (paymentType === "subscription") paymentType = "one_time";
    setForm({
      ...emptyForm(),
      ...p,
      payment_type: paymentType,
      category_id: p.category_id || "",
      level: p.level ?? 0,
    });
    setDialog({ mode: "edit", program: p });
  };

  const setField = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    // Validation before hitting server
    if (!form.name || form.name.length < 2) return toast.error("Name is required (min 2 chars)");
    if (!/^[a-z0-9-]{2,150}$/.test(form.slug)) return toast.error("Slug must be lowercase, digits, and hyphens only");
    if (form.validity_days <= 0) return toast.error("Validity days must be > 0");
    if (form.payment_type === "one_time" && form.price < 0) return toast.error("Price cannot be negative");

    setBusy(true);
    try {
      const body = { ...form };
      // Clean fields the server rejects when null/empty
      if (!body.category_id) delete body.category_id;
      if (!body.payment_mode) delete body.payment_mode;
      if (body.payment_type === "free") {
        body.price = 0;
        body.discount = 0;
      }
      // Legacy subscription fields — never send them.
      delete body.subscription_frequency;
      body.is_subscription = false;
      body.price = Number(body.price);
      body.discount = Number(body.discount);
      body.gst_percent = Number(body.gst_percent);
      body.validity_days = Number(body.validity_days);
      body.order_index = Number(body.order_index);
      body.level = Number(body.level) || 0;

      if (dialog.mode === "create") {
        await adminApi.createProgram(body);
        toast.success("Program created");
      } else {
        // On update, don't send slug (backend doesn't accept slug changes)
        const { slug, ...updateBody } = body;
        await adminApi.updateProgram(dialog.program.id, updateBody);
        toast.success("Program updated");
      }
      setDialog(null);
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Save failed"));
    } finally {
      setBusy(false);
    }
  };

  const toggleActive = async (p) => {
    try {
      if (p.is_active) await adminApi.deactivateProgram(p.id);
      else await adminApi.activateProgram(p.id);
      toast.success(p.is_active ? "Deactivated" : "Activated");
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Toggle failed"));
    }
  };

  const toggleFeatured = async (p) => {
    try {
      await adminApi.updateProgram(p.id, { is_featured: !p.is_featured });
      toast.success(p.is_featured ? "Unfeatured" : "Featured on Home");
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Toggle failed"));
    }
  };

  const doDelete = async () => {
    if (!deleteTarget) return;
    try {
      await adminApi.deleteProgram(deleteTarget.id);
      toast.success("Program deleted");
      setDeleteTarget(null);
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Delete failed"));
    }
  };

  return (
    <div className="rw-page space-y-5" data-testid="admin-programs-page">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="rw-serif text-3xl">Programs</h1>
          <p className="text-sm text-muted-foreground">
            Create, edit and publish learning programs. Each program contains
            one or more modules (audio · video · PDF).
          </p>
        </div>
        <Button onClick={openCreate} data-testid="admin-programs-new">
          <Plus className="mr-2 h-4 w-4" /> New program
        </Button>
      </div>

      <Card className="rw-card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search name or slug"
              className="pl-9"
              data-testid="admin-programs-search"
            />
          </div>
          <div className="text-xs text-muted-foreground">
            {filtered.length} / {items.length} programs
          </div>
        </div>
      </Card>

      {loading ? (
        <div className="grid place-items-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : filtered.length === 0 ? (
        <Card className="rw-card grid place-items-center p-16 text-center">
          <Sparkles className="mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-lg font-medium">No programs yet</p>
          <p className="mb-4 text-sm text-muted-foreground">
            Click <b>New program</b> to add your first program.
          </p>
          <Button onClick={openCreate}>
            <Plus className="mr-2 h-4 w-4" /> New program
          </Button>
        </Card>
      ) : (
        <div className="grid gap-3">
          {filtered.map((p) => (
            <Card
              key={p.id}
              className="rw-card flex flex-wrap items-center gap-4 p-4"
              data-testid={`admin-program-row-${p.id}`}
            >
              {p.thumbnail_url ? (
                <img
                  src={p.thumbnail_url}
                  alt=""
                  className="h-16 w-24 rounded-lg object-cover"
                />
              ) : (
                <div className="grid h-16 w-24 place-items-center rounded-lg bg-neutral-100">
                  <BookOpen className="h-6 w-6 text-neutral-400" />
                </div>
              )}
              <div className="min-w-[180px] flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-base font-semibold">{p.name}</span>
                  {p.is_active ? (
                    <Badge className="bg-emerald-100 text-emerald-800">Live</Badge>
                  ) : (
                    <Badge variant="secondary">Draft</Badge>
                  )}
                  {p.is_featured && (
                    <Badge className="bg-amber-100 text-amber-800">Featured</Badge>
                  )}
                  {typeof p.level === "number" && p.level > 0 && (
                    <Badge variant="outline">L{p.level}</Badge>
                  )}
                </div>
                <div className="mt-0.5 flex flex-wrap items-center gap-x-4 gap-y-0.5 text-xs text-muted-foreground">
                  <span className="font-mono">{p.slug}</span>
                  <span>₹{p.price} · {p.validity_days}d · GST {p.gst_percent}%</span>
                  <span>Order {p.order_index}</span>
                </div>
                {p.short_description && (
                  <p className="mt-1 line-clamp-1 text-sm">{p.short_description}</p>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Link to={`/admin/programs/${p.id}/modules`}>
                  <Button size="sm" variant="outline" data-testid={`admin-program-modules-${p.id}`}>
                    <Layers className="mr-1 h-3.5 w-3.5" /> Modules
                  </Button>
                </Link>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => toggleFeatured(p)}
                  title={p.is_featured ? "Remove from Home" : "Feature on Home"}
                  data-testid={`admin-program-featured-${p.id}`}
                  className={p.is_featured ? "border-amber-400 bg-amber-50 text-amber-800 hover:bg-amber-100" : ""}
                >
                  <Star
                    className={`h-3.5 w-3.5 ${p.is_featured ? "fill-amber-500 text-amber-500" : ""}`}
                  />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => toggleActive(p)}
                  data-testid={`admin-program-toggle-${p.id}`}
                >
                  {p.is_active ? (
                    <XCircle className="h-3.5 w-3.5" />
                  ) : (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  )}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => openEdit(p)}
                  data-testid={`admin-program-edit-${p.id}`}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-red-300 text-red-700 hover:bg-red-50"
                  onClick={() => setDeleteTarget(p)}
                  data-testid={`admin-program-delete-${p.id}`}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create / edit dialog */}
      <Dialog open={!!dialog} onOpenChange={(o) => !o && !busy && setDialog(null)}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="admin-program-dialog">
          <DialogHeader>
            <DialogTitle>
              {dialog?.mode === "create" ? "New program" : "Edit program"}
            </DialogTitle>
            <DialogDescription>
              Fields marked with * are required.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="md:col-span-2">
              <Label>Name *</Label>
              <Input
                value={form.name}
                onChange={(e) => {
                  const name = e.target.value;
                  setForm((f) => ({
                    ...f,
                    name,
                    slug: dialog?.mode === "create" ? slugify(name) : f.slug,
                  }));
                }}
                placeholder="e.g. Foundation Wellness Program"
                data-testid="admin-program-field-name"
              />
            </div>

            <div>
              <Label>Slug * <span className="text-xs text-muted-foreground">(URL-safe)</span></Label>
              <Input
                value={form.slug}
                onChange={(e) => setField("slug")(slugify(e.target.value))}
                placeholder="foundation-wellness"
                disabled={dialog?.mode === "edit"}
                data-testid="admin-program-field-slug"
              />
              {dialog?.mode === "edit" && (
                <p className="mt-1 text-[11px] text-muted-foreground">Slug can&apos;t be changed after creation</p>
              )}
            </div>

            <div>
              <Label>Category</Label>
              <Select
                value={form.category_id || "__none__"}
                onValueChange={(v) => setField("category_id")(v === "__none__" ? "" : v)}
              >
                <SelectTrigger data-testid="admin-program-field-category">
                  <SelectValue placeholder="Uncategorised" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Uncategorised</SelectItem>
                  {categories.map((c) => (
                    <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="md:col-span-2">
              <Label>Short description</Label>
              <Input
                value={form.short_description}
                onChange={(e) => setField("short_description")(e.target.value)}
                placeholder="One-liner shown on the program card (max 280 chars)"
                maxLength={280}
                data-testid="admin-program-field-short"
              />
            </div>

            <div className="md:col-span-2">
              <Label>Full description</Label>
              <textarea
                className="w-full rounded-md border p-2 text-sm"
                rows={5}
                value={form.description}
                onChange={(e) => setField("description")(e.target.value)}
                placeholder="Detailed program overview (max 5000 chars)"
                maxLength={5000}
                data-testid="admin-program-field-description"
              />
            </div>

            <MediaField
              label="Thumbnail image"
              hint="Square-ish, shown on program cards"
              accept="image/*"
              value={form.thumbnail_url}
              onChange={setField("thumbnail_url")}
              testid="admin-program-field-thumbnail"
            />
            <MediaField
              label="Banner image"
              hint="Wide 16:9, shown on the program detail page"
              accept="image/*"
              value={form.banner_url}
              onChange={setField("banner_url")}
              testid="admin-program-field-banner"
            />

            <div className="col-span-2 rounded-lg border border-[hsl(var(--rw-royal))]/20 bg-[hsl(var(--rw-sky-soft))]/40 p-3">
              <Label className="mb-2 block text-xs font-semibold uppercase tracking-widest text-[hsl(var(--rw-royal))]">Payment type</Label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { value: "free", label: "Free", hint: "No payment — user joins instantly." },
                  { value: "one_time", label: "One-Time", hint: "Razorpay checkout · access for validity_days." },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setField("payment_type")(opt.value)}
                    className={`rounded-lg border p-3 text-left text-xs transition ${
                      form.payment_type === opt.value
                        ? "border-[hsl(var(--rw-royal))] bg-white shadow-sm"
                        : "border-neutral-200 bg-white/60 hover:border-neutral-300"
                    }`}
                    data-testid={`admin-program-payment-type-${opt.value}`}
                  >
                    <div className="text-sm font-semibold">{opt.label}</div>
                    <div className="mt-0.5 text-[10px] text-muted-foreground">{opt.hint}</div>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <Label>{form.payment_type === "free" ? "Price (₹) — locked to 0" : "Price (₹) *"}</Label>
              <Input
                type="number"
                min={0}
                value={form.price}
                onChange={(e) => setField("price")(e.target.value)}
                disabled={form.payment_type === "free"}
                data-testid="admin-program-field-price"
              />
            </div>
            <div>
              <Label>Discount (₹)</Label>
              <Input
                type="number"
                min={0}
                value={form.discount}
                onChange={(e) => setField("discount")(e.target.value)}
              />
            </div>
            <div>
              <Label>GST %</Label>
              <Input
                type="number"
                min={0}
                max={100}
                value={form.gst_percent}
                onChange={(e) => setField("gst_percent")(e.target.value)}
              />
            </div>
            <div>
              <Label>Validity days *</Label>
              <Input
                type="number"
                min={1}
                value={form.validity_days}
                onChange={(e) => setField("validity_days")(e.target.value)}
                data-testid="admin-program-field-validity"
              />
            </div>
            <div>
              <Label>Level (0 = intro)</Label>
              <Input
                type="number"
                min={0}
                max={10}
                value={form.level}
                onChange={(e) => setField("level")(e.target.value)}
              />
            </div>
            <div>
              <Label>Order index</Label>
              <Input
                type="number"
                value={form.order_index}
                onChange={(e) => setField("order_index")(e.target.value)}
              />
            </div>

            <div>
              <Label>Access mode</Label>
              <Select
                value={form.access_mode}
                onValueChange={setField("access_mode")}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sequential">Sequential (level-locked)</SelectItem>
                  <SelectItem value="free">Free (open access)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="col-span-2">
              <Label>Payment mode <span className="text-[10px] text-muted-foreground">(overrides global setting)</span></Label>
              <Select
                value={form.payment_mode || "__default__"}
                onValueChange={(v) => setField("payment_mode")(v === "__default__" ? "" : v)}
              >
                <SelectTrigger data-testid="admin-program-field-payment-mode">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__default__">Use global setting</SelectItem>
                  <SelectItem value="manual_qr">QR (manual verification)</SelectItem>
                  <SelectItem value="razorpay">Razorpay (online)</SelectItem>
                  <SelectItem value="both">Both — user chooses</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center gap-3 rounded-lg border p-3">
              <Switch
                checked={form.is_active}
                onCheckedChange={setField("is_active")}
                data-testid="admin-program-field-active"
              />
              <div>
                <div className="text-sm font-medium">Published</div>
                <div className="text-[11px] text-muted-foreground">Visible in user app</div>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-lg border p-3">
              <Switch
                checked={form.is_featured}
                onCheckedChange={setField("is_featured")}
                data-testid="admin-program-field-featured"
              />
              <div>
                <div className="text-sm font-medium">Featured on Home</div>
                <div className="text-[11px] text-muted-foreground">
                  Show this program on the user Home page
                </div>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(null)} disabled={busy}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={busy} data-testid="admin-program-save">
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {dialog?.mode === "create" ? "Create program" : "Save changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent data-testid="admin-program-delete-dialog">
          <DialogHeader>
            <DialogTitle className="text-red-800">Delete program</DialogTitle>
            <DialogDescription>
              Delete <b>{deleteTarget?.name}</b>? This soft-deletes the program
              — users who already purchased it retain access via their
              existing purchases.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={doDelete} data-testid="admin-program-delete-confirm">
              <Trash2 className="mr-2 h-4 w-4" /> Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/**
 * MediaField — inline uploader for a URL field.
 * - Paste a URL directly, or
 * - Click Upload → picks a file → posts to /admin/uploads → sets URL.
 */
function MediaField({ label, hint, accept, value, onChange, testid }) {
  const [uploading, setUploading] = useState(false);

  const onFile = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const res = await adminApi.upload(f);
      const url = res?.url?.startsWith("/")
        ? `${window.location.origin.replace(/\/$/, "")}${res.url}`
        : res?.url;
      // The upload endpoint returns "/api/uploads/<id>"; on the frontend we
      // need it via the backend, so store the absolute URL.
      const finalUrl = res?.url?.startsWith("/api/")
        ? `${process.env.REACT_APP_BACKEND_URL}${res.url}`
        : url;
      onChange(finalUrl);
      toast.success("Uploaded");
    } catch (err) {
      toast.error(formatApiError(err, "Upload failed"));
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  return (
    <div>
      <Label>{label}</Label>
      <div className="flex items-center gap-2">
        <Input
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Paste URL or upload…"
          data-testid={testid}
        />
        <label className="inline-flex cursor-pointer">
          <input
            type="file"
            accept={accept}
            className="hidden"
            onChange={onFile}
            data-testid={`${testid}-file`}
          />
          <span className="rw-btn-pill inline-flex items-center gap-1 border bg-white px-3 py-1.5 text-xs">
            {uploading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Plus className="h-3.5 w-3.5" />
            )}
            Upload
          </span>
        </label>
        {value && (
          <button
            type="button"
            onClick={() => navigator.clipboard.writeText(value).then(() => toast.success("URL copied"))}
            className="rounded-md border p-1.5 text-muted-foreground hover:text-foreground"
            title="Copy URL"
          >
            <Copy className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      {hint && <p className="mt-1 text-[11px] text-muted-foreground">{hint}</p>}
      {value && accept?.startsWith("image") && (
        <img src={value} alt="" className="mt-2 h-24 rounded-lg border object-cover" />
      )}
    </div>
  );
}

export { MediaField };
