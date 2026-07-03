import { useState } from "react";
import { toast } from "sonner";
import { Download, FileText, Loader2 } from "lucide-react";

import TopBar from "@/components/TopBar";
import { reportsApi } from "@/services/referrals";
import { formatApiError } from "@/lib/api";

const REPORTS = [
  { key: "referral", title: "Referral Report", body: "Your 3-level downline with join dates and status." },
  { key: "income", title: "Income Report", body: "Commission ledger + summary buckets." },
  { key: "downline", title: "Downline Report", body: "Pure hierarchy tree by level." },
  { key: "subscription", title: "Subscription Report", body: "Inner Peace cycles + activity counts." },
  { key: "transaction", title: "Transaction Report", body: "All payments with GST breakdown." },
];

export default function Reports() {
  const [downloading, setDownloading] = useState(null);

  const download = async (type) => {
    setDownloading(type);
    try {
      const blob = await reportsApi.downloadReport(type);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `riyora-${type}-report.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Report downloaded");
    } catch (e) {
      toast.error(formatApiError(e, "Download failed"));
    } finally {
      setDownloading(null);
    }
  };

  return (
    <div className="px-4 pt-3 pb-24">
      <TopBar title="Reports" subtitle="Download PDF reports" />

      <div className="mt-4 space-y-3" data-testid="reports-list">
        {REPORTS.map((r) => (
          <div key={r.key} className="rw-card p-4" data-testid={`report-${r.key}`}>
            <div className="flex items-start gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-full bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal))]">
                <FileText className="h-4 w-4" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 className="rw-serif text-lg">{r.title}</h3>
                <p className="text-xs text-muted-foreground">{r.body}</p>
              </div>
            </div>
            <button
              onClick={() => download(r.key)}
              disabled={downloading === r.key}
              className="mt-3 flex w-full items-center justify-center gap-2 rw-btn-pill bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal-deep))]"
              data-testid={`report-download-${r.key}`}
            >
              {downloading === r.key ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Download PDF
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
