import { ChevronLeft } from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function TopBar({ title, subtitle, right, back = true, sticky = true }) {
  const nav = useNavigate();
  return (
    <div
      className={`${
        sticky ? "sticky top-0 z-30" : ""
      } -mx-4 flex items-center gap-3 border-b bg-white/95 px-4 py-3 backdrop-blur`}
      style={{ borderColor: "hsl(var(--rw-grey-100))" }}
    >
      {back && (
        <button
          onClick={() => nav(-1)}
          className="grid h-9 w-9 place-items-center rounded-full hover:bg-[hsl(var(--rw-grey-50))]"
          data-testid="topbar-back"
        >
          <ChevronLeft className="h-5 w-5 text-[hsl(var(--rw-royal-deep))]" />
        </button>
      )}
      <div className="min-w-0 flex-1">
        <h1 className="truncate rw-serif text-xl leading-tight text-foreground">{title}</h1>
        {subtitle && <p className="truncate text-xs text-muted-foreground">{subtitle}</p>}
      </div>
      {right}
    </div>
  );
}
