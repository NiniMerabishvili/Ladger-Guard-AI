import {
  confidenceTone,
  explanationFrom,
  formatDate,
  methodLabel,
  riskFactorsFrom,
} from "../lib/format";
import { badges } from "../lib/ui";
import type { Decision } from "../types";

interface AuditTrailTimelineProps {
  decisions: Decision[];
}

export function AuditTrailTimeline({ decisions }: AuditTrailTimelineProps) {
  if (decisions.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-line px-9 py-9 text-muted">
        No decisions have been recorded for this transaction yet.
      </p>
    );
  }

  return (
    <ol className="m-0 grid list-none p-0">
      {decisions.map((item) => {
        const tone = confidenceTone(item.confidence);
        const factors = riskFactorsFrom(item.reasoning);
        return (
          <li
            key={item.id}
            className="relative pb-[22px] pl-[22px] last:pb-0 before:absolute before:top-2 before:bottom-0 before:left-[5px] before:w-px before:bg-line last:before:hidden after:absolute after:top-2 after:left-0 after:size-[11px] after:rounded-full after:bg-mint after:shadow-[0_0_0_4px_rgb(62_224_178_/_14%)]"
          >
            <strong>
              {item.decision.replaceAll("_", " ")} · {methodLabel(item.method)}
            </strong>
            <p className="text-sm text-muted">
              {formatDate(item.created_at)}
              {item.reviewed_by ? ` · ${item.reviewed_by}` : ""}
              {item.model_used ? ` · ${item.model_used}` : ""}
            </p>
            <div className="my-2 flex flex-wrap gap-2">
              <span className={badges[tone]}>confidence {item.confidence.toFixed(2)}</span>
              {factors.map((factor) => (
                <span key={factor} className={badges.low}>
                  {factor.replaceAll("_", " ")}
                </span>
              ))}
            </div>
            <p className="m-0 text-[#c9d4e0]">{explanationFrom(item.reasoning)}</p>
          </li>
        );
      })}
    </ol>
  );
}
