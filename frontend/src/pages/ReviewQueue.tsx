import { Link } from "react-router-dom";
import { ReviewCard } from "../components/ReviewCard";
import { useActiveProject } from "../context/ProjectContext";
import { useReviewQueue } from "../hooks/useReviewQueue";
import { btn, pageHeader, pageLead, pageTitle, panel, panelError } from "../lib/ui";

export function ReviewQueue() {
  const { activeProjectId } = useActiveProject();
  const { queueQuery, reviewMutation } = useReviewQueue();

  return (
    <main>
      <div className={pageHeader}>
        <div>
          <h2 className={pageTitle}>Review queue</h2>
          <p className={pageLead}>
            Pending-review lines for the active project. Approve, reject, or point at a ledger row.
          </p>
        </div>
        <button
          type="button"
          className={btn}
          onClick={() => void queueQuery.refetch()}
          disabled={!activeProjectId || queueQuery.isFetching}
        >
          {queueQuery.isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {!activeProjectId ? (
        <p className={panel}>
          No active project.{" "}
          <Link className="text-mint hover:underline" to="/projects">
            Create or open a project
          </Link>
          .
        </p>
      ) : null}

      {activeProjectId && queueQuery.isError ? (
        <p className={panelError}>Could not load the review queue. Check that the API is running.</p>
      ) : null}
      {activeProjectId && queueQuery.isPending ? (
        <p className={panel}>Loading review queue…</p>
      ) : null}
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
