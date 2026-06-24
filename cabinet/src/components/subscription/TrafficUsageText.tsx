import { formatTraffic } from '../../utils/formatTraffic';

interface TrafficUsageTextProps {
  usedGb: number;
  limitGb?: number;
  isUnlimited?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

/** LTR-isolated traffic amounts for RTL layouts (e.g. 0 MB / 10.0 GB). */
export function TrafficUsageText({
  usedGb,
  limitGb,
  isUnlimited = false,
  className = '',
  style,
}: TrafficUsageTextProps) {
  const text =
    isUnlimited || limitGb === undefined
      ? formatTraffic(usedGb)
      : `${formatTraffic(usedGb)} / ${formatTraffic(limitGb)}`;

  return (
    <span
      dir="ltr"
      className={`inline-block font-mono tabular-nums [unicode-bidi:isolate] ${className}`}
      style={style}
    >
      {text}
    </span>
  );
}
