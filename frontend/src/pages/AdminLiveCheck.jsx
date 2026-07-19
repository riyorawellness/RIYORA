import { useEffect, useState } from "react";
import { toast } from "sonner";
import {
  RefreshCw, Loader2, CheckCircle2, XCircle, PlayCircle, Send,
  ShieldCheck, ShieldAlert, Webhook, MessageSquareText, CreditCard, Copy,
  ListChecks, Repeat, AlertTriangle,
} from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import api, { formatApiError } from "@/lib/api";

function ModeChip({ mode }) {
  if (mode === "live") {
    return (
      <Badge className="bg-green-100 text-green-700 hover:bg-green-100" data-testid="mode-live">
        <ShieldCheck className="mr-1 h-3 w-3" /> LIVE
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" data-testid="mode-mock">
      <ShieldAlert className="mr-1 h-3 w-3" /> {mode === "dev" ? "DEV" : "MOCK"}
    </Badge>
  );
}

function Row({ label, value, ok = null, mono = false, testid }) {
  return (
    <div className="flex items-center justify-between border-b py-2 text-sm last:border-0" data-testid={testid}>
      <span className="text-muted-foreground">{label}</span>
      <span className={`text-right ${mono ? "font-mono text-[11px]" : "font-medium"}`}>
        {ok === true && <CheckCircle2 className="mr-1 inline h-3.5 w-3.5 text-green-600" />}
        {ok === false && <XCircle className="mr-1 inline h-3.5 w-3.5 text-red-600" />}
        {value || <span className="text-muted-foreground">—</span>}
      </span>
    </div>
  );
}

function CoverageRow({ c }) {
  return (
    <div
      className="flex items-center justify-between rounded border px-2 py-1.5 text-xs"
      data-testid={`coverage-event-${c.event}`}
    >
      <div className="flex items-center gap-2">
        {c.seen ? (
          <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
        ) : (
          <XCircle className="h-3.5 w-3.5 text-neutral-400" />
        )}
        <span className="font-mono text-[11px]">{c.event}</span>
      </div>
      <div className="text-[10px] text-muted-foreground">
        {c.last_seen_at ? new Date(c.last_seen_at).toLocaleDateString() : "not seen"}
      </div>
    </div>
  );
}

export default function AdminLiveCheck() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [testOrder, setTestOrder] = useState(null);
  const [creatingOrder, setCreatingOrder] = useState(false);
  const [events, setEvents] = useState([]);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [coverage, setCoverage] = useState(null);
  const [loadingCoverage, setLoadingCoverage] = useState(false);
  const [failedSubs, setFailedSubs] = useState(null);
  const [loadingFailedSubs, setLoadingFailedSubs] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await api.get("/admin/qa/live-check/status").then((x) => x.data);
      setStatus(r);
    } catch (e) {
      toast.error(formatApiError(e, "Failed to load status"));
    } finally {
      setLoading(false);
    }
  };

  const loadEvents = async () => {
    setLoadingEvents(true);
    try {
      const r = await api.get("/admin/qa/live-check/webhook-events?limit=25").then((x) => x.data);
      setEvents(r.events || []);
    } catch (e) {
      toast.error(formatApiError(e, "Failed to load webhook events"));
    } finally {
      setLoadingEvents(false);
    }
  };

  const loadCoverage = async () => {
    setLoadingCoverage(true);
    try {
      const r = await api.get("/admin/qa/live-check/webhook-coverage?lookback_days=30").then((x) => x.data);
      setCoverage(r);
    } catch (e) {
      toast.error(formatApiError(e, "Failed to load webhook coverage"));
    } finally {
      setLoadingCoverage(false);
    }
  };

  const loadFailedSubs = async () => {
    setLoadingFailedSubs(true);
    try {
      const r = await api.get("/admin/qa/failed-subscriptions?limit=50").then((x) => x.data);
      setFailedSubs(r);
    } catch (e) {
      toast.error(formatApiError(e, "Failed to load failed subscriptions"));
    } finally {
      setLoadingFailedSubs(false);
    }
  };

  useEffect(() => {
    load();
    loadEvents();
    loadCoverage();
    loadFailedSubs();
  }, []);

  const createTestOrder = async () => {
    setCreatingOrder(true);
    setTestOrder(null);
    try {
      const r = await api
        .post("/admin/qa/live-check/razorpay/test-order", { amount_paise: 100 })
        .then((x) => x.data);
      setTestOrder(r);
      if (r.is_mock) {
        toast.info("Mock order created — Razorpay is in mock mode.");
      } else {
        toast.success(`Live order created: ${r.order_id}`);
      }
    } catch (e) {
      toast.error(formatApiError(e, "Failed to create test order"));
    } finally {
      setCreatingOrder(false);
    }
  };

  const copy = (val) => {
    navigator.clipboard?.writeText(String(val || "")).then(() => toast.success("Copied"));
  };

  const rzp = status?.razorpay;

  return (
    <div className="px-6 py-6" data-testid="admin-live-check-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="rw-eyebrow">Launch Diagnostics</p>
          <h1 className="mt-1 rw-serif text-4xl">Live Integration Check</h1>
          <p className="text-sm text-muted-foreground">
            Verify Razorpay + MSG91 keys before flipping production. Non-destructive: no user is charged, no purchase created.
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={load} disabled={loading} data-testid="live-check-refresh">
          {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
          Refresh status
        </Button>
      </div>

      {loading && !status ? (
        <Card className="mt-6 p-10 text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
        </Card>
      ) : status ? (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          {/* RAZORPAY */}
          <Card className="rw-card p-5" data-testid="live-check-razorpay-card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CreditCard className="h-5 w-5 text-primary" />
                <h2 className="rw-serif text-xl">Razorpay</h2>
              </div>
              <ModeChip mode={rzp.status} />
            </div>
            <div className="mt-3">
              <Row label="Mock mode env" value={rzp.mock_mode ? "true" : "false"} ok={!rzp.mock_mode} testid="row-rzp-mock" />
              <Row label="Effective mode" value={rzp.is_mock_effective ? "MOCK" : "LIVE"} ok={!rzp.is_mock_effective} />
              <Row label="Key id" value={rzp.key_id_masked} mono testid="row-rzp-key" />
              <Row label="Key looks live (rzp_live_…)" value={rzp.is_live_key ? "yes" : "no"} ok={rzp.is_live_key} />
              <Row label="Secret configured" value={rzp.has_secret ? "yes" : "no"} ok={rzp.has_secret} />
              <Row label="Webhook secret" value={rzp.has_webhook_secret ? "yes" : "no"} ok={rzp.has_webhook_secret} />
              <div className="border-b py-2 text-sm last:border-0">
                <div className="text-muted-foreground">Webhook URLs</div>
                <div className="mt-1 break-all font-mono text-[11px] text-primary">
                  {rzp.webhook_url_hint}
                </div>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Button size="sm" onClick={createTestOrder} disabled={creatingOrder} data-testid="rzp-test-order-btn">
                {creatingOrder ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
                Create ₹1 test order
              </Button>
              {testOrder && (
                <Badge variant={testOrder.is_mock ? "secondary" : "default"} data-testid="rzp-test-order-result">
                  {testOrder.is_mock ? "MOCK" : "LIVE"} · {testOrder.order_id}
                </Badge>
              )}
            </div>

            {testOrder && (
              <div className="mt-3 rounded-lg border border-dashed bg-neutral-50 p-3 text-xs" data-testid="rzp-test-order-detail">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Order id</span>
                  <span className="flex items-center gap-1 font-mono">
                    {testOrder.order_id}
                    <button onClick={() => copy(testOrder.order_id)} className="text-primary">
                      <Copy className="h-3 w-3" />
                    </button>
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Amount</span>
                  <span className="font-mono">₹{(testOrder.amount_paise / 100).toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Currency</span>
                  <span className="font-mono">{testOrder.currency}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Receipt</span>
                  <span className="font-mono">{testOrder.receipt}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Key id</span>
                  <span className="font-mono">{testOrder.key_id}</span>
                </div>
              </div>
            )}
          </Card>

          {/* Firebase */}
          <Card className="rw-card p-5" data-testid="live-check-firebase-card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MessageSquareText className="h-5 w-5 text-primary" />
                <h2 className="rw-serif text-xl">Firebase Authentication</h2>
              </div>
              <ModeChip mode={status?.firebase?.status === "live" ? "live" : "dev"} />
            </div>
            <div className="mt-3">
              <Row label="Admin SDK initialised" value={status?.firebase?.configured ? "yes" : "no"} ok={status?.firebase?.configured} testid="row-fb-configured" />
              <Row label="Project id" value={status?.firebase?.project_id} mono testid="row-fb-project" />
              <Row label="Endpoints" value="/auth/firebase/sync · /register · /link-existing" mono />
            </div>
            <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-3 text-[11px] text-emerald-900">
              Users sign in via Google or email/password on the frontend. The Firebase ID token is verified server-side before RIYORA mints its own JWT. No SMS OTP dependency.
            </div>
          </Card>

          {/* Webhook coverage checklist */}
          <Card className="rw-card p-5 lg:col-span-2" data-testid="live-check-coverage-card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ListChecks className="h-5 w-5 text-primary" />
                <h2 className="rw-serif text-xl">Webhook coverage · last 30 days</h2>
                {coverage && (
                  <Badge
                    className={
                      coverage.checklist.every((c) => c.seen)
                        ? "bg-green-100 text-green-700 hover:bg-green-100"
                        : "bg-amber-100 text-amber-700 hover:bg-amber-100"
                    }
                    data-testid="coverage-verdict"
                  >
                    {coverage.checklist.filter((c) => c.seen).length}/{coverage.checklist.length} events seen
                  </Badge>
                )}
              </div>
              <Button variant="ghost" size="sm" onClick={loadCoverage} disabled={loadingCoverage} data-testid="coverage-refresh">
                {loadingCoverage ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              </Button>
            </div>

            <div className="mt-3 rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs text-blue-900" data-testid="prod-webhook-url-block">
              <div className="mb-2 font-semibold">Configure in Razorpay dashboard → Settings → Webhooks:</div>
              <div className="flex items-center justify-between gap-2 rounded bg-white p-2 font-mono text-[11px] break-all">
                <span data-testid="prod-webhook-url">
                  {`${(process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "")}/api/payments/razorpay/webhook`}
                </span>
                <button
                  onClick={() =>
                    copy(
                      `${(process.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "")}/api/payments/razorpay/webhook`,
                    )
                  }
                  className="text-primary"
                  data-testid="copy-webhook-url"
                >
                  <Copy className="h-3 w-3" />
                </button>
              </div>
              <div className="mt-2 text-[11px]">
                Active event alias: <span className="font-mono">/api/payments/webhook</span> also works.
              </div>
            </div>

            {coverage ? (
              <div className="mt-4 grid gap-4 md:grid-cols-2" data-testid="coverage-checklist">
                <div>
                  <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    <CreditCard className="h-3.5 w-3.5" /> One-time payments
                  </div>
                  <div className="space-y-1">
                    {coverage.checklist
                      .filter((c) => c.category === "one_time")
                      .map((c) => (
                        <CoverageRow key={c.event} c={c} />
                      ))}
                  </div>
                </div>
                <div>
                  <div className="mb-2 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    <Repeat className="h-3.5 w-3.5" /> Subscriptions · AutoPay
                  </div>
                  <div className="space-y-1">
                    {coverage.checklist
                      .filter((c) => c.category === "subscription")
                      .map((c) => (
                        <CoverageRow key={c.event} c={c} />
                      ))}
                  </div>
                </div>
                {coverage.extra_events_seen?.length > 0 && (
                  <div className="md:col-span-2 mt-2 rounded-md bg-neutral-50 p-2 text-[11px]">
                    <div className="font-semibold text-muted-foreground">Other events observed:</div>
                    <div className="mt-1 font-mono text-[10px]">
                      {coverage.extra_events_seen.join(" · ")}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="mt-4 text-sm text-muted-foreground">Loading…</div>
            )}
          </Card>

          {/* Failed subscriptions */}
          <Card className="rw-card p-5 lg:col-span-2" data-testid="live-check-failed-subs-card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-red-600" />
                <h2 className="rw-serif text-xl">Failed subscriptions</h2>
                {failedSubs && (
                  <Badge
                    className={
                      (failedSubs.items || []).length === 0
                        ? "bg-green-100 text-green-700 hover:bg-green-100"
                        : "bg-red-100 text-red-700 hover:bg-red-100"
                    }
                    data-testid="failed-subs-count"
                  >
                    {(failedSubs.items || []).length} halted/pending
                  </Badge>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={loadFailedSubs}
                disabled={loadingFailedSubs}
                data-testid="failed-subs-refresh"
              >
                {loadingFailedSubs ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              </Button>
            </div>

            {failedSubs && (failedSubs.items || []).length === 0 && (
              <p className="mt-3 text-sm text-muted-foreground" data-testid="failed-subs-empty">
                All active subscriptions are healthy — no halted or pending mandates in the last 30 days.
              </p>
            )}

            {failedSubs && (failedSubs.items || []).length > 0 && (
              <div className="mt-3 space-y-2" data-testid="failed-subs-list">
                {(failedSubs.items || []).map((s) => (
                  <div
                    key={s.subscription_id}
                    className="flex items-center justify-between rounded border border-red-100 bg-red-50/60 p-2 text-xs"
                    data-testid={`failed-sub-row-${s.subscription_id}`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate font-semibold text-red-900">
                        {s.program_name}
                        <span className="ml-2 rounded bg-white px-1.5 py-0.5 text-[10px] font-mono text-red-700">
                          {s.status}
                        </span>
                      </div>
                      <div className="mt-0.5 text-[11px] text-muted-foreground">
                        {s.user?.full_name || s.user_membership_id} · {s.user?.email || s.user?.mobile || ""}
                      </div>
                    </div>
                    <div className="text-right text-[10px] font-mono text-muted-foreground">
                      <div>{s.frequency}</div>
                      <div>{s.subscription_id.slice(0, 20)}…</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Webhook events */}
          <Card className="rw-card p-5 lg:col-span-2" data-testid="live-check-webhook-card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Webhook className="h-5 w-5 text-primary" />
                <h2 className="rw-serif text-xl">Recent Razorpay webhook events</h2>
                <Badge variant="secondary" data-testid="webhook-count">{events.length}</Badge>
              </div>
              <Button variant="ghost" size="sm" onClick={loadEvents} disabled={loadingEvents} data-testid="webhook-refresh">
                {loadingEvents ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              </Button>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Configure your Razorpay dashboard webhook to any of: <span className="font-mono">/api/payments/webhook</span> or <span className="font-mono">/api/payments/razorpay/webhook</span>.
              Events land here as soon as Razorpay hits either URL.
            </p>

            {events.length === 0 ? (
              <div className="mt-4 rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                No webhook events yet. Trigger a real payment or use the Razorpay dashboard test-event feature to verify connectivity.
              </div>
            ) : (
              <div className="mt-4 divide-y" data-testid="webhook-events-list">
                {events.map((e) => (
                  <div key={e.id} className="flex items-center justify-between py-2 text-sm">
                    <div>
                      <div className="font-mono text-[11px] text-primary">{e.event}</div>
                      <div className="text-[11px] text-muted-foreground">{e.target || "—"}</div>
                    </div>
                    <div className="text-[11px] text-muted-foreground">
                      {new Date(e.created_at).toLocaleString()}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      ) : null}
    </div>
  );
}
