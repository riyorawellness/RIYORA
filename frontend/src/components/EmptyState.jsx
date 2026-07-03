import { Button } from "@/components/ui/button";

export default function EmptyState({
  icon: Icon,
  title,
  body,
  actionLabel,
  onAction,
  illustration,
}) {
  return (
    <div className="mx-auto flex max-w-sm flex-col items-center px-6 py-14 text-center">
      {illustration ? (
        <img src={illustration} alt="" className="mb-6 h-40 w-40 opacity-90" />
      ) : Icon ? (
        <div className="mb-5 grid h-20 w-20 place-items-center rounded-full bg-[hsl(var(--rw-sky-soft))] text-[hsl(var(--rw-royal))]">
          <Icon className="h-9 w-9" />
        </div>
      ) : null}
      <h3 className="rw-serif text-2xl text-foreground">{title}</h3>
      {body && <p className="mt-2 text-sm text-muted-foreground">{body}</p>}
      {actionLabel && onAction && (
        <Button className="mt-6 rounded-full" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
