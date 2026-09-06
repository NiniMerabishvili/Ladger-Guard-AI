import { MethodBreakdownChart } from "../components/MethodBreakdownChart";
import { MetricsCards } from "../components/MetricsCards";
import { useMetrics } from "../hooks/useMetrics";
import { btn, pageHeader, pageLead, pageTitle, panel, panelError } from "../lib/ui";

export function Dashboard() {
  const metricsQuery = useMetrics();

  return (
    <main>
      <div className={pageHeader}>
        <div>
          <h2 className={pageTitle}>Dashboard</h2>
          <p className={pageLead}>
            How much of the bank feed auto-matched, what still needs a person, and the running
            mock cost of embeddings plus LLM calls. Metrics refresh every 30 seconds.
          </p>
        </div>
        <button
          type="button"
          className={btn}
          onClick={() => void metricsQuery.refetch()}
          disabled={metricsQuery.isFetching}
        >
          {metricsQuery.isFetching ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {metricsQuery.isError ? (
        <p className={panelError}>Could not load metrics. Start the API on port 8000, then refresh.</p>
      ) : null}
      {metricsQuery.isPending ? <p className={panel}>Loading metrics…</p> : null}
      {metricsQuery.data ? (
        <>
          <MetricsCards metrics={metricsQuery.data} />
          <p className="mb-4 text-sm text-muted">{metricsQuery.data.labor_savings_note}</p>
          <MethodBreakdownChart breakdown={metricsQuery.data.method_breakdown} />
        </>
      ) : null}
    </main>
  );
}
