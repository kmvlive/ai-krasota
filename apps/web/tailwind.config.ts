import type { Config } from "tailwindcss";

// Премиальные дизайн-токены (PRD §22.3): фиксированные отступы и тени,
// чтобы система «не давала сломать дизайн».
const config: Config = {
  content: [
    "./src/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f5f3ff",
          100: "#ede9fe",
          500: "#8b5cf6",
          600: "#7c3aed",
          700: "#6d28d9",
          900: "#4c1d95",
        },
        surface: "#fafafa",
        ink: "#111113",
      },
      fontFamily: {
        sans: ["Inter", "Manrope", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(17,17,19,0.04), 0 8px 24px rgba(17,17,19,0.06)",
        elevated: "0 12px 48px rgba(17,17,19,0.12)",
      },
    },
  },
  plugins: [],
};

export default config;
