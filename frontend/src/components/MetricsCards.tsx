import { formatPct, formatUsd } from "../lib/format";
import { surface } from "../lib/ui";
import type { Metrics } from "../types";

interface MetricsCardsProps {
  metrics: Metrics;
}

export function MetricsCards({ metrics }: MetricsCardsProps) {
  const items = [
    {
      label: "Auto-matched",
      value: formatPct(metrics.auto_matched_pct),
      hint: `${metrics.total_transactions} transactions in the book`,
    },
    {
      label: "Needs review",
      value: formatPct(metrics.pending_review_pct),
      hint: "Confidence below 0.7 stays with a human",
    },
    {
      label: "Flagged",
      value: formatPct(metrics.flagged_pct),
      hint:
        metrics.false_positive_rate == null
          ? "False-positive rate not measured yet"
          : `False-positive rate ${formatPct(metrics.false_positive_rate * 100)}`,
    },
    {
      label: "LLM spend",
      value: formatUsd(metrics.estimated_llm_cost_usd),
      hint: `Labor savings ${formatUsd(metrics.estimated_manual_labor_savings_usd)} (assumption)`,
    },
  ];

  return (
    <section className="mb-5 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4" aria-label="Reconciliation metrics">
      {items.map((item) => (
        <article key={item.label} className={`${surface} px-[18px] pt-[18px] pb-4`}>
          <span className="block text-xs tracking-[0.06em] text-muted uppercase">{item.label}</span>
          <strong className="mt-2.5 block font-mono text-[1.7rem] font-semibold">{item.value}</strong>
          <small className="mt-2 block text-xs text-muted">{item.hint}</small>
        </article>
      ))}
    </section>
  );
}
