import type {
  Decision,
  HealthStatus,
  IngestResult,
  Metrics,
  Project,
  ReconcileResult,
  ReviewRequest,
  Transaction,
  TransactionQuery,
} from "../types";

const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function detailMessage(payload: unknown, fallback: string): string {
  if (typeof payload === "object" && payload && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          typeof item === "object" && item && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : JSON.stringify(item),
        )
        .join("; ");
    }
  }
  return fallback;
}

function queryString(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value);
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const isForm = typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (!isForm && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });
  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    throw new ApiError(
      response.status,
      detailMessage(payload, `${response.status} ${response.statusText}`),
    );
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthStatus>("/health"),
  listProjects: () => request<Project[]>("/projects"),
  createProject: (name?: string) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify({ name: name ?? null }),
    }),
  getProject: (projectId: string) => request<Project>(`/projects/${projectId}`),
  deleteProject: (projectId: string) =>
    request<void>(`/projects/${projectId}`, { method: "DELETE" }),
  getMetrics: (projectId?: string) =>
    request<Metrics>(`/metrics${queryString({ project_id: projectId })}`),
  getTransactions: (query: TransactionQuery | string = {}) => {
    const filters = typeof query === "string" ? { status: query } : query;
    return request<Transaction[]>(
      `/transactions${queryString({
        status: filters.status,
        source: filters.source,
        date_from: filters.date_from,
        date_to: filters.date_to,
        project_id: filters.project_id,
      })}`,
    );
  },
  getTransaction: (txId: string) => request<Transaction>(`/transactions/${txId}`),
  getDecisions: (txId: string) => request<Decision[]>(`/decisions/${txId}`),
  review: (txId: string, body: ReviewRequest) =>
    request<Decision>(`/review/${txId}`, {
      method: "POST",
      body: JSON.stringify({ reviewed_by: "reviewer", ...body }),
    }),
  ingestUploads: (bankFile: File, ledgerFile: File, projectId: string) => {
    const form = new FormData();
    form.append("bank_file", bankFile);
    form.append("ledger_file", ledgerFile);
    form.append("project_id", projectId);
    return request<IngestResult>("/ingest", { method: "POST", body: form });
  },
  runReconciliation: (projectId: string) =>
    request<ReconcileResult>(
      `/reconcile/run${queryString({ project_id: projectId })}`,
      { method: "POST" },
    ),
};
