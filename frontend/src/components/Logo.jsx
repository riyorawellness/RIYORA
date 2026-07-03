import { Link } from "react-router-dom";

export default function Logo({ size = "md", withTagline = false, className = "" }) {
  const sizes = {
    sm: "text-xl",
    md: "text-2xl",
    lg: "text-4xl md:text-5xl",
    xl: "text-5xl md:text-6xl",
  };
  return (
    <Link to="/" className={`inline-flex flex-col items-start ${className}`} data-testid="auth-logo">
      <span className={`rw-serif font-semibold tracking-tight text-primary ${sizes[size]}`}>
        RIYORA
        <span className="ml-1 rw-serif text-foreground/60">wellness</span>
      </span>
      {withTagline && (
        <span className="mt-1 text-[11px] font-medium uppercase tracking-[0.3em] text-primary/70">
          Heal · Learn · Earn
        </span>
      )}
    </Link>
  );
}
