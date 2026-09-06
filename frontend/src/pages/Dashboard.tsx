import { Link } from "react-router-dom";
import { MethodBreakdownChart } from "../components/MethodBreakdownChart";
import { MetricsCards } from "../components/MetricsCards";
import { useActiveProject } from "../context/ProjectContext";
import { useMetrics } from "../hooks/useMetrics";
import { btn, pageHeader, pageLead, pageTitle, panel, panelError } from "../lib/ui";

export function Dashboard() {
  const { activeProjectId } = useActiveProject();
  const metricsQuery = useMetrics();

  return (
    <main>
      <div className={pageHeader}>
        <div>
          <h2 className={pageTitle}>Dashboard</h2>
          <p className={pageLead}>
            Metrics for the active project. Switch projects from the Projects page.
          </p>
        </div>
        <button
          type="button"
          className={btn}
          onClick={() => void metricsQuery.refetch()}
          disabled={!activeProjectId || metricsQuery.isFetching}
        >
          {metricsQuery.isFetching ? "Refreshing…" : "Refresh"}
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

      {activeProjectId && metricsQuery.isError ? (
        <p className={panelError}>
          Could not load metrics
          {metricsQuery.error instanceof Error ? `: ${metricsQuery.error.message}` : ""}.
        </p>
      ) : null}
      {activeProjectId && metricsQuery.isPending ? <p className={panel}>Loading metrics…</p> : null}
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
