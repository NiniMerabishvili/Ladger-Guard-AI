import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useActiveProject } from "../context/ProjectContext";
import {
  btn,
  btnDanger,
  btnPrimary,
  pageHeader,
  pageLead,
  pageTitle,
  panel,
  panelError,
  surface,
} from "../lib/ui";

import { PROJECTS_QUERY_KEY } from "../lib/queryKeys";

function formatWhen(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ProjectsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { activeProjectId, setActiveProjectId } = useActiveProject();
  const [name, setName] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const projectsQuery = useQuery({
    queryKey: PROJECTS_QUERY_KEY,
    queryFn: () => api.listProjects(),
  });

  const createMutation = useMutation({
    mutationFn: () => api.createProject(name.trim() || undefined),
    onSuccess: (project) => {
      setName("");
      setActiveProjectId(project.id);
      void queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
      navigate("/upload");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (projectId: string) => api.deleteProject(projectId),
    onSuccess: (_data, projectId) => {
      setDeletingId(null);
      if (activeProjectId === projectId) {
        setActiveProjectId(null);
      }
      try {
        sessionStorage.removeItem(`ledger-guard:last-upload-run:${projectId}`);
      } catch {
        // ignore
      }
      void queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
      void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["upload-workspace", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["metrics"] });
      void queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
    onError: () => {
      setDeletingId(null);
    },
  });

  return (
    <main>
      <div className={pageHeader}>
        <div>
          <h2 className={pageTitle}>Projects</h2>
          <p className={pageLead}>
            Each upload run is saved as a project. Create a new one to clear the upload page and start
            fresh — older summaries stay here.
          </p>
        </div>
      </div>

      <section className={`${surface} mb-6 grid gap-3 p-5`}>
        <h3 className="m-0 text-base font-semibold">Create project</h3>
        <p className="m-0 text-sm text-muted">
          Opens a blank Upload & run workspace for this project. Previous projects stay in the list.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <input
            className="min-w-[220px] flex-1 rounded-[10px] border border-line bg-ink px-3 py-2 text-ink-text"
            placeholder="Optional name (e.g. March bank close)"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <button
            type="button"
            className={btnPrimary}
            disabled={createMutation.isPending}
            onClick={() => createMutation.mutate()}
          >
            {createMutation.isPending ? "Creating…" : "Create project"}
          </button>
        </div>
        {createMutation.isError ? (
          <p className={panelError}>{createMutation.error.message}</p>
        ) : null}
        {deleteMutation.isError ? (
          <p className={`${panelError} mt-3`}>{deleteMutation.error.message}</p>
        ) : null}
      </section>

      {projectsQuery.isError ? (
        <p className={panelError}>Could not load projects. Is the API running?</p>
      ) : null}
      {projectsQuery.isPending ? <p className={panel}>Loading projects…</p> : null}
      {projectsQuery.data?.length === 0 ? (
        <p className={panel}>No projects yet. Create one to begin.</p>
      ) : null}

      {projectsQuery.data && projectsQuery.data.length > 0 ? (
        <div className="grid gap-4">
          {projectsQuery.data.map((project) => {
            const isActive = project.id === activeProjectId;
            return (
              <article key={project.id} className={`${surface} grid gap-3 p-5`}>
                <header className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="m-0 text-[1.05rem]">{project.name}</h3>
                    <p className="mt-1 mb-0 text-sm text-muted">
                      {formatWhen(project.updated_at || project.created_at)} · {project.status}
                      {isActive ? " · active" : ""}
                    </p>
                    {(project.bank_filename || project.ledger_filename) && (
                      <p className="mt-1 mb-0 font-mono text-xs text-muted">
                        {[project.bank_filename, project.ledger_filename].filter(Boolean).join(" · ")}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className={btnPrimary}
                      onClick={() => {
                        setActiveProjectId(project.id);
                        navigate("/upload");
                      }}
                    >
                      Open upload
                    </button>
                    <Link className={btn} to="/" onClick={() => setActiveProjectId(project.id)}>
                      Dashboard
                    </Link>
                    <Link className={btn} to="/review" onClick={() => setActiveProjectId(project.id)}>
                      Review
                    </Link>
                    <button
                      type="button"
                      className={btnDanger}
                      disabled={deleteMutation.isPending}
                      onClick={() => {
                        const ok = window.confirm(
                          `Delete “${project.name}”? This removes its uploads, matches, and review items permanently.`,
                        );
                        if (!ok) return;
                        setDeletingId(project.id);
                        deleteMutation.mutate(project.id);
                      }}
                    >
                      {deletingId === project.id && deleteMutation.isPending
                        ? "Deleting…"
                        : "Delete"}
                    </button>
                  </div>
                </header>
                <div className="grid gap-2 sm:grid-cols-4">
                  <p className="m-0 text-sm text-muted">
                    Total{" "}
                    <span className="font-mono text-ink-text">{project.total_transactions}</span>
                  </p>
                  <p className="m-0 text-sm text-muted">
                    Matched <span className="font-mono text-ink-text">{project.matched}</span>
                  </p>
                  <p className="m-0 text-sm text-muted">
                    Pending{" "}
                    <span className="font-mono text-ink-text">{project.pending_review}</span>
                  </p>
                  <p className="m-0 text-sm text-muted">
                    Flagged <span className="font-mono text-ink-text">{project.flagged}</span>
                  </p>
                </div>
              </article>
            );
          })}
        </div>
      ) : null}
    </main>
  );
}
