interface DisclaimerProps {
  text: string;
  dataAsOf: string;
  lookbackYears: number;
}

export function Disclaimer({ text, dataAsOf, lookbackYears }: DisclaimerProps) {
  return (
    <p className="text-xs text-text-muted">
      {text} Based on {lookbackYears} years of historical price data as of {dataAsOf}.
    </p>
  );
}
