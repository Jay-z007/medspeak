import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-xs font-medium transition-all duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-zinc-400 disabled:pointer-events-none disabled:opacity-40 select-none active:scale-[0.98]",
  {
    variants: {
      variant: {
        default:
          "bg-zinc-100 text-zinc-950 hover:bg-white shadow-[0_1px_2px_rgba(0,0,0,0.4)] border border-white/20",
        secondary:
          "bg-zinc-900 text-zinc-200 border border-zinc-800/90 hover:bg-zinc-800/90 hover:border-zinc-700/80 hover:text-white",
        outline:
          "border border-zinc-800 bg-transparent text-zinc-300 hover:bg-zinc-900 hover:text-white hover:border-zinc-700",
        ghost:
          "text-zinc-400 hover:text-zinc-100 hover:bg-zinc-900/60",
        subtle:
          "bg-zinc-900/40 text-zinc-400 border border-zinc-800/50 hover:border-zinc-700 hover:text-zinc-200 hover:bg-zinc-900/80",
      },
      size: {
        default: "h-8 px-3.5 py-1.5",
        sm: "h-7 px-2.5 text-[11px]",
        lg: "h-10 px-5 text-sm",
        icon: "h-8 w-8",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
