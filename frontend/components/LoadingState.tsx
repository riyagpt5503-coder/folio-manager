export function LoadingState() {
  return (
    <div className="rounded-xl border border-[var(--border-hairline)] bg-surface-1 p-8 flex flex-col items-center justify-center gap-3 text-text-secondary">
      <div className="h-6 w-6 rounded-full border-2 border-[var(--gridline)] border-t-[var(--series-blue)] animate-spin" />
      <p className="text-sm">Fetching market data and optimizing your portfolio…</p>
    </div>
  );
}
