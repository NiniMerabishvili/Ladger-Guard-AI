/** Mirrors backend Pydantic schemas in app/schemas. */

export type DecisionStatus = "matched" | "flagged" | "pending_review";
export type MatchMethod = "exact_rule" | "semantic_match" | "llm_agent" | "human_override";
export type TransactionSource = "bank" | "ledger";
export type TransactionStatus = DecisionStatus | "unmatched";
export type ReviewAction = "approve" | "reject" | "manual_match";
export type ConfidenceTone = "high" | "medium" | "low";

/** TransactionCreate */
export interface TransactionCreate {
  source: TransactionSource;
  date: string;
  amount: number;
  currency: string;
  description: string;
  counterparty: string | null;
}

/** TransactionRead */
export interface TransactionRead extends TransactionCreate {
  id: string;
  status: TransactionStatus | string;
}

/** TransactionListItem */
export interface Transaction extends TransactionRead {
  latest_decision: Decision | null;
}

/** DecisionRead */
export interface Decision {
  id: string;
  transaction_id: string;
  matched_transaction_id: string | null;
  decision: DecisionStatus | string;
  method: MatchMethod | string;
  confidence: number;
  reasoning: Record<string, unknown> | null;
  model_used: string | null;
  reviewed_by: string | null;
  matching_run_id: string | null;
  created_at: string;
}

/** ReviewAction (request body) */
export interface ReviewRequest {
  decision: ReviewAction;
  reviewed_by?: string;
  matched_transaction_id?: string;
}

export interface TransactionQuery {
  status?: string;
  source?: TransactionSource;
  date_from?: string;
  date_to?: string;
}

/** MethodBreakdown */
export interface MethodBreakdown {
  exact_rule: number;
  semantic_match: number;
  llm_agent: number;
  human_override: number;
}

/** MetricsRead */
export interface Metrics {
  total_transactions: number;
  auto_matched_pct: number;
  pending_review_pct: number;
  flagged_pct: number;
  method_breakdown: MethodBreakdown;
  estimated_llm_cost_usd: number;
  estimated_manual_labor_savings_usd: number;
  labor_savings_note: string;
  false_positive_rate: number | null;
}

export interface HealthStatus {
  status: string;
}
