import { useState } from "react";
import type { ToolsPayload } from "../api/types";
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
