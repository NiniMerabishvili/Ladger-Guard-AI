import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { MethodBreakdownChart } from "../components/MethodBreakdownChart";
import { MetricsCards } from "../components/MetricsCards";
import { ReviewCard } from "../components/ReviewCard";
import { useActiveProject } from "../context/ProjectContext";
import { useReviewQueue } from "../hooks/useReviewQueue";
import { METRICS_QUERY_KEY, PROJECTS_QUERY_KEY, REVIEW_QUEUE_KEY } from "../lib/queryKeys";
import { formatAmount, formatDate, methodLabel } from "../lib/format";
import {
  badges,
  btn,
  btnPrimary,
  pageHeader,
  pageLead,
  pageTitle,
  panel,
  panelError,
  panelSuccess,
  surface,
} from "../lib/ui";
import type { IngestResult, Metrics, ReconcileResult, Transaction } from "../types";

function runStorageKey(projectId: string) {
  return `ledger-guard:last-upload-run:${projectId}`;
}

function FilePicker({
  label,
  hint,
  file,
  onChange,
}: {
  label: string;
  hint: string;
  file: File | null;
  onChange: (file: File | null) => void;
}) {
  return (
    <label className={`${surface} flex cursor-pointer flex-col gap-2 p-5`}>
      <span className="text-sm tracking-[0.06em] text-muted uppercase">{label}</span>
      <span className="text-sm text-muted">{hint}</span>
      <input
        type="file"
        accept=".csv,text/csv"
        className="mt-2 block w-full text-sm text-ink-text file:mr-3 file:rounded-[10px] file:border-0 file:bg-mint/14 file:px-3 file:py-2 file:font-medium file:text-mint"
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
      {file ? (
        <span className="font-mono text-sm text-mint">
          {file.name} · {(file.size / 1024).toFixed(1)} KB
        </span>
      ) : (
        <span className="text-sm text-muted">No file selected</span>
      )}
    </label>
  );
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className={`${surface} p-4`}>
      <p className="m-0 text-xs tracking-[0.06em] text-muted uppercase">{label}</p>
      <p className="mt-2 mb-0 font-mono text-2xl text-ink-text">{value}</p>
    </div>
  );
}

interface RunPayload {
  ingested: IngestResult;
  reconciled: ReconcileResult;
  summary: Metrics;
  pending: Transaction[];
  matched: Transaction[];
  flagged: Transaction[];
}

async function loadWorkspaceSnapshot(projectId: string) {
  const [summary, pending, matched, flagged] = await Promise.all([
    api.getMetrics(projectId),
    api.getTransactions({ status: "pending_review", source: "bank", project_id: projectId }),
    api.getTransactions({ status: "matched", source: "bank", project_id: projectId }),
    api.getTransactions({ status: "flagged", source: "bank", project_id: projectId }),
  ]);
  return { summary, pending, matched, flagged };
}

function readStoredRun(projectId: string): RunPayload | null {
  try {
    const raw = sessionStorage.getItem(runStorageKey(projectId));
    if (!raw) return null;
    return JSON.parse(raw) as RunPayload;
  } catch {
    return null;
  }
}

function writeStoredRun(projectId: string, payload: RunPayload) {
  try {
    sessionStorage.setItem(runStorageKey(projectId), JSON.stringify(payload));
  } catch {
    // ignore
  }
}

function clearStoredRun(projectId: string) {
  try {
    sessionStorage.removeItem(runStorageKey(projectId));
  } catch {
    // ignore
  }
}

