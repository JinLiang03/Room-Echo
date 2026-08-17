interface Props {
  values: number[];
  width?: number;
  height?: number;
  stroke?: string;
  ariaLabel: string;
}

export function Sparkline({
  values,
  width = 220,
  height = 48,
  stroke = "var(--accent)",
  ariaLabel,
}: Props) {
  if (values.length === 0) {
    return (
      <svg
        className="sparkline"
        width={width}
        height={height}
        role="img"
        aria-label={ariaLabel}
      >
        <text x={width / 2} y={height / 2} textAnchor="middle" className="sparkline-empty">
          无数据
        </text>
      </svg>
    );
  }
  const normalized = values.map((value) =>
    Number.isFinite(value) ? Math.min(1, Math.max(0, value)) : 0,
  );
  const points = normalized
    .map((value, index) => {
      const x =
        normalized.length === 1
          ? width / 2
          : (index / (normalized.length - 1)) * width;
      const y = height - value * (height - 6) - 3;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      className="sparkline"
      width={width}
      height={height}
      role="img"
      aria-label={ariaLabel}
      aria-hidden={false}
    >
      <polyline
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        points={points}
      />
      {normalized.length === 1 && (
        <circle
          cx={width / 2}
          cy={height - normalized[0] * (height - 6) - 3}
          r={2.5}
          fill={stroke}
        />
      )}
    </svg>
  );
}
