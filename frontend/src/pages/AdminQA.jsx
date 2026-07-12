import { useState } from "react";
import { toast } from "sonner";
import {
  ShieldCheck, ShieldAlert, PlayCircle, FileDown, CheckCircle2, XCircle, Loader2,
  RefreshCw, Info,
} from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import api, { formatApiError } from "@/lib/api";
import { downloadBlob } from "@/services/analytics";

export default function AdminQA() {
  const [report, setReport] = useState(null);
  const [running, setRunning] = useState(false);
  const [downloading, setDownloading] = useState(false);

  const runBRV = async () => {
    setRunning(true);
    try {
      const r = await api.get("/admin/qa/brv").then((x) => x.data);
      setReport(r);
      if (r.overall === "PASS") {
        toast.success(`Business Rule Validation: ${r.passed}/${r.total} PASSED`);
      } else {
        toast.warning(`BRV completed: ${r.failed} rule(s) failed`);
      }
    } catch (e) {
      toast.error(formatApiError(e, "BRV run failed"));
    } finally {
      setRunning(false);
    }
  };

  const downloadPDF = async () => {
    setDownloading(true);
    try {
      const blob = await api.get("/admin/qa/brv/pdf", { responseType: "blob" }).then((r) => r.data);
      downloadBlob(blob, `riyora-brv-${new Date().toISOString().slice(0, 10)}.pdf`);
      toast.success("BRV report downloaded");
    } catch (e) {
      toast.error(formatApiError(e, "Download failed"));
    } finally {
      setDownloading(false);
    }
  };

  const rulesByCategory = groupBy(report?.rules || [], "category");

  return (
    <div className="px-6 py-6" data-testid="admin-qa-page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="rw-eyebrow">Phase 9 · Quality Assurance</p>
          <h1 className="mt-1 rw-serif text-4xl">Business Rule Validation</h1>
          <p className="text-sm text-muted-foreground">
            Live check of every business rule against the running database. Generate a downloadable PDF report.
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={runBRV} disabled={running} data-testid="qa-run-btn">
            {running ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <PlayCircle className="mr-2 h-4 w-4" />}
            {report ? "Re-run BRV" : "Run BRV"}
          </Button>
          <Button variant="secondary" onClick={downloadPDF} disabled={!report || downloading} data-testid="qa-pdf-btn">
            {downloading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileDown className="mr-2 h-4 w-4" />}
            Download PDF report
          </Button>
        </div>
      </div>

      {/* Verdict card */}
      {report && (
        <Card className={`mt-6 border-2 p-5 ${report.overall === "PASS" ? "border-green-500" : "border-red-500"}`}
              data-testid="qa-verdict">
          <div className="flex items-center gap-4">
            <div className={`grid h-14 w-14 place-items-center rounded-full ${report.overall === "PASS" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
              {report.overall === "PASS" ? <ShieldCheck className="h-7 w-7" /> : <ShieldAlert className="h-7 w-7" />}
            </div>
            <div className="flex-1">
              <div className="rw-eyebrow">Overall verdict</div>
              <div className={`rw-serif text-4xl ${report.overall === "PASS" ? "text-green-700" : "text-red-700"}`}>
                {report.overall}
              </div>
              <div className="text-sm text-muted-foreground">
                {report.passed}/{report.total} rules passed · generated {new Date(report.generated_at).toLocaleString()}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3 text-center text-sm">
              <div className="rounded-lg bg-green-50 px-4 py-2">
                <div className="text-2xl font-semibold text-green-700">{report.passed}</div>
                <div className="text-[10px] uppercase tracking-widest text-green-700">Passed</div>
              </div>
              <div className="rounded-lg bg-red-50 px-4 py-2">
                <div className="text-2xl font-semibold text-red-700">{report.failed}</div>
                <div className="text-[10px] uppercase tracking-widest text-red-700">Failed</div>
              </div>
            </div>
          </div>
        </Card>
      )}

      {!report && !running && (
        <Card className="mt-6 border-dashed p-10 text-center">
          <Info className="mx-auto h-10 w-10 text-muted-foreground/60" />
          <p className="mt-3 text-sm text-muted-foreground">
            Click <strong>Run BRV</strong> to validate all business rules against the live database.
          </p>
        </Card>
      )}

      {running && (
        <Card className="mt-6 p-10 text-center">
          <Loader2 className="mx-auto h-10 w-10 animate-spin text-primary" />
          <p className="mt-3 text-sm text-muted-foreground">Running validation checks against the database…</p>
        </Card>
      )}

      {/* Category cards */}
      {report && (
        <section className="mt-8 grid gap-6 lg:grid-cols-2">
          {Object.entries(rulesByCategory).map(([cat, rules]) => {
            const passed = rules.filter((r) => r.status === "Pass").length;
            const total = rules.length;
            return (
              <Card key={cat} className="rw-card p-4" data-testid={`qa-cat-${cat.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`}>
                <div className="mb-2 flex items-center justify-between">
                  <h3 className="rw-serif text-xl">{cat}</h3>
                  <Badge variant={passed === total ? "default" : "destructive"}>
                    {passed}/{total} passed
                  </Badge>
                </div>
                <div className="divide-y">
                  {rules.map((r) => (
                    <div key={r.id} className="flex items-start gap-3 py-2">
                      <div className="mt-0.5">
                        {r.status === "Pass" ? (
                          <CheckCircle2 className="h-4 w-4 text-green-600" />
                        ) : (
                          <XCircle className="h-4 w-4 text-red-600" />
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium">{r.name}</div>
                        <div className="text-[11px] text-muted-foreground">
                          <span className="font-mono">{r.id}</span> · expected: <em>{r.expected}</em>
                        </div>
                        <div className="mt-1 text-[11px]">
                          <span className={r.status === "Pass" ? "text-green-700" : "text-red-700"}>
                            actual:
                          </span>{" "}
                          <span className="tabular-nums">{r.actual || "—"}</span>
                        </div>
                        {r.remarks && (
                          <div className="text-[11px] italic text-muted-foreground">{r.remarks}</div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            );
          })}
        </section>
      )}
    </div>
  );
}

function groupBy(items, key) {
  const out = {};
  for (const it of items) {
    (out[it[key]] ||= []).push(it);
  }
  return out;
}
