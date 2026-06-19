import { useEffect, useState } from "react";
import { api } from "./api/client";
import type { ToolsPayload } from "./api/types";
import { AppProvider, useApp } from "./state";
import { DisclaimerBar, Nav, Topbar } from "./components/Shell";
import { ErrorState, Skel } from "./components/ui";
import { AskScreen } from "./screens/Ask";
import { ExploreScreen } from "./screens/Explore";
import { VisualizeScreen } from "./screens/Visualize";
import { ModelScreen } from "./screens/Model";
import { EquityScreen } from "./screens/Equity";
import { GovernanceScreen } from "./screens/Governance";
import { MapScreen } from "./screens/MapScreen";

function Shell() {
  const { ready, bootError } = useApp();
  const [tab, setTab] = useState("ask");
  const [tools, setTools] = useState<ToolsPayload | null>(null);

  // Sync the tab to the URL hash so screens are linkable/back-navigable.
  useEffect(() => {
    const fromHash = () => {
      const h = location.hash.replace("#", "");
      if (h) setTab(h);
    };
    fromHash();
    window.addEventListener("hashchange", fromHash);
    return () => window.removeEventListener("hashchange", fromHash);
  }, []);
  useEffect(() => { if (location.hash.replace("#", "") !== tab) history.replaceState(null, "", `#${tab}`); }, [tab]);

  useEffect(() => { api.tools().then(setTools).catch(() => setTools(null)); }, []);

  if (bootError) {
    return (
      <div className="app">
        <Topbar />
        <div className="main"><div className="page"><ErrorState error={bootError} label="WaitCost engine unreachable" /></div></div>
      </div>
    );
  }

  return (
    <div className="app">
      <Topbar />
      <DisclaimerBar />
      <Nav active={tab} onChange={setTab} />
      <main className="main">
        {!ready ? <BootSkeleton /> : (
          <>
            {tab === "ask" && <AskScreen tools={tools} />}
            {tab === "explore" && <ExploreScreen />}
            {tab === "visualize" && <VisualizeScreen />}
            {tab === "model" && <ModelScreen />}
            {tab === "equity" && <EquityScreen />}
            {tab === "governance" && <GovernanceScreen tools={tools} />}
            {tab === "map" && <MapScreen />}
          </>
        )}
      </main>
    </div>
  );
}

function BootSkeleton() {
  return (
    <div className="page" aria-busy="true">
      <Skel h={20} w={180} />
      <Skel h={48} w="60%" style={{ marginTop: 14 }} />
      <Skel h={360} style={{ marginTop: 28, borderRadius: 14 }} />
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}
