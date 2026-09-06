import { NavLink, Outlet } from "react-router-dom";
import { RouteErrorBoundary } from "../components/RouteErrorBoundary";
import { useActiveProject } from "../context/ProjectContext";
import { cx } from "../lib/ui";

const navClass = ({ isActive }: { isActive: boolean }) =>
  cx(
    "block rounded-[10px] px-3 py-2.5 text-muted hover:bg-hover hover:text-ink-text",
    isActive && "bg-hover text-ink-text shadow-[inset_2px_0_0_#3ee0b2]",
  );

export function AppShell() {
  const { activeProjectId } = useActiveProject();

  return (
    <div className="grid min-h-screen lg:grid-cols-[248px_1fr]">
      <aside className="border-b border-line bg-ink/92 px-5 py-7 backdrop-blur-md lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r">
        <div className="mb-9 flex items-start gap-3">
          <img
            src="/logo.png"
            alt=""
            width={36}
            height={36}
            className="size-9 object-contain"
            aria-hidden="true"
          />
          <div>
            <h1 className="text-[1.05rem] tracking-wide">Ledger Guard</h1>
            <p className="mt-0.5 text-xs text-muted">Reconciliation copilot</p>
          </div>
        </div>
        <nav className="flex flex-wrap gap-1.5 lg:flex-col" aria-label="Primary">
          <NavLink to="/projects" className={navClass}>
            Projects
          </NavLink>
          <NavLink to="/upload" className={navClass}>
            Upload & run
          </NavLink>
          <NavLink to="/" end className={navClass}>
            Dashboard
          </NavLink>
          <NavLink to="/review" className={navClass}>
            Review queue
          </NavLink>
        </nav>
        {activeProjectId ? (
          <p className="mt-6 break-all font-mono text-[11px] text-muted">
            Active project
            <br />
            <span className="text-ink-text">{activeProjectId.slice(0, 8)}…</span>
          </p>
        ) : null}
      </aside>
      <div className="px-[18px] py-6 pb-10 lg:px-10 lg:py-8 lg:pb-12">
        <RouteErrorBoundary>
          <Outlet />
        </RouteErrorBoundary>
      </div>
    </div>
  );
}
