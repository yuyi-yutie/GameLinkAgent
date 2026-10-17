import { useCallback, useEffect, useState } from "react";

import { api } from "./api";
import { ConfigPanel } from "./components/ConfigPanel";
import { StatusBar } from "./components/StatusBar";
import { Home } from "./routes/Home";
import { Project } from "./routes/Project";
import type { Health } from "./types";

const PATH_PARAM = "path";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [projectPath, setProjectPath] = useState<string | null>(
    () => new URLSearchParams(window.location.search).get(PATH_PARAM),
  );

  const refreshHealth = useCallback(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    refreshHealth();
  }, [refreshHealth]);

  // Keep the selected project in the URL so a refresh lands back where you were.
  useEffect(() => {
    const url = new URL(window.location.href);
    if (projectPath) url.searchParams.set(PATH_PARAM, projectPath);
    else url.searchParams.delete(PATH_PARAM);
    window.history.replaceState(null, "", url);
  }, [projectPath]);

  return (
    <div className="app">
      <StatusBar health={health} onOpenConfig={() => setConfigOpen(true)} />
      {projectPath ? (
        <Project path={projectPath} onLeave={() => setProjectPath(null)} />
      ) : (
        <Home health={health} onPick={setProjectPath} />
      )}
      {configOpen && (
        <ConfigPanel
          onClose={() => {
            setConfigOpen(false);
            refreshHealth();
          }}
        />
      )}
    </div>
  );
}
