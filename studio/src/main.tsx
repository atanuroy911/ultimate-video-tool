import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Shell from "./Shell";
import { PairGate } from "./Pair";
import ProjectsPage from "./pages/Projects";
/** A screen loaded on demand. After an update the old files are gone: a tab opened before it reloads once to get the new ones. */
function lazyScreen(load: () => Promise<{ default: React.ComponentType<any> }>) {
  return React.lazy(() =>
    load().catch((error) => {
      if (!sessionStorage.getItem("vt-reloaded-for-update")) {
        sessionStorage.setItem("vt-reloaded-for-update", "1");
        location.reload();
        return new Promise<never>(() => {});
      }
      throw error;
    }).then((screen) => {
      sessionStorage.removeItem("vt-reloaded-for-update");
      return screen;
    }),
  );
}

const NewPage = lazyScreen(() => import("./pages/New"));
const ProgressPage = lazyScreen(() => import("./pages/Progress"));
const ReviewPage = lazyScreen(() => import("./pages/Review"));
const EditorPage = lazyScreen(() => import("./editor/EditorPage"));
const ExportPage = lazyScreen(() => import("./pages/Export"));
const ResultPage = lazyScreen(() => import("./pages/Result"));
const ThemesPage = lazyScreen(() => import("./pages/Themes"));
const SettingsPage = lazyScreen(() => import("./pages/Settings"));
const ShortsPage = lazyScreen(() => import("./pages/ShortsExtractor"));
const SocialPage = lazyScreen(() => import("./pages/SocialHub"));
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <PairGate>
    <BrowserRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/new" element={<NewPage />} />
          <Route path="/shorts" element={<ShortsPage />} />
          <Route path="/social" element={<SocialPage />} />
          <Route path="/p/:id/shorts" element={<ShortsPage />} />
          <Route path="/p/:id/progress" element={<ProgressPage />} />
          <Route path="/p/:id" element={<EditorPage />} />
          <Route path="/p/:id/pro" element={<ReviewPage />} />
          <Route path="/p/:id/export" element={<ExportPage />} />
          <Route path="/p/:id/result" element={<ResultPage />} />
          <Route path="/themes" element={<ThemesPage />} />
          <Route path="/themes/:name" element={<ThemesPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="*" element={<ProjectsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
    </PairGate>
  </React.StrictMode>
);

// installable app: the service worker lets browsers offer "Install" and opens the shell instantly
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => undefined));
}
