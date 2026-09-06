import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { Dashboard } from "./pages/Dashboard";
import { ProjectsPage } from "./pages/ProjectsPage";
import { ReviewQueue } from "./pages/ReviewQueue";
import { TransactionDetail } from "./pages/TransactionDetail";
import { UploadRun } from "./pages/UploadRun";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="upload" element={<UploadRun />} />
        <Route path="review" element={<ReviewQueue />} />
        <Route path="transactions/:txId" element={<TransactionDetail />} />
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Route>
    </Routes>
  );
}
