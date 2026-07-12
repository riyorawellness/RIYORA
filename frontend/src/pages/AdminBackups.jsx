import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  Archive,
  Download,
  Loader2,
  RotateCcw,
  Trash2,
  Database,
  ShieldCheck,
} from "lucide-react";

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

export default function AdminBackups() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [restoreTarget, setRestoreTarget] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [password, setPassword] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await adminApi.listBackups();
      setItems(r.items || []);
    } catch (e) {
      toast.error(formatApiError(e, "Could not load backups"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    if (!password.trim()) {
      toast.error("Enter your admin password");
      return;
    }
    setBusy(true);
    try {
      const res = await adminApi.createBackup(password, reason.trim() || "manual");
      toast.success(`Backup created · ${res.backup.filename}`);
      setCreateOpen(false);
      setPassword("");
      setReason("");
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Backup failed"));
    } finally {
      setBusy(false);
    }
  };

  const restore = async () => {
    if (!password.trim()) {
      toast.error("Enter your admin password");
      return;
    }
    setBusy(true);
    try {
      await adminApi.restoreBackup(restoreTarget.filename, password);
      toast.success(`Restored ${restoreTarget.filename}`);
      setRestoreTarget(null);
      setPassword("");
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Restore failed"));
    } finally {
      setBusy(false);
    }
  };

  const del = async () => {
    if (!password.trim()) {
      toast.error("Enter your admin password");
      return;
    }
    setBusy(true);
    try {
      await adminApi.deleteBackup(deleteTarget.filename, password);
      toast.success("Backup deleted");
      setDeleteTarget(null);
      setPassword("");
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Delete failed"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="admin-backups-page">
      <Card className="rw-card p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="rounded-full bg-indigo-100 p-2">
              <Database className="h-5 w-5 text-indigo-700" />
            </div>
            <div>
              <h2 className="rw-serif text-2xl">Backups &amp; Restore</h2>
              <p className="mt-1 max-w-xl text-sm text-muted-foreground">
                Full MongoDB dumps. Auto-created before any destructive
                action from Danger Zone; also creatable on demand. Restore
                overwrites the current database — protect this action with
                your admin password.
              </p>
            </div>
          </div>
          <Button
            onClick={() => setCreateOpen(true)}
            data-testid="admin-backup-create-open"
          >
            <Archive className="mr-2 h-4 w-4" /> Create backup now
          </Button>
        </div>
      </Card>

      <Card className="rw-card p-0 overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : items.length === 0 ? (
          <p className="p-8 text-center text-sm text-muted-foreground">
            No backups yet. Click <b>Create backup now</b> above.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-neutral-50 text-left text-xs uppercase tracking-widest text-neutral-500">
              <tr>
                <th className="px-4 py-3">Filename</th>
                <th className="px-4 py-3">Size</th>
                <th className="px-4 py-3">Created</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((b) => (
                <tr
                  key={b.filename}
                  className="border-t"
                  data-testid={`admin-backup-row-${b.filename}`}
                >
                  <td className="px-4 py-3 font-mono text-[11px]">
                    {b.filename}
                  </td>
                  <td className="px-4 py-3">{b.size_human}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {new Date(b.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap justify-end gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setRestoreTarget(b);
                          setPassword("");
                        }}
                        data-testid={`admin-backup-restore-${b.filename}`}
                      >
                        <RotateCcw className="mr-1 h-3 w-3" /> Restore
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="border-red-200 text-red-700 hover:bg-red-50"
                        onClick={() => {
                          setDeleteTarget(b);
                          setPassword("");
                        }}
                        data-testid={`admin-backup-delete-${b.filename}`}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={(o) => !o && !busy && setCreateOpen(false)}>
        <DialogContent data-testid="admin-backup-create-dialog">
          <DialogHeader>
            <DialogTitle>Create backup</DialogTitle>
            <DialogDescription>
              Runs <code>mongodump</code> against the current database and
              saves a gzipped archive to <code>/app/backups</code>. Takes a
              few seconds for a small dataset.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Reason (optional)</Label>
              <Input
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="pre_launch, snapshot, etc."
                data-testid="admin-backup-reason"
              />
            </div>
            <div>
              <Label>Admin password</Label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                data-testid="admin-backup-password"
                autoComplete="current-password"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={busy}>
              Cancel
            </Button>
            <Button
              onClick={create}
              disabled={busy || !password.trim()}
              data-testid="admin-backup-create-confirm"
            >
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Archive className="mr-2 h-4 w-4" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Restore dialog */}
      <Dialog open={!!restoreTarget} onOpenChange={(o) => !o && !busy && setRestoreTarget(null)}>
        <DialogContent data-testid="admin-backup-restore-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-amber-800">
              <ShieldCheck className="h-5 w-5" /> Restore backup
            </DialogTitle>
            <DialogDescription>
              Overwrites the entire database with the contents of{" "}
              <span className="font-mono">{restoreTarget?.filename}</span>.
              This action is destructive.
            </DialogDescription>
          </DialogHeader>
          <div>
            <Label>Admin password</Label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              data-testid="admin-backup-restore-password"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRestoreTarget(null)} disabled={busy}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={restore}
              disabled={busy || !password.trim()}
              data-testid="admin-backup-restore-confirm"
            >
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RotateCcw className="mr-2 h-4 w-4" />}
              Restore now
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && !busy && setDeleteTarget(null)}>
        <DialogContent data-testid="admin-backup-delete-dialog">
          <DialogHeader>
            <DialogTitle>Delete backup</DialogTitle>
            <DialogDescription>
              Remove <span className="font-mono">{deleteTarget?.filename}</span>.
              This does NOT touch the database.
            </DialogDescription>
          </DialogHeader>
          <div>
            <Label>Admin password</Label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              data-testid="admin-backup-delete-password"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={busy}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={del}
              disabled={busy || !password.trim()}
              data-testid="admin-backup-delete-confirm"
            >
              {busy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Trash2 className="mr-2 h-4 w-4" />}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
