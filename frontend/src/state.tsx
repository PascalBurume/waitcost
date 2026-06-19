import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api/client";
import type { Coc, Params, ProvenanceMap } from "./api/types";

type Theme = "light" | "dark";

interface AppState {
  coc: string;
  setCoc: (c: string) => void;
  theme: Theme;
  toggleTheme: () => void;
  params: Params | null;
  cocs: Coc[];
  provenance: ProvenanceMap | null;
  ready: boolean;
  bootError: Error | null;
}

const Ctx = createContext<AppState | null>(null);

const THEME_KEY = "waitcost-theme";

export function AppProvider({ children }: { children: ReactNode }) {
  // LA / CA-600 is the product default.
  const [coc, setCoc] = useState("CA-600");
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = (typeof localStorage !== "undefined" && localStorage.getItem(THEME_KEY)) as Theme | null;
    if (saved === "light" || saved === "dark") return saved;
    return typeof matchMedia !== "undefined" && matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark" : "light";
  });
  const [params, setParams] = useState<Params | null>(null);
  const [cocs, setCocs] = useState<Coc[]>([]);
  const [provenance, setProvenance] = useState<ProvenanceMap | null>(null);
  const [ready, setReady] = useState(false);
  const [bootError, setBootError] = useState<Error | null>(null);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem(THEME_KEY, theme); } catch { /* ignore */ }
  }, [theme]);

  useEffect(() => {
    let alive = true;
    Promise.all([api.params(), api.cocs()])
      .then(([p, cs]) => { if (alive) { setParams(p); setCocs(cs); setReady(true); } })
      .catch((e) => { if (alive) setBootError(e as Error); });
    // Provenance is an enhancement: fetch once, but never block boot if it fails.
    api.provenance().then((pv) => { if (alive) setProvenance(pv); }).catch(() => { /* ignore */ });
    return () => { alive = false; };
  }, []);

  const value: AppState = {
    coc, setCoc, theme,
    toggleTheme: () => setTheme((t) => (t === "light" ? "dark" : "light")),
    params, cocs, provenance, ready, bootError,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp must be used within AppProvider");
  return v;
}

/** Friendly city name for a CoC code, from the loaded catalog. */
export function useCityName(coc: string): string {
  const { cocs } = useApp();
  return cocs.find((c) => c.coc === coc)?.name ?? coc;
}
