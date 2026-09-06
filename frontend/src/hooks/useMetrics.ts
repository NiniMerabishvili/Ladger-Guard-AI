import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useActiveProject } from "../context/ProjectContext";
import { METRICS_QUERY_KEY } from "../lib/queryKeys";

export { METRICS_QUERY_KEY };

export function useMetrics() {
  const { activeProjectId } = useActiveProject();
  return useQuery({
    queryKey: [...METRICS_QUERY_KEY, activeProjectId],
    queryFn: () => api.getMetrics(activeProjectId ?? undefined),
    enabled: Boolean(activeProjectId),
    refetchInterval: 30_000,
  });
}
