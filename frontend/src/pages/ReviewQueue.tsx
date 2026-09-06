import { ReviewCard } from "../components/ReviewCard";
import { useReviewQueue } from "../hooks/useReviewQueue";
import { btn, pageHeader, pageLead, pageTitle, panel, panelError } from "../lib/ui";

export function ReviewQueue() {
  const { queueQuery, reviewMutation } = useReviewQueue();

  return (
    <main>
      <div className={pageHeader}>
        <div>
          <h2 className={pageTitle}>Review queue</h2>
          <p className={pageLead}>
            These lines stayed below the 0.7 confidence line — like a $5,000 wire to a new vendor.
            Approve, reject, or point it at a ledger row yourself.
          </p>
        </div>
        <button
          type="button"
          className={btn}
          onClick={() => void queueQuery.refetch()}
          disabled={queueQuery.isFetching}
        >
          {queueQuery.isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {queueQuery.isError ? (
        <p className={panelError}>Could not load the review queue. Check that the API is running.</p>
      ) : null}
      {queueQuery.isPending ? <p className={panel}>Loading review queue…</p> : null}
      {reviewMutation.isError ? <p className={panelError}>{reviewMutation.error.message}</p> : null}
      {queueQuery.data?.length === 0 ? (
        <p className={panel}>Nothing pending. High-confidence matches never land here.</p>
      ) : null}
      {queueQuery.data && queueQuery.data.length > 0 ? (
        <div className="grid gap-4">
          {queueQuery.data.map((transaction) => (
            <ReviewCard
              key={transaction.id}
              transaction={transaction}
              busy={reviewMutation.isPending && reviewMutation.variables?.txId === transaction.id}
              onReview={(txId, action, matchedTransactionId) =>
                reviewMutation.mutate({ txId, action, matchedTransactionId })
              }
            />
          ))}
        </div>
      ) : null}
    </main>
  );
}
