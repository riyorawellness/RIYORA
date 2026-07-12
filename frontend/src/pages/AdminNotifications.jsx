import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Send, RefreshCcw } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import { adminApi } from "@/services/admin";
import { formatApiError } from "@/lib/api";

const CATEGORIES = ["announcement", "offer", "renewal", "program", "activity", "system"];

export default function AdminNotifications() {
  const [form, setForm] = useState({
    title: "", body: "", category: "announcement", is_broadcast: true,
    target_membership_ids: "", cta_link: "",
  });
  const [items, setItems] = useState([]);
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      setItems((await adminApi.notificationHistory()).items || []);
    } catch (e) {
      toast.error(formatApiError(e, "Load failed"));
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const send = async () => {
    if (!form.title || !form.body) {
      toast.error("Title and body required");
      return;
    }
    setSending(true);
    try {
      const payload = {
        title: form.title,
        body: form.body,
        category: form.category,
        is_broadcast: form.is_broadcast,
        target_membership_ids: form.is_broadcast
          ? null
          : form.target_membership_ids
              .split(/[,\s]+/)
              .map((x) => x.trim())
              .filter(Boolean),
        cta_link: form.cta_link || null,
      };
      const res = await adminApi.sendNotification(payload);
      toast.success(`Delivered to ${res.delivered_count} member(s)`);
      setForm({ ...form, title: "", body: "" });
      load();
    } catch (e) {
      toast.error(formatApiError(e, "Send failed"));
    } finally { setSending(false); }
  };

  return (
    <div className="px-6 py-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="rw-eyebrow">Comms</p>
          <h1 className="mt-1 rw-serif text-4xl">Notifications</h1>
        </div>
        <Button
          variant="outline"
          onClick={async () => {
            try {
              const r = await adminApi.scanExpiring();
              toast.success(`Sent ${r.notifications_created} expiring-plan reminder(s)`);
            } catch (e) {
              toast.error(formatApiError(e, "Scan failed"));
            }
          }}
          data-testid="notif-scan-expiring"
        >
          <RefreshCcw className="mr-2 h-4 w-4" /> Scan expiring plans
        </Button>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[400px_1fr]">
        <Card className="rw-card p-6">
          <h2 className="rw-serif text-2xl">Compose</h2>
          <div className="mt-4 space-y-3">
            <div>
              <Label>Title</Label>
              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="notif-title" />
            </div>
            <div>
              <Label>Body</Label>
              <Textarea rows={4} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} data-testid="notif-body" />
            </div>
            <div>
              <Label>Category</Label>
              <select
                className="mt-1 h-10 w-full rounded-md border bg-white px-3 text-sm"
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                data-testid="notif-category"
              >
                {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-3">
              <Switch checked={form.is_broadcast} onCheckedChange={(v) => setForm({ ...form, is_broadcast: v })} data-testid="notif-broadcast" />
              <span className="text-sm">{form.is_broadcast ? "Broadcast to all active users" : "Target specific members"}</span>
            </div>
            {!form.is_broadcast && (
              <div>
                <Label>Target membership IDs (comma or space separated)</Label>
                <Textarea
                  rows={2}
                  value={form.target_membership_ids}
                  onChange={(e) => setForm({ ...form, target_membership_ids: e.target.value })}
                  placeholder="RW123456, RW234567"
                  data-testid="notif-targets"
                />
              </div>
            )}
            <div>
              <Label>CTA link (optional)</Label>
              <Input value={form.cta_link} onChange={(e) => setForm({ ...form, cta_link: e.target.value })} data-testid="notif-cta" />
            </div>
            <Button onClick={send} disabled={sending} className="w-full" data-testid="notif-send">
              {sending ? <Loader2 className="mr-1 h-4 w-4 animate-spin" /> : <Send className="mr-1 h-4 w-4" />}
              Send
            </Button>
          </div>
        </Card>

        <Card className="rw-card p-0 overflow-x-auto">
          {loading ? (
            <div className="grid place-items-center py-14"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
          ) : (
            <Table data-testid="notif-history">
              <TableHeader>
                <TableRow>
                  <TableHead>Sent</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Audience</TableHead>
                  <TableHead className="text-right">Delivered</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((n) => (
                  <TableRow key={n.id}>
                    <TableCell className="text-xs">{new Date(n.created_at).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</TableCell>
                    <TableCell className="max-w-[240px]">
                      <div className="font-medium">{n.title}</div>
                      <div className="truncate text-xs text-muted-foreground">{n.body}</div>
                    </TableCell>
                    <TableCell><Badge variant="outline">{n.category}</Badge></TableCell>
                    <TableCell><Badge variant="secondary">{n.is_broadcast ? "broadcast" : "targeted"}</Badge></TableCell>
                    <TableCell className="text-right font-semibold">{n.delivered_count}</TableCell>
                  </TableRow>
                ))}
                {items.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">No notifications sent yet.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </Card>
      </div>
    </div>
  );
}
