import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-medium tracking-wide uppercase font-mono transition-colors",
  {
    variants: {
      variant: {
        default:
          "border border-zinc-800 bg-zinc-900/90 text-zinc-300 shadow-sm",
        secondary:
          "border border-zinc-800/60 bg-zinc-950/80 text-zinc-400",
        outline:
          "border border-zinc-700/60 text-zinc-300 bg-transparent",
        active:
          "border border-white/20 bg-zinc-800 text-white shadow-sm",
        status:
          "border border-zinc-800/80 bg-black/60 text-zinc-400",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
