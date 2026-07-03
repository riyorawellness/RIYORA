import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Loader2, Mail } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { toast } from "sonner";

import api, { formatApiError } from "@/lib/api";
import { useSystemInfo } from "@/hooks/useSystemInfo";

const SLUG_TITLES = {
  privacy: "Privacy Policy",
  terms: "Terms of Service",
  "data-security": "Data & Security",
  faq: "Help & FAQ",
  contact: "Contact Us",
  about: "About Us",
  refund: "Refund Policy",
  support: "Support",
};

/**
 * Universal reader for CMS pages. Route it as /legal/:slug so a single
 * component can render Privacy, Terms, Data & Security, FAQ, Contact.
 * Content comes from the admin CMS.
 */
export default function LegalPage() {
  const { slug: paramSlug } = useParams();
  const nav = useNavigate();
  const slug = paramSlug || "privacy";
  const [page, setPage] = useState(null);
  const [loading, setLoading] = useState(true);
  const sys = useSystemInfo();

  useEffect(() => {
    setLoading(true);
    api.get(`/cms/pages/${slug}`)
      .then((r) => setPage(r.data))
      .catch((e) => toast.error(formatApiError(e, "Unable to load page")))
      .finally(() => setLoading(false));
  }, [slug]);

  const title = page?.title || SLUG_TITLES[slug] || "Page";
  const updated = page?.updated_at;

  return (
    <div className="min-h-screen bg-white pb-24" data-testid={`legal-page-${slug}`}>
      {/* Header */}
      <div className="sticky top-0 z-10 border-b bg-white/95 backdrop-blur">
        <div className="rw-phone flex items-center gap-3 px-4 py-3">
          <button
            onClick={() => nav(-1)}
            className="grid h-9 w-9 place-items-center rounded-full hover:bg-neutral-100"
            aria-label="Back"
            data-testid={`legal-back-${slug}`}
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="min-w-0 flex-1">
            <p className="rw-eyebrow">RIYORA Wellness</p>
            <h1 className="truncate rw-serif text-xl leading-tight">{title}</h1>
          </div>
        </div>
      </div>

      <div className="rw-phone px-5 pt-4">
        {updated && (
          <p className="text-[11px] text-muted-foreground" data-testid={`legal-updated-${slug}`}>
            Last updated: {new Date(updated).toLocaleDateString("en-IN", {
              day: "2-digit", month: "long", year: "numeric",
            })}
          </p>
        )}

        {loading ? (
          <div className="grid place-items-center py-20 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        ) : page?.empty || !page?.body ? (
          <div className="mt-10 rounded-2xl border border-dashed border-neutral-200 p-8 text-center text-sm text-muted-foreground">
            This page hasn&apos;t been published yet. Please check back soon.
          </div>
        ) : (
          <>
            <article
              className="prose prose-sm mt-4 max-w-none text-neutral-800 [&_h1]:rw-serif [&_h1]:text-2xl [&_h1]:text-[hsl(var(--rw-royal))] [&_h2]:rw-serif [&_h2]:mt-6 [&_h2]:text-lg [&_h2]:text-[hsl(var(--rw-royal))] [&_h3]:mt-4 [&_h3]:font-semibold [&_p]:leading-relaxed [&_ul]:my-3 [&_li]:my-1 [&_a]:font-medium [&_a]:text-[hsl(var(--rw-royal))]"
              data-testid={`legal-body-${slug}`}
            >
              <ReactMarkdown>{page.body}</ReactMarkdown>
            </article>

            {/* Prominent email CTA on Contact / FAQ / Support pages */}
            {(slug === "contact" || slug === "faq" || slug === "support") && sys?.support_email && (
              <a
                href={`mailto:${sys.support_email}?subject=${encodeURIComponent(
                  "Support Request - RIYORA Wellness"
                )}`}
                className="mt-6 flex items-center gap-3 rounded-2xl border-2 border-[hsl(var(--rw-royal))] bg-[hsl(var(--rw-sky-soft))] p-4 transition hover:bg-white"
                data-testid={`legal-email-${slug}`}
              >
                <div className="grid h-10 w-10 place-items-center rounded-full bg-[hsl(var(--rw-royal))] text-white">
                  <Mail className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-[10px] uppercase tracking-widest text-muted-foreground">Email support</div>
                  <div className="truncate font-semibold text-[hsl(var(--rw-royal))]">{sys.support_email}</div>
                  <div className="truncate text-[11px] text-muted-foreground">Subject: Support Request - RIYORA Wellness</div>
                </div>
              </a>
            )}
          </>
        )}

        <p className="mt-10 text-center text-[10px] text-muted-foreground">
          © {new Date().getFullYear()} {sys?.company_name || "RIYORA Wellness"}. All Rights Reserved. · v{sys?.application_version || "1.0.0"}
        </p>
      </div>
    </div>
  );
}
