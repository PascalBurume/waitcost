"""Train + evaluate + explain the inflow predictor, and emit the calibration.

Run from repo root:
    python scripts/train_inflow.py

Writes model/inflow_model.json (full provenance: metrics, SHAP, calibration).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model import inflow_model as im  # noqa: E402

CSV = "data/coc_panel.csv"


def main():
    df = im.load_panel(CSV)
    print(f"Loaded real panel: {len(df)} CoCs (HUD 2024 PIT + ACS 2024 1-yr)\n")

    # Compare two candidate targets honestly via leave-one-CoC-out CV.
    Xs, mu, sd = im._design(df)
    for col in ["homeless_rate_per_1k", "unsheltered_rate_per_1k"]:
        y = df[col].to_numpy(float)
        label, _, loo = im.select_model(Xs, y)
        print(f"target={col:24s}  best={label:18s}  LOO R^2={loo['loo_r2']:+.3f}  "
              f"LOO MAE={loo['loo_mae']:.3f}")

    print("\n--- Primary model: total homeless rate per 1k -> CA-600 calibration ---")
    rep = im.train_and_calibrate(CSV, target_coc="CA-600",
                                 target_col="homeless_rate_per_1k",
                                 spm_first_time_annual=29818, spm_pit=71320)  # HUD SPM 2023 M5
    print(f"model={rep['model']}  n={rep['n_coc']}")
    print(f"LOO R^2={rep['loo_r2']:+.3f}   LOO MAE={rep['loo_mae']:.3f}   "
          f"in-sample R^2={rep['insample_r2']:+.3f}")
    print(f"CA-600 observed rate ={rep['observed_rate_per_1k']:.2f}/1k   "
          f"predicted ={rep['predicted_rate_per_1k']:.2f}/1k "
          f"[p10 {rep['pred_rate_p10']:.2f}, p90 {rep['pred_rate_p90']:.2f}]")
    print("\nSHAP (exact, additive) — drivers of CA-600 predicted homelessness:")
    for d in rep["shap_target"]:
        bar = "+" if d["shap"] >= 0 else "-"
        print(f"  {bar} {d['feature']:24s} {d['shap']:+.3f} /1k")
    inf = rep["inflow_at_risk_monthly"]
    print(f"\nCalibrated monthly at-risk inflow (CA-600): "
          f"p50={inf['p50']:.0f}  [p10 {inf['p10']:.0f}, p90 {inf['p90']:.0f}]  "
          f"implied CV={inf['implied_cv']:.2f}")

    out = im.save_report(rep, "model/inflow_model.json")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
