import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import {
  Copy,
  File as FileIcon,
  FileText,
  Film,
  Image as ImageIcon,
  Loader2,
  Music,
  Search,
  Trash2,
  Upload,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
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

const iconFor = (ct = "") => {
  if (ct.startsWith("image/")) return ImageIcon;
  if (ct.startsWith("video/")) return Film;
  if (ct.startsWith("audio/")) return Music;
  if (ct.includes("pdf")) return FileText;
  return FileIcon;
};

const kindFor = (ct = "") => {
  if (ct.startsWith("image/")) return "Image";
  if (ct.startsWith("video/")) return "Video";
  if (ct.startsWith("audio/")) return "Audio";
  if (ct.includes("pdf")) return "PDF";
  return "File";
};

const bytesFmt = (n = 0) => {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
};

const absoluteUrl = (url = "") =>
  url.startsWith("/api/") ? `${process.env.REACT_APP_BACKEND_URL}${url}` : url;

export default function AdminMedia() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [q, setQ] = useState("");
  const [kind, setKind] = useState("all"); // all | image | video | audio | pdf
  const [deleteTarget, setDeleteTarget] = useState(null);
  const fileInput = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await adminApi.listUploads();
      setItems(r.items || []);
    } catch (e) {
      toast.error(formatApiError(e, "Could not load uploads"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    return items.filter((f) => {
      const k = kindFor(f.content_type || "").toLowerCase();
      if (kind !== "all" && k !== kind) return false;
      if (!term) return true;
      return (
        (f.original_name || "").toLowerCase().includes(term) ||
        (f.content_type || "").toLowerCase().includes(term)
      );
    });
  }, [items, q, kind]);

  const onFiles = async (files) => {
    if (!files?.length) return;
    setUploading(true);
    let ok = 0;
    let fail = 0;
    for (const f of files) {
      try {
        await adminApi.upload(f);
        ok += 1;
      } catch (e) {
        fail += 1;
        toast.error(formatApiError(e, `Upload failed: ${f.name}`));
      }
    }
    setUploading(false);
    if (ok) toast.success(`Uploaded ${ok} file${ok > 1 ? "s" : ""}${fail ? `, ${fail} failed` : ""}`);
    load();
  };

  const doDelete = async () => {
    if (!deleteTarget) return;
    try {
      await adminApi.deleteUpload(deleteTarget.id);
      toast.success("Deleted");
      setDeleteTarget(null);
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Delete failed"));
    }
  };

  const copyUrl = (f) => {
    const abs = absoluteUrl(f.url);
    navigator.clipboard.writeText(abs).then(
      () => toast.success("URL copied to clipboard"),
      () => toast.error("Copy failed — copy manually"),
    );
  };

  const totalBytes = items.reduce((s, f) => s + (f.size_bytes || 0), 0);

  return (
    <div className="rw-page space-y-5" data-testid="admin-media-page">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="rw-serif text-3xl">Media library</h1>
          <p className="text-sm text-muted-foreground">
            Every image, PDF, audio and video uploaded to RIYORA. Paste the copied
            URL into a program or module to use it.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            ref={fileInput}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => onFiles(Array.from(e.target.files || []))}
            data-testid="admin-media-file-input"
          />
          <Button
            onClick={() => fileInput.current?.click()}
            disabled={uploading}
            data-testid="admin-media-upload"
          >
            {uploading ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Upload className="mr-2 h-4 w-4" />
            )}
            Upload files
          </Button>
        </div>
      </div>

      <Card className="rw-card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative flex-1 min-w-[220px]">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search file name or type"
              className="pl-9"
              data-testid="admin-media-search"
            />
          </div>
          <div className="flex flex-wrap gap-1">
            {["all", "image", "video", "audio", "pdf"].map((k) => (
              <button
                key={k}
                onClick={() => setKind(k)}
                className={`rounded-full border px-3 py-1 text-xs capitalize ${
                  kind === k ? "border-primary bg-primary/10 text-primary" : ""
                }`}
                data-testid={`admin-media-kind-${k}`}
              >
                {k}
              </button>
            ))}
          </div>
          <div className="text-xs text-muted-foreground">
            {filtered.length} / {items.length} files · {bytesFmt(totalBytes)} total
          </div>
        </div>
      </Card>

      {loading ? (
        <div className="grid place-items-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : filtered.length === 0 ? (
        <Card
          className="rw-card grid cursor-pointer place-items-center border-2 border-dashed p-16 text-center transition-colors hover:bg-neutral-50"
          onClick={() => fileInput.current?.click()}
        >
          <Upload className="mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-lg font-medium">
            {items.length === 0 ? "No files uploaded yet" : "No matches"}
          </p>
          <p className="text-sm text-muted-foreground">
            {items.length === 0
              ? "Click to upload your first file — images, PDFs, audio and video are all supported."
              : "Try clearing the search or filter."}
          </p>
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {filtered.map((f) => {
            const abs = absoluteUrl(f.url);
            const ct = f.content_type || "";
            const Icon = iconFor(ct);
            const isImg = ct.startsWith("image/");
            return (
              <Card
                key={f.id}
                className="rw-card overflow-hidden"
                data-testid={`admin-media-item-${f.id}`}
              >
                <div className="grid h-40 place-items-center bg-neutral-100">
                  {isImg ? (
                    <img
                      src={abs}
                      alt={f.original_name}
                      className="h-full w-full object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <Icon className="h-12 w-12 text-neutral-400" />
                  )}
                </div>
                <div className="space-y-1 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="line-clamp-1 text-sm font-medium" title={f.original_name}>
                      {f.original_name}
                    </div>
                    <Badge variant="outline" className="shrink-0 text-[10px]">
                      {kindFor(ct)}
                    </Badge>
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    {bytesFmt(f.size_bytes)} · {new Date(f.created_at).toLocaleDateString()}
                  </div>
                  <div className="flex gap-2 pt-1">
                    <Button
                      size="sm"
                      variant="outline"
                      className="flex-1"
                      onClick={() => copyUrl(f)}
                      data-testid={`admin-media-copy-${f.id}`}
                    >
                      <Copy className="mr-1 h-3 w-3" /> Copy URL
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="border-red-300 text-red-700 hover:bg-red-50"
                      onClick={() => setDeleteTarget(f)}
                      data-testid={`admin-media-delete-${f.id}`}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent data-testid="admin-media-delete-dialog">
          <DialogHeader>
            <DialogTitle className="text-red-800">Delete file</DialogTitle>
            <DialogDescription>
              Delete <b>{deleteTarget?.original_name}</b>? Any program or module
              still referencing this URL will show a broken link.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={doDelete} data-testid="admin-media-delete-confirm">
              <Trash2 className="mr-2 h-4 w-4" /> Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
