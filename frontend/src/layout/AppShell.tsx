import { NavLink, Outlet } from "react-router-dom";
import { cx } from "../lib/ui";

const navClass = ({ isActive }: { isActive: boolean }) =>
  cx(
    "block rounded-[10px] px-3 py-2.5 text-muted hover:bg-hover hover:text-ink-text",
    isActive && "bg-hover text-ink-text shadow-[inset_2px_0_0_#3ee0b2]",
  );

export function AppShell() {
  return (
    <div className="grid min-h-screen lg:grid-cols-[248px_1fr]">
      <aside className="border-b border-line bg-ink/92 px-5 py-7 backdrop-blur-md lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r">
        <div className="mb-9 flex items-start gap-3">
          <div
            className="size-9 rounded-[10px] bg-gradient-to-br from-mint to-[#1f8f74] shadow-[0_0_0_4px_rgb(62_224_178_/_14%)]"
            aria-hidden="true"
          />
          <div>
            <h1 className="text-[1.05rem] tracking-wide">Ledger Guard</h1>
            <p className="mt-0.5 text-xs text-muted">Reconciliation copilot</p>
          </div>
        </div>
        <nav className="flex flex-wrap gap-1.5 lg:flex-col" aria-label="Primary">
          <NavLink to="/" end className={navClass}>
            Dashboard
          </NavLink>
          <NavLink to="/review" className={navClass}>
            Review queue
          </NavLink>
        </nav>
      </aside>
      <div className="px-[18px] py-6 pb-10 lg:px-10 lg:py-8 lg:pb-12">
        <Outlet />
      </div>
    </div>
  );
}
