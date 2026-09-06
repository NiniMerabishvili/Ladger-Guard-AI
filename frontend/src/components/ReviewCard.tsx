import { useState } from "react";
import { Link } from "react-router-dom";
import {
  confidenceTone,
  explanationFrom,
  formatAmount,
  formatDate,
  methodLabel,
  riskFactorsFrom,
} from "../lib/format";
import { badges, btn, btnDanger, btnPrimary, surface } from "../lib/ui";
import type { ReviewAction, Transaction } from "../types";

interface ReviewCardProps {
  transaction: Transaction;
  busy?: boolean;
  onReview: (txId: string, action: ReviewAction, matchedTransactionId?: string) => void;
}

export function ReviewCard({ transaction, busy = false, onReview }: ReviewCardProps) {
  const [ledgerId, setLedgerId] = useState("");
  const decision = transaction.latest_decision;
  const tone = confidenceTone(decision?.confidence ?? 0);
  const factors = riskFactorsFrom(decision?.reasoning ?? null);
  const sourceBadge = transaction.source === "ledger" ? badges.ledger : badges.bank;

  return (
    <article className={`${surface} grid gap-4 p-5`}>
      <header className="flex items-start justify-between gap-4">
        <div>
          <h3 className="mb-1.5 text-[1.05rem]">{transaction.description}</h3>
          <p className="text-sm text-muted">
            {formatAmount(transaction.amount, transaction.currency)} · {formatDate(transaction.date)}
            {transaction.counterparty ? ` · ${transaction.counterparty}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className={sourceBadge}>{transaction.source}</span>
          <span className={badges[tone]}>
            confidence {decision ? decision.confidence.toFixed(2) : "—"}
          </span>
          {decision ? <span className={badges.neutral}>{methodLabel(decision.method)}</span> : null}
        </div>
      </header>

      <p className="m-0 text-[#c9d4e0]">{explanationFrom(decision?.reasoning ?? null)}</p>

      {factors.length > 0 ? (
        <div className="flex flex-wrap gap-2" aria-label="Risk factors">
          {factors.map((factor) => (
            <span key={factor} className={badges.low}>
              {factor.replaceAll("_", " ")}
            </span>
          ))}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className={btnPrimary}
          disabled={busy}
          onClick={() => onReview(transaction.id, "approve")}
        >
          Approve
        </button>
        <button
          type="button"
          className={btnDanger}
          disabled={busy}
          onClick={() => onReview(transaction.id, "reject")}
        >
          Reject
        </button>
        <div className="flex min-w-[240px] flex-1 gap-2">
          <input
            className="min-w-[180px] flex-1 rounded-[10px] border border-line bg-[#0d141c] px-2.5 py-2 text-ink-text"
            value={ledgerId}
            onChange={(event) => setLedgerId(event.target.value)}
            placeholder="Ledger transaction UUID"
            aria-label="Ledger transaction id for manual match"
            disabled={busy}
          />
          <button
            type="button"
            className={btn}
            disabled={busy || !ledgerId.trim()}
            onClick={() => onReview(transaction.id, "manual_match", ledgerId.trim())}
          >
            Manual match
          </button>
        </div>
        <Link className={btn} to={`/transactions/${transaction.id}`}>
          Audit trail
        </Link>
      </div>
    </article>
  );
}
