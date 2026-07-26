interface ErrorStateProps {
  message: string;
}

export function ErrorState({ message }: ErrorStateProps) {
  return (
    <div className="rounded-xl border border-[#d03b3b]/30 bg-[#d03b3b]/5 p-6 flex flex-col gap-1">
      <p className="font-medium text-[#d03b3b]">Couldn&apos;t build a portfolio</p>
      <p className="text-sm text-text-secondary">{message}</p>
    </div>
  );
}
