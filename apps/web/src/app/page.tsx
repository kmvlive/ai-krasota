import Link from "next/link";

// Лендинг платформы — структура по PRD §13.1.
// Полноценная реализация (hero-анимация, калькулятор тарифов, FAQ) — Фаза 1 MVP.
export default function LandingPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col items-center justify-center gap-6 px-4">
      <h1 className="text-center text-4xl font-semibold tracking-tight sm:text-5xl">
        Ваш салон красоты — онлайн за 5 минут
      </h1>
      <p className="max-w-xl text-center text-lg text-ink/70">
        Сайт на субдомене, онлайн-запись, умная CRM и AI-ассистент. Без программистов
        и дизайнеров.
      </p>
      <Link
        href="/signup"
        className="rounded-xl bg-brand-600 px-8 py-4 text-base font-medium text-white shadow-elevated transition hover:bg-brand-700"
      >
        Попробовать 14 дней бесплатно
      </Link>
      <p className="text-sm text-ink/50">Карта не нужна</p>
    </main>
  );
}
