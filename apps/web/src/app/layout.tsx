import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI-krasota — сайт салона красоты с онлайн-записью за 5 минут",
  description:
    "Премиальная SaaS-платформа для бьюти-мастеров: сайт, календарь, CRM, AI-ассистент.",
  manifest: "/manifest.webmanifest", // PWA (PRD §16.2)
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#7c3aed",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
