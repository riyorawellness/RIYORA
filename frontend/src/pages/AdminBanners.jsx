import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Plus, Trash2, Pencil, Image as ImageIcon } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

import { adminApi } from "@/services/admin";
import { formatApiError } from "@/lib/api";

const EMPTY = {
  title: "", image_url: "", cta_label: "", cta_link: "",
  placement: "home", priority: 0,
  schedule_start: "", schedule_end: "", is_active: true,
};

export default function AdminBanners() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // banner id or "new"
  const [draft, setDraft] = useState(EMPTY);
  const [uploading, setUploading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      setItems((await adminApi.banners()).items || []);
    } catch (e) {
      toast.error(formatApiError(e, "Load failed"));
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const openNew = () => { setDraft(EMPTY); setEditing("new"); };
  const openEdit = (b) => {
    setDraft({
      title: b.title || "", image_url: b.image_url || "",
      cta_label: b.cta_label || "", cta_link: b.cta_link || "",
      placement: b.placement || "home", priority: b.priority || 0,
      schedule_start: b.schedule_start || "", schedule_end: b.schedule_end || "",
      is_active: !!b.is_active,
    });
    setEditing(b.id);
  };
  const close = () => { setEditing(null); setDraft(EMPTY); };

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const r = await adminApi.upload(file);
      setDraft((d) => ({ ...d, image_url: r.url }));
      toast.success("Uploaded");
    } catch (e) {
      toast.error(formatApiError(e, "Upload failed"));
    } finally { setUploading(false); }
  };

  const save = async () => {
    const payload = {
      ...draft,
      priority: Number(draft.priority) || 0,
      schedule_start: draft.schedule_start || null,
      schedule_end: draft.schedule_end || null,
    };
    if (!payload.title || !payload.image_url) {
      toast.error("Title + image required");
      return;
    }
    try {
      if (editing === "new") await adminApi.createBanner(payload);
      else await adminApi.updateBanner(editing, payload);
      toast.success("Saved");
      close();
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Save failed"));
    }
  };

  const del = async (id) => {
    if (!confirm("Delete banner?")) return;
    try {
      await adminApi.deleteBanner(id);
      toast.success("Deleted");
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Delete failed"));
    }
  };

  return (
    <div className="px-6 py-6">
      <div className="flex items-baseline justify-between">
        <div>
          <p className="rw-eyebrow">Marketing</p>
          <h1 className="mt-1 rw-serif text-4xl">Banners</h1>
          <p className="text-sm text-muted-foreground">Home / offer / festival · schedule with start &amp; end</p>
        </div>
        <Button onClick={openNew} data-testid="banner-new">
          <Plus className="mr-1 h-4 w-4" /> New banner
        </Button>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3" data-testid="banners-list">
        {loading ? (
          <div className="col-span-full grid place-items-center py-14 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : items.length === 0 ? (
          <Card className="rw-card col-span-full grid place-items-center p-14 text-center text-sm text-muted-foreground">
            <ImageIcon className="mb-2 h-6 w-6" /> No banners yet.
          </Card>
        ) : items.map((b) => (
          <Card key={b.id} className="rw-card overflow-hidden">
            {b.image_url ? (
              <img src={b.image_url} alt={b.title} className="h-40 w-full object-cover" />
            ) : (
              <div className="h-40 bg-neutral-100" />
            )}
            <div className="p-4">
              <div className="mb-2 flex items-center gap-2">
                <Badge variant="outline" className="text-[10px]">{b.placement}</Badge>
                <Badge variant={b.is_active ? "default" : "secondary"} className="text-[10px]">
                  {b.is_active ? "active" : "inactive"}
                </Badge>
                <span className="ml-auto text-[10px] text-muted-foreground">priority {b.priority}</span>
              </div>
              <h3 className="rw-serif text-lg">{b.title}</h3>
              {(b.schedule_start || b.schedule_end) && (
                <p className="mt-1 text-[11px] text-muted-foreground">
                  {b.schedule_start?.slice(0, 10) || "—"} → {b.schedule_end?.slice(0, 10) || "—"}
                </p>
              )}
              <div className="mt-3 flex gap-2">
                <Button size="sm" variant="outline" onClick={() => openEdit(b)} data-testid={`banner-edit-${b.id}`}>
                  <Pencil className="mr-1 h-3 w-3" /> Edit
                </Button>
                <Button size="sm" variant="outline" onClick={() => del(b.id)} data-testid={`banner-delete-${b.id}`}>
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Dialog open={!!editing} onOpenChange={(o) => !o && close()}>
        <DialogContent className="max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editing === "new" ? "Create banner" : "Edit banner"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Title</Label>
              <Input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} data-testid="banner-title" />
            </div>
            <div>
              <Label>Image (upload or paste URL)</Label>
              <div className="flex items-center gap-2">
                <Input value={draft.image_url} onChange={(e) => setDraft({ ...draft, image_url: e.target.value })} placeholder="/api/uploads/..." data-testid="banner-image-url" />
                <label className="cursor-pointer rounded-md border px-3 py-2 text-xs">
                  {uploading ? "…" : "Upload"}
                  <input type="file" accept="image/*" hidden onChange={upload} data-testid="banner-upload" />
                </label>
              </div>
              {draft.image_url && (
                <img src={draft.image_url} alt="preview" className="mt-2 h-28 rounded-md object-cover" />
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>CTA label</Label>
                <Input value={draft.cta_label} onChange={(e) => setDraft({ ...draft, cta_label: e.target.value })} data-testid="banner-cta-label" />
              </div>
              <div>
                <Label>CTA link</Label>
                <Input value={draft.cta_link} onChange={(e) => setDraft({ ...draft, cta_link: e.target.value })} data-testid="banner-cta-link" />
              </div>
              <div>
                <Label>Placement</Label>
                <select
                  className="mt-1 h-10 w-full rounded-md border bg-white px-3 text-sm"
                  value={draft.placement}
                  onChange={(e) => setDraft({ ...draft, placement: e.target.value })}
                  data-testid="banner-placement"
                >
                  {["home", "programs", "checkout", "offer", "festival", "announcement"].map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
              </div>
              <div>
                <Label>Priority</Label>
                <Input type="number" value={draft.priority} onChange={(e) => setDraft({ ...draft, priority: e.target.value })} data-testid="banner-priority" />
              </div>
              <div>
                <Label>Schedule start (ISO)</Label>
                <Input value={draft.schedule_start} onChange={(e) => setDraft({ ...draft, schedule_start: e.target.value })} placeholder="2026-08-01T00:00:00Z" data-testid="banner-start" />
              </div>
              <div>
                <Label>Schedule end (ISO)</Label>
                <Input value={draft.schedule_end} onChange={(e) => setDraft({ ...draft, schedule_end: e.target.value })} placeholder="2026-08-31T23:59:59Z" data-testid="banner-end" />
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Switch checked={draft.is_active} onCheckedChange={(v) => setDraft({ ...draft, is_active: v })} data-testid="banner-active" />
              <span className="text-sm">{draft.is_active ? "Active" : "Inactive"}</span>
            </div>
            <Button onClick={save} className="w-full" data-testid="banner-save">Save banner</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