export function UploadRun() {
  const queryClient = useQueryClient();
  const { activeProjectId, setActiveProjectId } = useActiveProject();
  const { reviewMutation } = useReviewQueue();
  const resultsRef = useRef<HTMLDivElement | null>(null);
  const [bankFile, setBankFile] = useState<File | null>(null);
  const [ledgerFile, setLedgerFile] = useState<File | null>(null);
  const [run, setRun] = useState<RunPayload | null>(null);
  const [phase, setPhase] = useState<string | null>(null);

  const projectQuery = useQuery({
    queryKey: ["project", activeProjectId],
    queryFn: () => api.getProject(activeProjectId!),
    enabled: Boolean(activeProjectId),
  });

  useEffect(() => {
    if (!activeProjectId) {
      setRun(null);
      setBankFile(null);
      setLedgerFile(null);
      return;
    }
    setRun(readStoredRun(activeProjectId));
    setBankFile(null);
    setLedgerFile(null);
  }, [activeProjectId]);

  const workspaceQuery = useQuery({
    queryKey: ["upload-workspace", activeProjectId],
    queryFn: () => loadWorkspaceSnapshot(activeProjectId!),
    enabled: Boolean(activeProjectId),
  });

  useEffect(() => {
    if (!activeProjectId || !workspaceQuery.data) return;
    const { summary, pending, matched, flagged } = workspaceQuery.data;
    setRun((current) => {
      if (current) {
        return { ...current, summary, pending, matched, flagged };
      }
      if (summary.total_transactions === 0) return null;
      return {
        ingested: {
          bank_count: pending.length + matched.length + flagged.length,
          ledger_count: Math.max(
            0,
            summary.total_transactions - (pending.length + matched.length + flagged.length),
          ),
          total: summary.total_transactions,
          project_id: activeProjectId,
        },
        reconciled: {
          matching_run_id: "—",
          processed: pending.length + matched.length + flagged.length,
          skipped_resolved: 0,
          exact_rule: summary.method_breakdown.exact_rule,
          semantic_match: summary.method_breakdown.semantic_match,
          llm_agent: summary.method_breakdown.llm_agent,
          decisions_written:
            summary.method_breakdown.exact_rule +
            summary.method_breakdown.semantic_match +
            summary.method_breakdown.llm_agent +
            summary.method_breakdown.human_override,
          project_id: activeProjectId,
        },
        summary,
        pending,
        matched,
        flagged,
      };
    });
  }, [workspaceQuery.data, activeProjectId]);

  const newProjectMutation = useMutation({
    mutationFn: () => api.createProject(),
    onSuccess: (project) => {
      if (activeProjectId) clearStoredRun(activeProjectId);
      setActiveProjectId(project.id);
      setRun(null);
      setBankFile(null);
      setLedgerFile(null);
      setPhase(null);
      void queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
    },
  });

  const pipeline = useMutation({
    mutationFn: async (): Promise<RunPayload> => {
      if (!activeProjectId) {
        throw new Error("Create or open a project first.");
      }
      if (!bankFile || !ledgerFile) {
        throw new Error("Choose both the bank statement and the company ledger CSV.");
      }
      let ingested: IngestResult;
      try {
        setPhase("Uploading CSVs…");
        ingested = await api.ingestUploads(bankFile, ledgerFile, activeProjectId);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        throw new Error(`Ingest failed: ${message}`);
      }
      let reconciled: ReconcileResult;
      try {
        setPhase("Reconciling (exact → semantic → agent)…");
        reconciled = await api.runReconciliation(activeProjectId);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        throw new Error(`Reconcile failed (ingest OK): ${message}`);
      }
      setPhase("Loading results…");
      const snapshot = await loadWorkspaceSnapshot(activeProjectId);
      return { ingested, reconciled, ...snapshot };
    },
    onSuccess: (data) => {
      if (!activeProjectId) return;
      setRun(data);
      writeStoredRun(activeProjectId, data);
      setPhase(null);
      void queryClient.invalidateQueries({ queryKey: METRICS_QUERY_KEY });
      void queryClient.invalidateQueries({ queryKey: REVIEW_QUEUE_KEY });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
      void queryClient.invalidateQueries({ queryKey: ["upload-workspace"] });
      void queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
      void queryClient.invalidateQueries({ queryKey: ["project", activeProjectId] });
      requestAnimationFrame(() => {
        resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    },
    onError: () => {
      setPhase(null);
    },
  });

  const reviewBusyId =
    reviewMutation.isPending && reviewMutation.variables ? reviewMutation.variables.txId : null;

  if (!activeProjectId) {
    return (
      <main>
        <div className={pageHeader}>
          <div>
            <h2 className={pageTitle}>Upload & run</h2>
            <p className={pageLead}>
              Create a project first. Each project keeps its own uploads, matches, and summaries.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className={btnPrimary}
            disabled={newProjectMutation.isPending}
            onClick={() => newProjectMutation.mutate()}
          >
            {newProjectMutation.isPending ? "Creating…" : "Create project"}
          </button>
          <Link className={btn} to="/projects">
            Open projects
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main>
      <div className={pageHeader}>
        <div>
          <h2 className={pageTitle}>Upload & run</h2>
          <p className={pageLead}>
            Project:{" "}
            <span className="text-ink-text">{projectQuery.data?.name ?? activeProjectId}</span>.
            Upload CSVs, reconcile, and see results here. Use Upload new project to start clean
            without losing older work.
          </p>
        </div>
      </div>

      <div className="mb-5 flex flex-wrap gap-3">
        <button
          type="button"
          className={btn}
          disabled={newProjectMutation.isPending || pipeline.isPending}
          onClick={() => newProjectMutation.mutate()}
        >
          {newProjectMutation.isPending ? "Starting…" : "Upload new project"}
        </button>
        <Link className={btn} to="/projects">
          All projects
        </Link>
      </div>

      <div className="mb-5 grid gap-4 lg:grid-cols-2">
        <FilePicker
          label="Bank statement CSV"
          hint="Columns: transaction_id, date, amount, currency, description, counterparty"
          file={bankFile}
          onChange={setBankFile}
        />
        <FilePicker
          label="Company ledger CSV"
          hint="Same columns — internal books to match against the bank"
          file={ledgerFile}
          onChange={setLedgerFile}
        />
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <button
          type="button"
          className={btnPrimary}
          disabled={pipeline.isPending || !bankFile || !ledgerFile}
          onClick={() => pipeline.mutate()}
        >
          {pipeline.isPending ? phase ?? "Uploading & reconciling…" : "Upload & reconcile"}
        </button>
        <Link className={btn} to="/review">
          Open review queue
        </Link>
        <Link className={btn} to="/">
          Dashboard
        </Link>
      </div>

      {pipeline.isError ? (
        <p className={`${panelError} mb-5`}>{pipeline.error.message}</p>
      ) : null}

      {pipeline.isPending ? (
        <p className={`${panel} mb-5`}>
          {phase ?? "Working…"} Stay on this page — results appear below when finished.
        </p>
      ) : null}

      {!run && !pipeline.isPending ? (
        <p className={`${panel} mb-5`}>
          Choose both CSVs, then click Upload & reconcile. Totals, metrics, and pending-review items
          show on this page for the active project.
        </p>
      ) : null}

      {run ? (
        <div ref={resultsRef} className="grid gap-5">
          <p className={`${panelSuccess} mb-0`}>
            Results for this project —{" "}
            <span className="text-ink-text">
              {run.reconciled.decisions_written} decision
              {run.reconciled.decisions_written === 1 ? "" : "s"}
            </span>
            , {run.pending.length} pending review, {run.matched.length} matched.
          </p>

          <section>
            <h3 className="mb-3 text-base font-semibold">Run summary</h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile label="Bank rows ingested" value={run.ingested.bank_count} />
              <StatTile label="Ledger rows ingested" value={run.ingested.ledger_count} />
              <StatTile label="Exact matches" value={run.reconciled.exact_rule} />
              <StatTile label="Semantic matches" value={run.reconciled.semantic_match} />
              <StatTile label="Agent leftovers" value={run.reconciled.llm_agent} />
              <StatTile label="Pending review now" value={run.pending.length} />
              <StatTile label="Matched bank lines" value={run.matched.length} />
              <StatTile label="Flagged" value={run.flagged.length} />
            </div>
          </section>

          <section>
            <h3 className="mb-3 text-base font-semibold">Portfolio metrics</h3>
            <MetricsCards metrics={run.summary} />
            <p className="mb-4 text-sm text-muted">{run.summary.labor_savings_note}</p>
            <MethodBreakdownChart breakdown={run.summary.method_breakdown} />
          </section>

          <section>
            <div className="mb-3 flex items-end justify-between gap-3">
              <div>
                <h3 className="m-0 text-base font-semibold">Needs review</h3>
                <p className="mt-1 mb-0 text-sm text-muted">
                  Same items as the review queue (and ClickUp).
                </p>
              </div>
              <Link className={btn} to="/review">
                Full queue
              </Link>
            </div>
            {run.pending.length === 0 ? (
              <p className={panel}>Nothing pending — everything matched or cleared.</p>
            ) : (
              <div className="grid gap-4">
                {run.pending.map((transaction) => (
                  <ReviewCard
                    key={transaction.id}
                    transaction={transaction}
                    busy={reviewBusyId === transaction.id}
                    onReview={(txId, action, matchedTransactionId) => {
                      reviewMutation.mutate(
                        { txId, action, matchedTransactionId },
                        {
                          onSuccess: () => {
                            setRun((current) => {
                              if (!current || !activeProjectId) return current;
                              const next = {
                                ...current,
                                pending: current.pending.filter((row) => row.id !== txId),
                              };
                              writeStoredRun(activeProjectId, next);
                              return next;
                            });
                          },
                        },
                      );
                    }}
                  />
                ))}
              </div>
            )}
          </section>

          {run.matched.length > 0 ? (
            <section>
              <h3 className="mb-3 text-base font-semibold">Matched bank lines</h3>
              <div className={`${surface} divide-y divide-line overflow-hidden`}>
                {run.matched.slice(0, 25).map((tx) => (
                  <div
                    key={tx.id}
                    className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                  >
                    <div>
                      <p className="m-0 font-medium text-ink-text">{tx.description}</p>
                      <p className="m-0 text-sm text-muted">
                        {formatAmount(tx.amount, tx.currency)} · {formatDate(tx.date)}
                        {tx.counterparty ? ` · ${tx.counterparty}` : ""}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className={badges.high}>matched</span>
                      {tx.latest_decision ? (
                        <span className={badges.neutral}>
                          {methodLabel(tx.latest_decision.method)}
                        </span>
                      ) : null}
                      <Link
                        className="text-sm text-mint hover:underline"
                        to={`/transactions/${tx.id}`}
                      >
                        Detail
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      ) : null}
    </main>
  );
}
