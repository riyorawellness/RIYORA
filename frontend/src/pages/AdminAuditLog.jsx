import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Search } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import { adminApi } from "@/services/admin";
import { formatApiError } from "@/lib/api";

export default function AdminAuditLog() {
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [q, setQ] = useState("");
  const [action, setAction] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const params = { page, page_size: 50 };
      if (q) params.q = q;
      if (action) params.action = action;
      const d = await adminApi.auditLog(params);
      setItems(d.items || []);
      setTotal(d.total || 0);
    } catch (e) {
      toast.error(formatApiError(e, "Load failed"));
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [page]);

  return (
    <div className="px-6 py-6">
      <p className="rw-eyebrow">Security</p>
      <h1 className="mt-1 rw-serif text-4xl">Audit log</h1>
      <p className="text-sm text-muted-foreground">{total} entries · every admin & user action tracked</p>

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search action / target / actor" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" data-testid="audit-q" />
        </div>
        <Input placeholder="Action filter (e.g. payment.)" value={action} onChange={(e) => setAction(e.target.value)} className="w-48" data-testid="audit-action" />
        <Button onClick={() => { setPage(1); load(); }} data-testid="audit-apply">Apply</Button>
      </div>

      <Card className="rw-card mt-4 overflow-x-auto p-0">
        {loading ? (
          <div className="grid place-items-center py-14"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>
        ) : (
          <Table data-testid="audit-table">
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Actor</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Target</TableHead>
                <TableHead>Meta</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-xs">{new Date(r.created_at).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit" })}</TableCell>
                  <TableCell className="font-mono text-xs">{r.actor_membership_id || "—"}</TableCell>
                  <TableCell><Badge variant="outline" className="text-[10px]">{r.action}</Badge></TableCell>
                  <TableCell className="font-mono text-xs max-w-[220px] truncate">{r.target || "—"}</TableCell>
                  <TableCell className="max-w-[320px] truncate text-xs text-muted-foreground">
                    {r.meta ? JSON.stringify(r.meta) : "—"}
                  </TableCell>
                </TableRow>
              ))}
              {items.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-10 text-center text-muted-foreground">No entries.</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        )}
      </Card>

      <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
        <span>Page {page}</span>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" disabled={page === 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>Prev</Button>
          <Button size="sm" variant="outline" disabled={items.length < 50} onClick={() => setPage((p) => p + 1)}>Next</Button>
        </div>
      </div>
    </div>
  );
}
