import { Navigate, Route, Routes } from "react-router-dom";
import { StudioPage } from "./pages/StudioPage";
import { GenerationPage } from "./pages/GenerationPage";
import { HistoryPage } from "./pages/HistoryPage";

export function AppRouter() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/studio" replace />} />
      <Route path="/studio" element={<StudioPage />} />
      <Route path="/studio/:id" element={<GenerationPage />} />
      <Route path="/history" element={<HistoryPage />} />
      <Route path="*" element={<Navigate to="/studio" replace />} />
    </Routes>
  );
}
