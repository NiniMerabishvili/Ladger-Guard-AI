import type {
  Decision,
  HealthStatus,
  Metrics,
  ReviewRequest,
  Transaction,
  TransactionQuery,
} from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

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
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
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
  getMetrics: () => request<Metrics>("/metrics"),
  getTransactions: (query: TransactionQuery | string = {}) => {
    const filters = typeof query === "string" ? { status: query } : query;
    return request<Transaction[]>(
      `/transactions${queryString({
        status: filters.status,
        source: filters.source,
        date_from: filters.date_from,
        date_to: filters.date_to,
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
  ingest: () => request<Record<string, string>>("/ingest", { method: "POST" }),
  runReconciliation: () =>
    request<Record<string, string>>("/reconcile/run", { method: "POST" }),
};
