import { cn } from "@/lib/utils";
import { HTMLAttributes } from "react";

export function Badge({
  className,
  variant = "default",
  ...props
}: HTMLAttributes<HTMLSpanElement> & {
  variant?: "default" | "success" | "warning" | "muted";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        variant === "default" && "bg-indigo-500/15 text-indigo-300 ring-1 ring-indigo-500/30",
        variant === "success" && "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
        variant === "warning" && "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
        variant === "muted" && "bg-zinc-800 text-zinc-400 ring-1 ring-zinc-700",
        className,
      )}
      {...props}
    />
  );
}
