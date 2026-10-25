/** Score out of 100: green at 80 or more, amber 50–79, red below 50, "—" when inconclusive. */
export default function ScoreRing({ score, size = 112 }: { score: number | null; size?: number }) {
  const stroke = size / 10;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const color = score === null ? "#6b7280" : score >= 80 ? "#15803d" : score >= 50 ? "#b45309" : "#b91c1c";
  const label = score === null ? "No score: inconclusive" : `Score ${score} out of 100`;
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label} className="shrink-0">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e5e7eb" strokeWidth={stroke} />
      {score !== null && (
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${(score / 100) * circumference} ${circumference}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      )}
      <text
        x="50%"
        y="50%"
        dominantBaseline="central"
        textAnchor="middle"
        fontSize={size / 3.4}
        fontWeight={700}
        fill={score === null ? "#374151" : color}
      >
        {score === null ? "—" : score}
      </text>
    </svg>
  );
}
