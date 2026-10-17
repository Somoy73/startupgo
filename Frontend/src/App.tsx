import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Assess } from "./pages/Assess";
import { Compare } from "./pages/Compare";
import { DealFlow } from "./pages/DealFlow";
import { Matching } from "./pages/Matching";
import { Methodology } from "./pages/Methodology";
import { Pipeline } from "./pages/Pipeline";
import { StartupPage } from "./pages/StartupPage";
import { AppDataProvider } from "./state/AppData";

export function App() {
  return (
    <BrowserRouter>
      <AppDataProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<DealFlow />} />
            <Route path="startups/:slug" element={<StartupPage />} />
            <Route path="matching" element={<Matching />} />
            <Route path="assess" element={<Assess />} />
            <Route path="assess/:slug" element={<Assess />} />
            <Route path="pipeline" element={<Pipeline />} />
            <Route path="compare" element={<Compare />} />
            <Route path="methodology" element={<Methodology />} />
            <Route path="*" element={<p className="empty">Page not found.</p>} />
          </Route>
        </Routes>
      </AppDataProvider>
    </BrowserRouter>
  );
}
