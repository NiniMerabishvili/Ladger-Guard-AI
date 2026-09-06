import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useActiveProject } from "../context/ProjectContext";
import { METRICS_QUERY_KEY, REVIEW_QUEUE_KEY } from "../lib/queryKeys";
import type { ReviewAction, Transaction } from "../types";

export { REVIEW_QUEUE_KEY };

interface ReviewVariables {
  txId: string;
  action: ReviewAction;
  matchedTransactionId?: string;
}

export function useReviewQueue() {
  const queryClient = useQueryClient();
  const { activeProjectId } = useActiveProject();
  const queueKey = [...REVIEW_QUEUE_KEY, activeProjectId] as const;

  const queueQuery = useQuery({
    queryKey: queueKey,
    queryFn: () =>
      api.getTransactions({
        status: "pending_review",
        project_id: activeProjectId ?? undefined,
      }),
    enabled: Boolean(activeProjectId),
  });

  const reviewMutation = useMutation({
    mutationFn: ({ txId, action, matchedTransactionId }: ReviewVariables) =>
      api.review(txId, {
        decision: action,
        matched_transaction_id: matchedTransactionId,
      }),
    onMutate: async (variables) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<Transaction[]>(queueKey);
      queryClient.setQueryData<Transaction[]>(
        queueKey,
        (current) => current?.filter((item) => item.id !== variables.txId) ?? [],
      );
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queueKey, context.previous);
      }
    },
    onSettled: (_data, _error, variables) => {
      void queryClient.invalidateQueries({ queryKey: METRICS_QUERY_KEY });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: ["decisions", variables.txId] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
  });

  return { queueQuery, reviewMutation };
}
