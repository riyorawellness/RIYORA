import { Link } from "react-router-dom";
import { TID } from "@/constants/testIds";

export default function Logo({ size = "md", withTagline = false, to = "/", className = "" }) {
  const sizes = {
    sm: "text-lg",
    md: "text-xl",
    lg: "text-4xl",
    xl: "text-5xl md:text-6xl",
  };
  return (
    <Link to={to} className={`inline-flex flex-col ${className}`} data-testid="auth-logo">
      <span
        className={`rw-serif font-semibold tracking-tight text-[hsl(var(--rw-royal-deep))] ${sizes[size]}`}
      >
        RIYORA
        <span className="ml-1 font-light text-[hsl(var(--rw-royal))]/70">wellness</span>
      </span>
      {withTagline && (
        <span className="mt-1 text-[10px] font-semibold uppercase tracking-[0.28em] text-[hsl(var(--rw-gold))]">
          Heal · Learn · Earn
        </span>
      )}
    </Link>
  );
}
