import type { HTMLAttributes } from "react";

/** Карточка с фиксированным премиальным shadow-токеном (PRD §22.3). */
export function Card({ className = "", ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={`rounded-2xl bg-white p-5 shadow-card ${className}`}
      {...props}
    />
  );
}
