import { useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckCircle2, Clock, Loader2, RefreshCw, ShieldCheck, XCircle } from "lucide-react";

import api, { formatApiError } from "@/lib/api";

/**
 * Admin panel — review + approve/reject user-submitted email or mobile
 * change requests. Every approve/reject requires the admin to re-enter
 * their own password (a bearer token alone is not enough — defense in
 * depth against a stolen admin session).
 */
export default function AdminChangeRequests() {
  const [items, setItems] = useState([]);
  const [pending, setPending] = useState(0);
  const [tab, setTab] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [modal, setModal] = useState(null); // { request, mode: "approve"|"reject" }

  const load = async () => {
    setLoading(true);
    try {
      const q = tab === "all" ? "" : `?status=${tab}`;
      const { data } = await api.get(`/admin/change-requests${q}`);
      setItems(data.items || []);
      setPending(data.pending || 0);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [tab]);

  return (
    <div className="p-6" data-testid="admin-change-requests-page">
      <div className="flex items-center justify-between">
        <div>
          <p className="rw-eyebrow">User management</p>
          <h1 className="mt-1 rw-serif text-3xl">Profile change requests</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {pending} pending · audit-logged · admin password required to approve/reject
          </p>
        </div>
        <button onClick={load} className="rw-btn-pill rw-btn-ghost" data-testid="acr-refresh">
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      <div className="mt-6 flex gap-2">
        {["pending", "approved", "rejected", "all"].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`rounded-full px-4 py-1.5 text-xs font-semibold ${tab === t ? "bg-[hsl(var(--rw-royal))] text-white" : "border border-neutral-200 text-foreground"}`}
            data-testid={`acr-tab-${t}`}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      <div className="mt-6 overflow-hidden rounded-2xl border border-neutral-200">
        {loading ? (
          <div className="grid place-items-center p-10"><Loader2 className="h-6 w-6 animate-spin text-primary" /></div>
        ) : items.length === 0 ? (
          <div className="p-10 text-center text-sm text-muted-foreground" data-testid="acr-empty">No requests found.</div>
        ) : (
          <table className="w-full text-left text-xs">
            <thead className="bg-neutral-50 text-[10px] uppercase tracking-widest text-muted-foreground">
              <tr>
                <th className="p-3">When</th>
                <th className="p-3">User</th>
                <th className="p-3">Field</th>
                <th className="p-3">From → To</th>
                <th className="p-3">Reason</th>
                <th className="p-3">Status</th>
                <th className="p-3">Action</th>
              </tr>
            </thead>
            <tbody data-testid="acr-list">
              {items.map((r) => (
                <tr key={r.id} className="border-t border-neutral-100">
                  <td className="p-3 text-[11px] text-muted-foreground">{r.requested_at?.slice(0,16).replace("T"," ")}</td>
                  <td className="p-3">
                    <div className="font-semibold">{r.user_full_name || "—"}</div>
                    <div className="text-[11px] text-muted-foreground">{r.user_membership_id}</div>
                  </td>
                  <td className="p-3 uppercase text-[11px] font-semibold">{r.field}</td>
                  <td className="p-3">
                    <div className="font-mono text-[11px]">{r.current_value || "—"}</div>
                    <div className="font-mono text-[11px] text-emerald-700">→ {r.new_value}</div>
                  </td>
                  <td className="p-3 text-[11px] text-muted-foreground max-w-[200px]">{r.reason || "—"}</td>
                  <td className="p-3"><StatusBadge s={r.status} /></td>
                  <td className="p-3">
                    {r.status === "pending" ? (
                      <div className="flex gap-1">
                        <button onClick={() => setModal({ request: r, mode: "approve" })} className="rounded-full bg-emerald-600 px-3 py-1 text-[11px] font-semibold text-white" data-testid={`acr-approve-${r.id}`}>Approve</button>
                        <button onClick={() => setModal({ request: r, mode: "reject" })} className="rounded-full border border-red-200 px-3 py-1 text-[11px] font-semibold text-red-700" data-testid={`acr-reject-${r.id}`}>Reject</button>
                      </div>
                    ) : (
                      <span className="text-[11px] text-muted-foreground">{r.reviewer_id ? `by ${r.reviewer_id}` : "—"}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {modal && (
        <PasswordModal
          req={modal.request}
          mode={modal.mode}
          onClose={() => setModal(null)}
          onDone={() => { setModal(null); load(); }}
        />
      )}
    </div>
  );
}

function StatusBadge({ s }) {
  if (s === "approved") return <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700"><CheckCircle2 className="h-3 w-3" /> Approved</span>;
  if (s === "rejected") return <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-0.5 text-[10px] font-semibold text-red-700"><XCircle className="h-3 w-3" /> Rejected</span>;
  return <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-800"><Clock className="h-3 w-3" /> Pending</span>;
}

function PasswordModal({ req, mode, onClose, onDone }) {
  const [password, setPassword] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const isApprove = mode === "approve";

  const submit = async (e) => {
    e.preventDefault();
    if (!password) return toast.error("Enter your admin password");
    setBusy(true);
    try {
      await api.post(`/admin/change-requests/${req.id}/${mode}`, {
        admin_password: password,
        note: note.trim() || null,
      });
      toast.success(isApprove ? "Approved — user's account updated." : "Rejected — user has been notified.");
      onDone();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" data-testid="acr-modal">
      <form onSubmit={submit} className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <div className="flex items-center gap-2">
          <div className={`grid h-9 w-9 place-items-center rounded-full ${isApprove ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
            <ShieldCheck className="h-4 w-4" />
          </div>
          <div>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Confirm as admin</p>
            <h2 className="rw-serif text-xl">{isApprove ? "Approve" : "Reject"} — {req.field}</h2>
          </div>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          {req.user_full_name} · {req.user_membership_id}<br/>
          <span className="font-mono">{req.current_value || "—"}</span> → <span className="font-mono">{req.new_value}</span>
        </p>

        <div className="mt-4">
          <label className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">Admin password</label>
          <input
            type="password"
            className="rw-input mt-1"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoFocus
            data-testid="acr-modal-password"
          />
        </div>

        <div className="mt-3">
          <label className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
            {isApprove ? "Approval note (optional)" : "Rejection reason (visible to user)"}
          </label>
          <textarea
            className="rw-input mt-1 min-h-[60px]"
            rows={2}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            data-testid="acr-modal-note"
          />
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-full border border-neutral-200 px-4 py-2 text-xs font-semibold" data-testid="acr-modal-cancel">Cancel</button>
          <button
            type="submit"
            disabled={busy}
            className={`rounded-full px-4 py-2 text-xs font-semibold text-white ${isApprove ? "bg-emerald-600" : "bg-red-600"}`}
            data-testid="acr-modal-confirm"
          >
            {busy ? <Loader2 className="mr-1 inline h-3 w-3 animate-spin" /> : null}
            Confirm {isApprove ? "approval" : "rejection"}
          </button>
        </div>
      </form>
    </div>
  );
}
