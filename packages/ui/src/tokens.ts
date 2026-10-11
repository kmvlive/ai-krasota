// Премиальные дизайн-токены (PRD §3.3, §22.3).
// Мастер выбирает только из того, что уже красиво — система не даёт «сломать» дизайн.

export const PALETTES = [
  { id: "lilac", name: "Сирень", bg: "#fafafa", accent: "#7c3aed" },
  { id: "blush", name: "Пудра", bg: "#fdf7f5", accent: "#c26a5b" },
  { id: "mint", name: "Мята", bg: "#f4faf7", accent: "#2f8f6b" },
  { id: "noir", name: "Нуар", bg: "#111113", accent: "#d4af37" },
] as const;

export const SHADOWS = {
  card: "0 1px 2px rgba(17,17,19,0.04), 0 8px 24px rgba(17,17,19,0.06)",
  elevated: "0 12px 48px rgba(17,17,19,0.12)",
} as const;

export const SPACING = { xs: 4, sm: 8, md: 16, lg: 24, xl: 32, "2xl": 48 } as const;

/** Минимальный touch-target по PRD §16.2 */
export const MIN_TOUCH_TARGET = 44;
