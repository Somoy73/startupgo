import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Compare } from "./pages/Compare";
import { DealFlow } from "./pages/DealFlow";
import { Methodology } from "./pages/Methodology";
import { Pipeline } from "./pages/Pipeline";
import { StartupPage } from "./pages/StartupPage";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DealFlow />} />
          <Route path="startups/:slug" element={<StartupPage />} />
          <Route path="pipeline" element={<Pipeline />} />
          <Route path="compare" element={<Compare />} />
          <Route path="methodology" element={<Methodology />} />
          <Route path="*" element={<p className="empty">Page not found.</p>} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
