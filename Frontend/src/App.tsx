import { IconContext } from "react-icons";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { EmptyState } from "@/components/ui";
import { Assess } from "@/pages/Assess";
import { Compare } from "@/pages/Compare";
import { Discover } from "@/pages/Discover";
import { Matching } from "@/pages/Matching";
import { Methodology } from "@/pages/Methodology";
import { Pipeline } from "@/pages/Pipeline";
import { StartupPage } from "@/pages/StartupPage";
import { AppDataProvider } from "@/state/AppData";

// Icons are decorative: every one sits next to visible text or an aria-label.
const ICONS = { attr: { "aria-hidden": true } };

export function App() {
  return (
    <IconContext.Provider value={ICONS}>
      <BrowserRouter>
        <AppDataProvider>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Discover />} />
              <Route path="startups/:slug" element={<StartupPage />} />
              <Route path="matching" element={<Matching />} />
              <Route path="assess" element={<Assess />} />
              <Route path="assess/:slug" element={<Assess />} />
              <Route path="pipeline" element={<Pipeline />} />
              <Route path="compare" element={<Compare />} />
              <Route path="methodology" element={<Methodology />} />
              <Route path="*" element={<EmptyState>Page not found.</EmptyState>} />
            </Route>
          </Routes>
        </AppDataProvider>
      </BrowserRouter>
    </IconContext.Provider>
  );
}
