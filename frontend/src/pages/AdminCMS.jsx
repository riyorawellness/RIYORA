import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Save, FileText } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";

import { adminApi } from "@/services/admin";
import { formatApiError } from "@/lib/api";

export default function AdminCMS() {
  const [pages, setPages] = useState([]);
  const [selected, setSelected] = useState(null);
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const d = await adminApi.cmsList();
      setPages(d.items || []);
      if (!selected && d.items?.length) setSelected(d.items[0].slug);
    } catch (e) {
      toast.error(formatApiError(e, "Load failed"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  useEffect(() => {
    if (!selected) return;
    (async () => {
      try {
        const p = await adminApi.cmsGet(selected);
        setDraft({
          title: p.title || "",
          body: p.body || "",
          meta_description: p.meta_description || "",
          is_published: p.is_published ?? true,
        });
      } catch (e) {
        toast.error(formatApiError(e, "Load failed"));
      }
    })();
  }, [selected]);

  const save = async () => {
    if (!selected || !draft) return;
    setSaving(true);
    try {
      await adminApi.cmsUpsert(selected, draft);
      toast.success("Saved");
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Save failed"));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div className="grid place-items-center py-24 text-muted-foreground"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  }

  return (
    <div className="px-6 py-6">
      <p className="rw-eyebrow">Content</p>
      <h1 className="mt-1 rw-serif text-4xl">CMS pages</h1>
      <p className="text-sm text-muted-foreground">
        Editable public pages · About / Privacy / Terms / Refund / FAQ / Contact / Support
      </p>

      <div className="mt-6 grid gap-6 md:grid-cols-[220px_1fr]">
        <Card className="rw-card p-2">
          <nav className="flex flex-col gap-1" data-testid="cms-page-nav">
            {pages.map((p) => (
              <button
                key={p.slug}
                onClick={() => setSelected(p.slug)}
                className={`flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm ${
                  selected === p.slug
                    ? "bg-primary/10 text-primary font-semibold"
                    : "hover:bg-neutral-50"
                }`}
                data-testid={`cms-tab-${p.slug}`}
              >
                <FileText className="h-3.5 w-3.5" />
                <span className="flex-1 truncate">{p.title}</span>
                {p.is_published ? (
                  <span className="text-[10px] text-emerald-600">●</span>
                ) : (
                  <span className="text-[10px] text-neutral-400">○</span>
                )}
              </button>
            ))}
          </nav>
        </Card>

        <Card className="rw-card p-6">
          {!draft ? (
            <div className="grid place-items-center py-14 text-muted-foreground">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <Label>Title</Label>
                <Input value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} data-testid="cms-title" />
              </div>
              <div>
                <Label>Meta description (SEO, optional)</Label>
                <Input value={draft.meta_description} onChange={(e) => setDraft({ ...draft, meta_description: e.target.value })} data-testid="cms-meta" />
              </div>
              <div>
                <Label>Body (HTML or plain text · 200K max)</Label>
                <Textarea
                  className="min-h-[360px] font-mono text-sm"
                  value={draft.body}
                  onChange={(e) => setDraft({ ...draft, body: e.target.value })}
                  data-testid="cms-body"
                />
              </div>
              <div className="flex items-center gap-3">
                <Switch
                  checked={draft.is_published}
                  onCheckedChange={(v) => setDraft({ ...draft, is_published: v })}
                  data-testid="cms-published"
                />
                <span className="text-sm">{draft.is_published ? "Published" : "Draft"}</span>
              </div>
              <Button onClick={save} disabled={saving} data-testid="cms-save">
                {saving ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Save className="mr-1 h-4 w-4" />}
                Save {selected}
              </Button>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
