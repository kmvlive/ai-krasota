import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const styles: Record<Variant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700",
  secondary: "bg-white text-ink border border-ink/10 hover:border-ink/25",
  ghost: "bg-transparent text-brand-600 hover:bg-brand-50",
};

/** Кнопка design-system. Touch-friendly: минимум 44x44px (.cursorrules, PRD §16.2). */
export function Button({ variant = "primary", className = "", ...props }: ButtonProps) {
  return (
    <button
      className={`inline-flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl px-5 py-3 text-sm font-medium transition ${styles[variant]} ${className}`}
      {...props}
    />
  );
}
