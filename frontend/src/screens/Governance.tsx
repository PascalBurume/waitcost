import { useState } from "react";
import type { ToolsPayload, AskResult } from "../api/types";
import { api } from "../api/client";
import { useApp } from "../state";
import { Icon } from "../lib/icons";
import { TierBadge } from "../components/ui";

const TIERS = [
  { tier: 0 as const, label: "Automatic — read only", desc: "Look-ups, context, chart rendering, backtest. No judgement, no side effects.", gate: "Runs immediately." },
  { tier: 1 as const, label: "Automatic — analysis", desc: "Scenarios, equity queries, briefs. Always returns ranges and sources; declines on thin data.", gate: "Runs immediately, logged in the trajectory." },
  { tier: 2 as const, label: "Human approval required", desc: "Any recommendation of a specific, binding allocation or budget action.", gate: "Pauses and asks a named person to sign off before proceeding." },
];

export function GovernanceScreen({ tools }: { tools: ToolsPayload | null }) {
  const { params } = useApp();
  const [thin, setThin] = useState(false);

  return (
    <div className="page page-wide">
      <div className="section-head">
        <span className="eyebrow">Governance</span>
        <h1 className="page-title serif">How the agent is allowed to act</h1>
        <p className="lede">Every tool call carries an Action Tier. Reads and analysis run automatically; a binding allocation pauses for a named human. When the data can't support an honest answer, the agent declines rather than guesses.</p>
      </div>

      <div className="gov-grid">
        <div>
          <div className="card gov-tiers">
            <span className="eyebrow">Action tiers</span>
            <div className="tier-table" style={{ marginTop: 14 }}>
              {TIERS.map((t) => (
                <div className="tier-row" key={t.tier}>
                  <TierBadge tier={t.tier} />
                  <div>
                    <div className="tier-cell-h">{t.label}</div>
                    <div className="tier-cell-d">{t.desc}</div>
                  </div>
                  <div className="tier-gate">{t.gate}</div>
                </div>
              ))}
            </div>

            <div className="gov-tools">
              <span className="eyebrow">The agent's tool catalog{tools ? ` · ${tools.capabilities.length} capabilities · ${tools.agents} agents` : ""}</span>
              <div style={{ marginTop: 12 }}>
                {(tools?.capabilities ?? []).map((c) => (
                  <div className="gov-tool" key={c.name}>
                    <TierBadge tier={c.tier} compact />
                    <span className="step-tool">{c.name}</span>
                    <span className="gov-tool-desc">{c.desc}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div>
          <div className="card" style={{ marginBottom: 22, padding: "20px 22px" }}>
            <span className="eyebrow"><Icon.Shield size={13} /> Every answer is checked — the Evaluator (5th agent)</span>
            <p className="muted" style={{ fontSize: "var(--fs-sm)", margin: "12px 0 18px", lineHeight: 1.65 }}>
              The worst outcome in a budget tool is a confident <i>wrong</i> answer. So before you
              see one, a post-answer critic checks it across six dimensions — hard guarantees in
              code, plus an LLM judge for relevance. When something's off, we show you what.
            </p>

            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase",
              color: "var(--ink-3)", marginBottom: 6 }}>The six checks</div>
            <ul style={{ listStyle: "none", margin: 0, padding: 0, fontSize: "var(--fs-sm)" }}>
              {([
                ["Grounding", "every figure traces to the engine — no invented numbers"],
                ["Scope", "never answers an individual / sub-CoC question"],
                ["Parameters", "flags any default used; echoes back what it read"],
                ["Data confidence", "labels non-LA cities illustrative, widens the range"],
                ["Chart ↔ text", "the chart shows the same figure as the text"],
                ["Question-match", "an LLM judge checks it answers what you asked"],
              ] as const).map(([n, d]) => (
                <li key={n} style={{ display: "flex", gap: 14, padding: "8px 0", lineHeight: 1.5,
                  borderBottom: "1px solid var(--hairline)" }}>
                  <span style={{ flex: "0 0 130px", fontWeight: 600 }}>{n}</span>
                  <span style={{ flex: 1, color: "var(--ink-2)" }}>{d}</span>
                </li>
              ))}
            </ul>

            <div style={{ marginTop: 18, display: "grid", gap: 8, fontSize: "var(--fs-sm)", lineHeight: 1.55 }}>
              <div><b>If it's wrong</b> — it self-corrects once, then declines rather than guess.</div>
              <div><b>If it's ambiguous</b> — it asks which reading you meant instead of picking one.</div>
              <div><b>If it's unsure</b> — it answers with a caveat, never a wrongful refusal.</div>
            </div>

            <EvaluatorDemo />
          </div>

          <div className="card gov-suff">
            <span className="eyebrow">Data-sufficiency demo</span>
            <p className="muted" style={{ fontSize: "var(--fs-sm)", margin: "8px 0 16px" }}>
              Toggle a thin-data condition. Rather than show an unsupported band, the agent declines.
            </p>
            <label className="approval-check" style={{ marginBottom: 16 }}>
              <input type="checkbox" checked={thin} onChange={(e) => setThin(e.target.checked)} />
              <span>Simulate: PIT count older than the support threshold (insufficient to bound uncertainty).</span>
            </label>
            {thin ? (
              <div className="suff-no">
                <span className="suff-badge no"><Icon.Slash size={12} /> Declined</span>
                <p>The agent stops here. The available data can't support an honest 80% range, so it will not produce a number.</p>
                <div className="suff-quote">“I can't answer this without overstating my confidence. The PIT vintage for this CoC is outside the support window — tighten the data before relying on a cost-of-waiting figure.”</div>
              </div>
            ) : (
              <div className="suff-ok">
                <span className="suff-badge ok"><Icon.Check size={12} /> Supported</span>
                <p>Data passes the support check. Scenarios run, every figure ships with sources and an 80% range, and the full trajectory is logged.</p>
              </div>
            )}
          </div>

          <div className="card gov-sources" style={{ marginTop: 22 }}>
            <span className="eyebrow">Data sources</span>
            <ul className="src-list" style={{ marginTop: 12 }}>
              <li><b>HUD 2024 PIT</b> — Point-in-Time homelessness counts (CoC PopSub).</li>
              <li><b>Census ACS 2024</b> — population, income, poverty, housing cost.</li>
              <li><b>HUD SPM (2023)</b> — system inflow + key exit/return rates.</li>
              <li><b>Economic Roundtable</b> — per-person public cost estimates (2024$).</li>
            </ul>
            <p className="muted" style={{ fontSize: "var(--fs-sm)", marginTop: 12, lineHeight: 1.55 }}>
              The ACS economic features are reproducible from the Census API via{" "}
              <code>scripts/fetch_acs.py</code> and were verified against the original transcription
              (0 of 119 values differed ≥5%). See <code>data_sources/METHODOLOGY.md</code>.
            </p>
            <div className="lifecycle">
              <span className="eyebrow">Lifecycle</span>
              <p className="muted" style={{ fontSize: "var(--fs-sm)", marginTop: 8, lineHeight: 1.55 }}>
                Recalibrated on each annual PIT + ACS release. Held-out R² and the backtest are re-run every refresh;
                if the model drifts outside its backtest band, the headline reverts to a wider documented-prior range.
                {params ? ` Current vintage: ${params.data_vintage}.` : ""}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Live demo: run the Evaluator on a sample question and show its real verdict, so
// the per-dimension check isn't just described — you watch it happen.
const _RC_COLOR: Record<string, string> = { ok: "#1d9e75", warn: "#c8881e", fail: "#d93025" };
const _RC_STATUS: Record<string, [string, string]> = {
  pass: ["Looks solid", "#1d9e75"], warn: ["Read with caveats", "#c8881e"],
  repair: ["Self-corrected", "#1a73e8"], decline: ["Withheld", "#d93025"],
};

function EvaluatorDemo() {
  const { coc } = useApp();
  const [busy, setBusy] = useState(false);
  const [q, setQ] = useState<string | null>(null);
  const [res, setRes] = useState<AskResult | null>(null);

  const examples: [string, string][] = [
    ["A clean question", "What if we wait 3 years on a $15M program?"],
    ["No budget given", "What does waiting 3 years cost?"],
    ["Out of scope", "Which family on 5th Street will become homeless next year?"],
  ];
  const run = (question: string) => {
    setQ(question); setBusy(true); setRes(null);
    api.ask({ question, coc }).then(setRes).catch(() => setRes(null)).finally(() => setBusy(false));
  };

  const rc = res?.response_check;
  const icon = (s: string) => s === "ok" ? <Icon.Check size={13} />
    : s === "warn" ? <Icon.Info size={13} /> : <Icon.Slash size={13} />;

  return (
    <div style={{ marginTop: 16, borderTop: "1px solid var(--hairline)", paddingTop: 14 }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".04em", textTransform: "uppercase",
        color: "var(--ink-3)", marginBottom: 8 }}>See it run on a live answer</div>
      <div className="declined-suggest" style={{ marginBottom: res || busy ? 14 : 0 }}>
        {examples.map(([label, question]) => (
          <button key={label} className="suggest-chip" disabled={busy}
            style={{ opacity: busy ? 0.5 : 1 }} onClick={() => run(question)}>{label}</button>
        ))}
      </div>

      {busy && (
        <div className="muted" style={{ fontSize: "var(--fs-sm)", display: "flex", gap: 8, alignItems: "center" }}>
          <Icon.Spinner size={14} /> Running the engine, then checking the answer…
        </div>
      )}

      {!busy && res && (
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 10, marginBottom: 8 }}>
            <span className="muted" style={{ fontSize: "var(--fs-sm)" }}>“{q}”</span>
            <span className="pill" style={{ flex: "0 0 auto",
              color: (_RC_STATUS[rc?.status ?? (res.declined ? "decline" : "pass")] || _RC_STATUS.pass)[1] }}>
              {(_RC_STATUS[rc?.status ?? (res.declined ? "decline" : "pass")] || _RC_STATUS.pass)[0]}
            </span>
          </div>
          {rc ? (
            <ul style={{ listStyle: "none", margin: 0, padding: 0, fontSize: "var(--fs-sm)" }}>
              {rc.checks.map((c) => (
                <li key={c.name} style={{ display: "flex", gap: 10, padding: "4px 0", alignItems: "baseline" }}>
                  <span style={{ color: _RC_COLOR[c.status], flex: "0 0 auto", transform: "translateY(2px)" }}>{icon(c.status)}</span>
                  <span style={{ flex: "0 0 116px", fontWeight: 600, textTransform: "capitalize" }}>{c.name.replace(/_/g, " ")}</span>
                  <span style={{ flex: 1, color: "var(--ink-2)" }}>{c.detail}</span>
                </li>
              ))}
            </ul>
          ) : (
            // out-of-scope / clarify: the deterministic safety rail caught it before the engine ran
            <p className="muted" style={{ fontSize: "var(--fs-sm)", lineHeight: 1.55 }}>
              <b style={{ color: "#d93025" }}>Scope check failed</b> — the engine never ran. {res.reason}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
