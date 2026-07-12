import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { ShieldAlert, X } from "lucide-react";
import { exitAdminPreview, getPreviewMeta } from "@/services/adminPreview";

/**
 * Sticky red banner shown on user-facing pages while an admin is
 * impersonating a member. Poll on route change so it disappears the moment
 * the admin clicks "Exit preview".
 */
export default function PreviewBanner() {
  const [meta, setMeta] = useState(getPreviewMeta());
  const location = useLocation();

  useEffect(() => {
    setMeta(getPreviewMeta());
  }, [location.pathname]);

  if (!meta) return null;

  const exit = () => {
    exitAdminPreview();
    setMeta(null);
    // Full reload back to admin so AuthContext restores admin session state.
    window.location.assign("/admin/users");
  };

  return (
    <div
      className="sticky top-0 z-50 flex items-center justify-between gap-3 border-b-2 border-red-500 bg-red-600 px-4 py-2 text-xs text-white shadow-md"
      data-testid="admin-preview-banner"
    >
      <div className="flex items-center gap-2 min-w-0">
        <ShieldAlert className="h-4 w-4 flex-shrink-0" />
        <div className="min-w-0">
          <div className="font-semibold uppercase tracking-widest">
            Admin preview
          </div>
          <div className="truncate text-white/90">
            Viewing as <span className="font-mono">{meta.membership_id}</span>
            {meta.full_name ? ` · ${meta.full_name}` : ""}
          </div>
        </div>
      </div>
      <button
        onClick={exit}
        className="inline-flex items-center gap-1 rounded-full bg-white/15 px-3 py-1 text-[11px] font-semibold hover:bg-white/25"
        data-testid="admin-preview-exit"
      >
        <X className="h-3 w-3" /> Exit preview
      </button>
    </div>
  );
}
