import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { methodLabel } from "../lib/format";
import { surface } from "../lib/ui";
import type { MethodBreakdown } from "../types";

const COLORS: Record<string, string> = {
  exact_rule: "#3ee0b2",
  semantic_match: "#7eb0ff",
  llm_agent: "#e8c36a",
  human_override: "#c9a6ff",
};

interface MethodBreakdownChartProps {
  breakdown: MethodBreakdown;
}

export function MethodBreakdownChart({ breakdown }: MethodBreakdownChartProps) {
  const data = (Object.entries(breakdown) as [keyof MethodBreakdown, number][]).map(
    ([method, count]) => ({
      method,
      label: methodLabel(method),
      count,
    }),
  );
  const total = data.reduce((sum, row) => sum + row.count, 0);

  if (total === 0) {
    return (
      <section className={`${surface} p-5`}>
        <h3 className="mb-1 text-base">Method breakdown</h3>
        <p className="m-0 text-muted">
          No decisions yet. Run reconciliation to see exact vs semantic vs agent vs human.
        </p>
      </section>
    );
  }

  return (
    <section className={`${surface} p-5`} aria-label="Decision method breakdown">
      <h3 className="mb-1 text-base">Method breakdown</h3>
      <p className="mb-4 text-muted">
        How each posted decision was made — rules first, then embeddings, then the agent.
      </p>
      <div className="grid min-h-[260px] grid-cols-1 gap-3 lg:grid-cols-[220px_1fr]">
        <ResponsiveContainer width="100%" height={260}>
          <PieChart>
            <Pie data={data} dataKey="count" nameKey="label" innerRadius={56} outerRadius={86} paddingAngle={3}>
              {data.map((row) => (
                <Cell key={row.method} fill={COLORS[row.method]} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{ background: "#121923", border: "1px solid #263140", borderRadius: 8 }}
            />
          </PieChart>
        </ResponsiveContainer>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
            <CartesianGrid stroke="#263140" vertical={false} />
            <XAxis dataKey="label" stroke="#8d99ab" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} stroke="#8d99ab" tick={{ fontSize: 12 }} />
            <Tooltip
              contentStyle={{ background: "#121923", border: "1px solid #263140", borderRadius: 8 }}
            />
            <Bar dataKey="count" radius={[6, 6, 0, 0]}>
              {data.map((row) => (
                <Cell key={row.method} fill={COLORS[row.method]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
