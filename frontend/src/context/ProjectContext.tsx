import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

const STORAGE_KEY = "ledger-guard:active-project-id";

interface ProjectContextValue {
  activeProjectId: string | null;
  setActiveProjectId: (id: string | null) => void;
}

const ProjectContext = createContext<ProjectContextValue | null>(null);

function readStoredId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [activeProjectId, setActiveProjectIdState] = useState<string | null>(() => readStoredId());

  const setActiveProjectId = (id: string | null) => {
    setActiveProjectIdState(id);
    try {
      if (id) localStorage.setItem(STORAGE_KEY, id);
      else localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  };

  const value = useMemo(
    () => ({ activeProjectId, setActiveProjectId }),
    [activeProjectId],
  );

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useActiveProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) {
    throw new Error("useActiveProject must be used within ProjectProvider");
  }
  return ctx;
}
