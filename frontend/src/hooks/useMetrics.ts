import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export const METRICS_QUERY_KEY = ["metrics"] as const;

export function useMetrics() {
  return useQuery({
    queryKey: METRICS_QUERY_KEY,
    queryFn: api.getMetrics,
    refetchInterval: 30_000,
  });
}
