import Logo from "./components/brand/Logo";

export default function Loading() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-5 bg-[var(--color-paper)]">
      <Logo href={null} />
      <svg
        className="h-5 w-5 animate-spin text-[var(--color-signal)]"
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
    </div>
  );
}
