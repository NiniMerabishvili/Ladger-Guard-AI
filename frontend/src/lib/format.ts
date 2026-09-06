import type { ConfidenceTone } from "../types";

export function confidenceTone(value: number): ConfidenceTone {
  if (value >= 0.9) return "high";
  if (value >= 0.7) return "medium";
  return "low";
}

export function formatPct(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function formatUsd(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(value);
}

export function formatAmount(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(amount);
}

export function formatDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  if (value.length <= 10) {
    return parsed.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      timeZone: "UTC",
    });
  }
  return parsed.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function methodLabel(method: string): string {
  return method.replaceAll("_", " ");
}

export function explanationFrom(reasoning: Record<string, unknown> | null): string {
  if (!reasoning) return "No explanation recorded.";
  for (const key of ["explanation", "reason", "action"]) {
    const value = reasoning[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return JSON.stringify(reasoning);
}

export function riskFactorsFrom(reasoning: Record<string, unknown> | null): string[] {
  const raw = reasoning?.risk_factors;
  if (!Array.isArray(raw)) return [];
  return raw.filter((item): item is string => typeof item === "string");
}
