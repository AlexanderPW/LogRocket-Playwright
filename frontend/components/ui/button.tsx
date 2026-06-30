import { cn } from "@/lib/utils";
import { ButtonHTMLAttributes, forwardRef } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "md", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center rounded-lg font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none",
          variant === "default" &&
            "bg-indigo-500 text-white hover:bg-indigo-400 shadow-sm shadow-indigo-500/20",
          variant === "secondary" &&
            "bg-zinc-800 text-zinc-100 hover:bg-zinc-700 border border-zinc-700",
          variant === "ghost" && "text-zinc-300 hover:bg-zinc-800 hover:text-white",
          variant === "danger" && "bg-red-600 text-white hover:bg-red-500",
          size === "sm" && "h-8 px-3 text-sm",
          size === "md" && "h-10 px-4 text-sm",
          size === "lg" && "h-11 px-6",
          className,
        )}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
