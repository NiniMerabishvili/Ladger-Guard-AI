import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { AuditTrailTimeline } from "../components/AuditTrailTimeline";
import { formatAmount, formatDate } from "../lib/format";
import { badges, btn, pageHeader, pageLead, pageTitle, panel, panelError, surface } from "../lib/ui";

export function TransactionDetail() {
  const { txId = "" } = useParams();
  const txQuery = useQuery({
    queryKey: ["transactions", txId],
    queryFn: () => api.getTransaction(txId),
    enabled: Boolean(txId),
  });
  const trailQuery = useQuery({
    queryKey: ["decisions", txId],
    queryFn: () => api.getDecisions(txId),
    enabled: Boolean(txId),
  });

  const transaction = txQuery.data;
  const sourceBadge = transaction?.source === "ledger" ? badges.ledger : badges.bank;

  return (
    <main>
      <div className={pageHeader}>
        <div>
          <h2 className={pageTitle}>Transaction detail</h2>
          <p className={pageLead}>
            Every match, flag, and human override for this line — oldest first, never overwritten.
          </p>
        </div>
        <Link className={btn} to="/review">
          Back to queue
        </Link>
      </div>

      {txQuery.isError ? (
        <p className={panelError}>Transaction not found, or the API is not reachable.</p>
      ) : null}
      {txQuery.isPending ? <p className={panel}>Loading transaction…</p> : null}

      {transaction ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
          <section className={`${surface} p-[22px]`}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="mb-1.5 text-[1.05rem]">{transaction.description}</h3>
                <p className="font-mono text-sm text-muted">{transaction.id}</p>
              </div>
              <span className={sourceBadge}>{transaction.source}</span>
            </div>
            <dl className="mt-4 grid grid-cols-[140px_1fr] gap-x-3 gap-y-2">
              <dt className="text-muted">Amount</dt>
              <dd className="m-0">{formatAmount(transaction.amount, transaction.currency)}</dd>
              <dt className="text-muted">Date</dt>
              <dd className="m-0">{formatDate(transaction.date)}</dd>
              <dt className="text-muted">Counterparty</dt>
              <dd className="m-0">{transaction.counterparty ?? "—"}</dd>
              <dt className="text-muted">Status</dt>
              <dd className="m-0">{transaction.status.replaceAll("_", " ")}</dd>
            </dl>
          </section>
          <section className={`${surface} p-[22px]`}>
            <h3 className="mb-4 text-[1.05rem]">Audit trail</h3>
            {trailQuery.isPending ? <p className={panel}>Loading history…</p> : null}
            {trailQuery.isError ? <p className={panelError}>Could not load the audit trail.</p> : null}
            {trailQuery.data ? <AuditTrailTimeline decisions={trailQuery.data} /> : null}
          </section>
        </div>
      ) : null}
    </main>
  );
}
