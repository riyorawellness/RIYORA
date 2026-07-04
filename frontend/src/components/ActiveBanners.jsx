import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import api from "@/lib/api";
import { resolveUploadUrl } from "@/services/manualPayments";

/**
 * Fetches active banners for a given placement and renders a lightweight
 * auto-rotating carousel. Silent no-op when the API returns zero banners.
 *
 * Placements the admin can select in /admin/banners: "home" | "programs" | "checkout".
 */
export default function ActiveBanners({ placement, className = "", intervalMs = 5000 }) {
  const [items, setItems] = useState([]);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    let live = true;
    api.get(`/banners/active`, { params: { placement } })
      .then((r) => { if (live) setItems(r.data?.items || []); })
      .catch(() => {});
    return () => { live = false; };
  }, [placement]);

  useEffect(() => {
    if (items.length < 2) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % items.length), intervalMs);
    return () => clearInterval(t);
  }, [items.length, intervalMs]);

  if (!items.length) return null;

  const b = items[idx];
  const isExternal = /^https?:/.test(b.cta_link || "");

  const inner = (
    <div className="relative aspect-[16/7] w-full overflow-hidden rounded-2xl bg-neutral-900" data-testid={`banner-slide-${placement}`}>
      {b.image_url ? (
        <img
          src={resolveUploadUrl(b.image_url)}
          alt={b.title || "banner"}
          className="h-full w-full object-cover"
          loading="lazy"
        />
      ) : (
        <div
          className="h-full w-full"
          style={{ background: "linear-gradient(135deg, hsl(var(--rw-royal)) 0%, hsl(var(--rw-royal-deep)) 100%)" }}
        />
      )}
      <div
        className="pointer-events-none absolute inset-0"
        style={{ background: "linear-gradient(180deg, transparent 40%, rgba(0,0,0,0.65) 100%)" }}
      />
      <div className="absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 p-4 text-white">
        <div className="min-w-0 flex-1">
          {b.title && <div className="rw-serif truncate text-lg leading-tight">{b.title}</div>}
          {b.subtitle && <div className="mt-0.5 truncate text-[11px] opacity-90">{b.subtitle}</div>}
        </div>
        {b.cta_label && (
          <span className="inline-flex items-center gap-1 rounded-full bg-white/95 px-3 py-1 text-[11px] font-semibold text-[hsl(var(--rw-royal))]">
            {b.cta_label} {isExternal && <ExternalLink className="h-3 w-3" />}
          </span>
        )}
      </div>

      {items.length > 1 && (
        <>
          <button
            type="button"
            onClick={(e) => { e.preventDefault(); setIdx((idx - 1 + items.length) % items.length); }}
            className="absolute left-2 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-full bg-black/40 text-white opacity-0 transition group-hover:opacity-100"
            aria-label="Previous"
            data-testid={`banner-prev-${placement}`}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            onClick={(e) => { e.preventDefault(); setIdx((idx + 1) % items.length); }}
            className="absolute right-2 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-full bg-black/40 text-white opacity-0 transition group-hover:opacity-100"
            aria-label="Next"
            data-testid={`banner-next-${placement}`}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <div className="absolute inset-x-0 bottom-2 flex justify-center gap-1">
            {items.map((_, i) => (
              <button
                key={i}
                type="button"
                onClick={(e) => { e.preventDefault(); setIdx(i); }}
                className={`h-1.5 rounded-full transition-all ${i === idx ? "w-5 bg-white" : "w-1.5 bg-white/50"}`}
                aria-label={`Slide ${i + 1}`}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );

  const wrapperClass = `group block ${className}`;
  const testid = `banner-${placement}`;

  if (!b.cta_link) {
    return <div className={wrapperClass} data-testid={testid}>{inner}</div>;
  }
  if (isExternal) {
    return (
      <a
        href={b.cta_link}
        target="_blank"
        rel="noreferrer noopener"
        className={wrapperClass}
        data-testid={testid}
      >
        {inner}
      </a>
    );
  }
  return (
    <Link to={b.cta_link} className={wrapperClass} data-testid={testid}>
      {inner}
    </Link>
  );
}
