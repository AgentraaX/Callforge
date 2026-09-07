import Link from "next/link";
import Logo from "./components/brand/Logo";
import ThemeButton from "./components/ui/ThemeButton";

export default function NotFound() {
  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-6 bg-paper px-5 text-center">
      <Logo href="/" />
      <div>
        <p className="font-mono text-[12px] uppercase tracking-[0.2em] text-signal">Error 404</p>
        <h1 className="mt-2 font-display text-[40px] font-semibold tracking-[-0.02em] text-ink">
          Page not found
        </h1>
        <p className="mx-auto mt-2 max-w-[38ch] text-[14px] leading-[1.6] text-slate">
          That link doesn&apos;t point anywhere. Head back and try again.
        </p>
      </div>
      <ThemeButton href="/">Back to home</ThemeButton>
      <Link href="/dashboard" className="text-[13px] font-medium text-signal hover:underline">
        Go to the dashboard
      </Link>
    </div>
  );
}
