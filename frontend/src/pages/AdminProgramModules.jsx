import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { toast } from "sonner";
import {
  ArrowLeft,
  ChevronDown,
  ChevronUp,
  FileText,
  Loader2,
  Music,
  Pencil,
  Plus,
  Trash2,
  Video,
} from "lucide-react";

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

import { adminApi } from "@/services/admin";
import { formatApiError } from "@/lib/api";
import { MediaField } from "@/pages/AdminPrograms";

const emptyForm = (program_id, module_number = 1) => ({
  program_id,
  module_number,
  name: "",
  description: "",
  video_url: "",
  audio_url: "",
  pdf_url: "",
  assignment: "",
  order_index: 0,
  sequential_unlock: true,
  is_active: true,
});

export default function AdminProgramModules() {
  const { programId } = useParams();
  const [program, setProgram] = useState(null);
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const [dialog, setDialog] = useState(null); // { mode, module? }
  const [form, setForm] = useState(emptyForm(programId));
  const [deleteTarget, setDeleteTarget] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [p, m] = await Promise.all([
        adminApi.getProgram(programId),
        adminApi.listModules({ program_id: programId, page_size: 200 }),
      ]);
      setProgram(p);
      // Sort by module_number ascending for editor UX
      setModules(
        (m.items || []).sort((a, b) => (a.module_number || 0) - (b.module_number || 0)),
      );
    } catch (e) {
      toast.error(formatApiError(e, "Could not load modules"));
    } finally {
      setLoading(false);
    }
  }, [programId]);

  useEffect(() => {
    load();
  }, [load]);

  const setField = (k) => (v) => setForm((f) => ({ ...f, [k]: v }));

  const openCreate = () => {
    const nextNum = modules.length ? Math.max(...modules.map((m) => m.module_number || 0)) + 1 : 1;
    setForm(emptyForm(programId, nextNum));
    setDialog({ mode: "create" });
  };

  const openEdit = (mod) => {
    setForm({ ...emptyForm(programId), ...mod });
    setDialog({ mode: "edit", module: mod });
  };

  const submit = async () => {
    if (!form.name || form.name.length < 2) return toast.error("Name is required");
    if (form.module_number < 1) return toast.error("Module number must be ≥ 1");
    setBusy(true);
    try {
      const body = { ...form };
      body.module_number = Number(body.module_number);
      body.order_index = Number(body.order_index);
      if (dialog.mode === "create") {
        await adminApi.createModule(body);
        toast.success("Module created");
      } else {
        const { program_id, ...updateBody } = body;
        await adminApi.updateModule(dialog.module.id, updateBody);
        toast.success("Module updated");
      }
      setDialog(null);
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Save failed"));
    } finally {
      setBusy(false);
    }
  };

  const doDelete = async () => {
    if (!deleteTarget) return;
    try {
      await adminApi.deleteModule(deleteTarget.id);
      toast.success("Module deleted");
      setDeleteTarget(null);
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Delete failed"));
    }
  };

  const moveModule = async (mod, delta) => {
    // Swap module_number with the adjacent module.
    const idx = modules.findIndex((m) => m.id === mod.id);
    const target = modules[idx + delta];
    if (!target) return;
    try {
      // Two-step swap using a temp very-high number to avoid unique conflict.
      const tempNum = 100000 + Math.floor(Math.random() * 90000);
      await adminApi.updateModule(mod.id, { module_number: tempNum });
      await adminApi.updateModule(target.id, { module_number: mod.module_number });
      await adminApi.updateModule(mod.id, { module_number: target.module_number });
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Reorder failed"));
    }
  };

  return (
    <div className="rw-page space-y-5" data-testid="admin-modules-page">
      <div className="flex items-center gap-3">
        <Link to="/admin/programs">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-1 h-4 w-4" /> Programs
          </Button>
        </Link>
      </div>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="rw-serif text-3xl">
            {program?.name || "Loading…"}
          </h1>
          <p className="text-sm text-muted-foreground">
            Modules for this program. Users see them in module_number order.
          </p>
        </div>
        <Button onClick={openCreate} data-testid="admin-modules-new">
          <Plus className="mr-2 h-4 w-4" /> New module
        </Button>
      </div>

      {loading ? (
        <div className="grid place-items-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : modules.length === 0 ? (
        <Card className="rw-card grid place-items-center p-16 text-center">
          <FileText className="mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-lg font-medium">No modules yet</p>
          <p className="mb-4 text-sm text-muted-foreground">
            Add your first module — attach audio, video, PDF or an assignment.
          </p>
          <Button onClick={openCreate}>
            <Plus className="mr-2 h-4 w-4" /> New module
          </Button>
        </Card>
      ) : (
        <div className="grid gap-3">
          {modules.map((m, i) => (
            <Card
              key={m.id}
              className="rw-card flex flex-wrap items-center gap-4 p-4"
              data-testid={`admin-module-row-${m.id}`}
            >
              <div className="grid h-12 w-12 place-items-center rounded-lg bg-neutral-100 text-lg font-semibold">
                {m.module_number}
              </div>
              <div className="min-w-[160px] flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-base font-semibold">{m.name}</span>
                  {m.is_active ? (
                    <Badge className="bg-emerald-100 text-emerald-800">Live</Badge>
                  ) : (
                    <Badge variant="secondary">Hidden</Badge>
                  )}
                  {m.sequential_unlock && (
                    <Badge variant="outline">Sequential</Badge>
                  )}
                </div>
                <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
                  {m.video_url && <span className="inline-flex items-center gap-1"><Video className="h-3 w-3" /> Video</span>}
                  {m.audio_url && <span className="inline-flex items-center gap-1"><Music className="h-3 w-3" /> Audio</span>}
                  {m.pdf_url && <span className="inline-flex items-center gap-1"><FileText className="h-3 w-3" /> PDF</span>}
                  {m.assignment && <span>Assignment</span>}
                  {!(m.video_url || m.audio_url || m.pdf_url || m.assignment) && (
                    <span className="text-red-500">No media attached</span>
                  )}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={i === 0}
                  onClick={() => moveModule(m, -1)}
                  data-testid={`admin-module-up-${m.id}`}
                  title="Move up"
                >
                  <ChevronUp className="h-3.5 w-3.5" />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={i === modules.length - 1}
                  onClick={() => moveModule(m, +1)}
                  data-testid={`admin-module-down-${m.id}`}
                  title="Move down"
                >
                  <ChevronDown className="h-3.5 w-3.5" />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => openEdit(m)}
                  data-testid={`admin-module-edit-${m.id}`}
                >
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="border-red-300 text-red-700 hover:bg-red-50"
                  onClick={() => setDeleteTarget(m)}
                  data-testid={`admin-module-delete-${m.id}`}
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
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="admin-module-dialog">
          <DialogHeader>
            <DialogTitle>
              {dialog?.mode === "create" ? "New module" : "Edit module"}
            </DialogTitle>
            <DialogDescription>
              Attach audio, video and/or PDF. All media fields are optional — you can also add just an assignment.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <Label>Module number *</Label>
              <Input
                type="number"
                min={1}
                value={form.module_number}
                onChange={(e) => setField("module_number")(e.target.value)}
                data-testid="admin-module-field-number"
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
            <div className="md:col-span-2">
              <Label>Name *</Label>
              <Input
                value={form.name}
                onChange={(e) => setField("name")(e.target.value)}
                placeholder="e.g. Breathwork Foundations"
                data-testid="admin-module-field-name"
              />
            </div>
            <div className="md:col-span-2">
              <Label>Description</Label>
              <textarea
                className="w-full rounded-md border p-2 text-sm"
                rows={3}
                value={form.description}
                onChange={(e) => setField("description")(e.target.value)}
                maxLength={2000}
                data-testid="admin-module-field-description"
              />
            </div>

            <MediaField
              label="Video"
              hint="Upload a .mp4 or paste a hosted video URL"
              accept="video/*"
              value={form.video_url}
              onChange={setField("video_url")}
              testid="admin-module-field-video"
            />
            <MediaField
              label="Audio"
              hint="Upload .mp3 / .m4a or paste a hosted URL"
              accept="audio/*"
              value={form.audio_url}
              onChange={setField("audio_url")}
              testid="admin-module-field-audio"
            />
            <MediaField
              label="PDF / Worksheet"
              hint="Upload .pdf"
              accept="application/pdf"
              value={form.pdf_url}
              onChange={setField("pdf_url")}
              testid="admin-module-field-pdf"
            />

            <div className="md:col-span-2">
              <Label>Assignment (optional)</Label>
              <textarea
                className="w-full rounded-md border p-2 text-sm"
                rows={4}
                value={form.assignment}
                onChange={(e) => setField("assignment")(e.target.value)}
                placeholder="Instructions or reflection prompts for the learner…"
                maxLength={5000}
                data-testid="admin-module-field-assignment"
              />
            </div>

            <div className="flex items-center gap-3 rounded-lg border p-3">
              <Switch
                checked={form.is_active}
                onCheckedChange={setField("is_active")}
                data-testid="admin-module-field-active"
              />
              <div>
                <div className="text-sm font-medium">Visible</div>
                <div className="text-[11px] text-muted-foreground">Shown in the learner app</div>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-lg border p-3">
              <Switch
                checked={form.sequential_unlock}
                onCheckedChange={setField("sequential_unlock")}
              />
              <div>
                <div className="text-sm font-medium">Sequential unlock</div>
                <div className="text-[11px] text-muted-foreground">Must complete the previous module first</div>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialog(null)} disabled={busy}>Cancel</Button>
            <Button onClick={submit} disabled={busy} data-testid="admin-module-save">
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {dialog?.mode === "create" ? "Create module" : "Save changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent data-testid="admin-module-delete-dialog">
          <DialogHeader>
            <DialogTitle className="text-red-800">Delete module</DialogTitle>
            <DialogDescription>
              Delete <b>{deleteTarget?.name}</b>? This is a soft-delete — existing user progress is preserved.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={doDelete} data-testid="admin-module-delete-confirm">
              <Trash2 className="mr-2 h-4 w-4" /> Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
