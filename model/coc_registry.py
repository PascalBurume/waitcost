"""Multi-CoC support: run the SAME engine + SAME trained model for other cities.

The inflow model is a CROSS-CoC model (trained on 15 cities), so it predicts for
any city from that city's real ACS signals — no retraining. To run a city we:
  * take its REAL HUD 2024 PIT counts (initial state)            -> data/coc_panel.csv
  * predict its inflow with the SAME model from its REAL ACS     -> model.inflow_model
  * borrow CA-600's SPM-calibrated flow rates + costs as a labeled cross-CoC prior
    (until that city is calibrated from its own HUD SPM profile).

CA-600 (Los Angeles) stays the fully SPM-calibrated, backtested reference city;
other cities are clearly labeled "illustrative — local flow/cost calibration pending."
"""
import copy
import os

import pandas as pd
import yaml

from model.inflow_model import train_and_calibrate

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = os.path.join(REPO, "data", "coc_panel.csv")
BASE_PARAMS = os.path.join(REPO, "config", "params.yaml")


def available_cocs():
    """List the cities the engine can run (the 15 in the trained panel)."""
    df = pd.read_csv(PANEL)
    return [{"coc": r.coc, "name": r.coc_name, "pit_total": int(r.pit_total)}
            for r in df.itertuples()]


def build_params_for_coc(coc):
    """Build a params dict for `coc`, reusing the trained model + base structure.

    CA-600 returns the fully-calibrated base params unchanged.
    """
    base = yaml.safe_load(open(BASE_PARAMS))
    if coc == "CA-600":
        return base

    df = pd.read_csv(PANEL)
    sel = df[df["coc"] == coc]
    if sel.empty:
        raise ValueError(f"Unknown CoC '{coc}'. Options: {[c['coc'] for c in available_cocs()]}")
    r = sel.iloc[0]

    pit_total = int(r["pit_total"]); shel = int(r["pit_sheltered"])
    unshel = int(r["pit_unsheltered"]); chronic = int(r["pit_chronic"])
    pop = float(r["population"]); pov = float(r["poverty_rate"])

    # Split unsheltered into chronic / non-chronic (we only have total chronic per
    # city, so estimate the unsheltered-chronic share proportionally; conserves total).
    chronic_unshel = min(round(chronic * unshel / pit_total), unshel) if pit_total else 0
    unshel_nonchronic = max(unshel - chronic_unshel, 0)

    # at_risk / housed_stable: ACS proxies (same formula as the CA-600 calibration).
    poverty_persons = round(pov / 100.0 * pop)
    housed = max(poverty_persons - pit_total, pit_total)
    at_risk = max(round(0.08 * housed), 1)

    # Inflow from the SAME model, predicted from THIS city's real ACS signals.
    rep = train_and_calibrate(PANEL, target_coc=coc)
    inflow = rep["inflow_at_risk_monthly"]

    p = copy.deepcopy(base)
    p["meta"]["coc"] = f"{r['coc_name']} ({coc})"
    p["meta"]["data_vintage"] = ("HUD 2024 PIT (real) + Census ACS 2024 (API; real, drives the inflow "
                                 "model); flow rates & costs are CA-600 priors — local calibration pending")
    p["initial_population"] = {
        "housed_stable": int(housed), "at_risk": int(at_risk),
        "sheltered": shel, "unsheltered": unshel_nonchronic,
        "chronic_unsheltered": chronic_unshel, "exited_positive": 0,
    }
    p["inflow"] = {"at_risk": int(round(inflow["p50"]))}
    p["inflow_uncertainty"] = {"cv": round(float(inflow["implied_cv"]), 2),
                               "source": f"ACS->PIT model predicted for {coc} (LOO R^2={rep['loo_r2']:.2f})"}
    # Keep new-homeless flow consistent with the model's predicted inflow.
    for t in p["transitions"]:
        if t["from"] == "at_risk" and t["to"] == "sheltered":
            t["rate"] = round(inflow["p50"] / at_risk, 4)
            t["source"] = "calibrated to model-predicted inflow"
            t["confidence"] = "low"
    return p
