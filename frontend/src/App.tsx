import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./layout/AppShell";
import { Dashboard } from "./pages/Dashboard";
import { ReviewQueue } from "./pages/ReviewQueue";
import { TransactionDetail } from "./pages/TransactionDetail";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="review" element={<ReviewQueue />} />
        <Route path="transactions/:txId" element={<TransactionDetail />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
