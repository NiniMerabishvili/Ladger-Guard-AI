import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { METRICS_QUERY_KEY } from "./useMetrics";
import type { ReviewAction, Transaction } from "../types";

export const REVIEW_QUEUE_KEY = ["transactions", "pending_review"] as const;

interface ReviewVariables {
  txId: string;
  action: ReviewAction;
  matchedTransactionId?: string;
}

export function useReviewQueue() {
  const queryClient = useQueryClient();

  const queueQuery = useQuery({
    queryKey: REVIEW_QUEUE_KEY,
    queryFn: () => api.getTransactions({ status: "pending_review" }),
  });

  const reviewMutation = useMutation({
    mutationFn: ({ txId, action, matchedTransactionId }: ReviewVariables) =>
      api.review(txId, {
        decision: action,
        matched_transaction_id: matchedTransactionId,
      }),
    onMutate: async (variables) => {
      await queryClient.cancelQueries({ queryKey: REVIEW_QUEUE_KEY });
      const previous = queryClient.getQueryData<Transaction[]>(REVIEW_QUEUE_KEY);
      queryClient.setQueryData<Transaction[]>(
        REVIEW_QUEUE_KEY,
        (current) => current?.filter((item) => item.id !== variables.txId) ?? [],
      );
      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(REVIEW_QUEUE_KEY, context.previous);
      }
    },
    onSettled: (_data, _error, variables) => {
      void queryClient.invalidateQueries({ queryKey: METRICS_QUERY_KEY });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: ["decisions", variables.txId] });
    },
  });

  return { queueQuery, reviewMutation };
}
