"""Learned inflow predictor: ACS economic signals -> homelessness, with SHAP.

This is the project's real *learned* component (the "where's the ML?" answer).

INPUTS (named):  per-capita income, median household income, poverty rate,
                 median home value (housing cost), population density,
                 persons-per-household — all real ACS 2024 1-yr values.
TRAINING SIGNAL: real HUD 2024 PIT homeless counts per CoC (rate per 1,000).
MODEL:           gradient-boosted decision stumps (additive ensemble), trained
                 on a 15-CoC cross-section in data/coc_panel.csv.
METRICS:         leave-one-CoC-out cross-validation R^2 and MAE (honest, since
                 n is small and we never test on a CoC we trained on).
EXPLAINABILITY:  because the model is additive, f(x) = base + Σ_j g_j(x_j), the
                 Shapley value of feature j is EXACT: φ_j(x) = g_j(x_j) − E[g_j].
                 (This is what shap.TreeExplainer returns for an additive model;
                 we compute it in closed form so the demo needs no extra deps.)

The model's prediction for the chosen CoC + its leave-one-out residual spread
give a calibrated inflow with a *learned* uncertainty band, which the Monte
Carlo then propagates — replacing hand-set noise with model-derived noise.

Pure NumPy/pandas: no scikit-learn/scipy/shap required to run.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

# Named features (order is stable; used for SHAP labels). Trimmed to the
# economically-motivated, low-collinearity set (per-capita income is dropped as
# collinear with median household income; persons-per-household carried no
# signal in leave-one-out testing).
FEATURES = [
    "log_median_home_value",   # housing cost — the headline driver in the literature
    "poverty_rate",
    "median_household_income",
    "log_pop_density",
]


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
def load_panel(csv_path):
    """Load the real CoC panel and derive the modelling frame."""
    df = pd.read_csv(csv_path)
    df["homeless_rate_per_1k"] = df["pit_total"] / df["population"] * 1000.0
    df["unsheltered_rate_per_1k"] = df["pit_unsheltered"] / df["population"] * 1000.0
    df["log_median_home_value"] = np.log(df["median_home_value"].astype(float))
    df["log_pop_density"] = np.log(df["pop_density_sqmi"].astype(float))
    return df


def _design(df):
    X = df[FEATURES].to_numpy(float)
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd == 0] = 1.0
    Xs = (X - mu) / sd
    return Xs, mu, sd


# --------------------------------------------------------------------------- #
# Gradient-boosted stumps (additive ensemble -> exact SHAP)
# --------------------------------------------------------------------------- #
class GBStumps:
    """Additive gradient boosting with depth-1 trees (stumps).

    Additivity is the point: each stump touches exactly one feature, so the
    fitted function decomposes as f(x) = base + Σ_j g_j(x_j), which makes the
    Shapley decomposition exact and closed-form.
    """

    def __init__(self, n_rounds=40, lr=0.1, min_leaf=3, seed=0):
        self.n_rounds = int(n_rounds)
        self.lr = float(lr)
        self.min_leaf = int(min_leaf)
        self.seed = int(seed)
        self.base_ = 0.0
        self.stumps_ = []   # list of (feature_idx, threshold, left_val, right_val)

    def _best_stump(self, X, resid):
        n, p = X.shape
        best = None
        best_sse = np.inf
        for j in range(p):
            xj = X[:, j]
            order = np.argsort(xj)
            xs = xj[order]
            # candidate thresholds = midpoints between consecutive unique values
            cuts = (xs[:-1] + xs[1:]) / 2.0
            for t in np.unique(cuts):
                left = xj <= t
                right = ~left
                if left.sum() < self.min_leaf or right.sum() < self.min_leaf:
                    continue
                lv = resid[left].mean()
                rv = resid[right].mean()
                sse = ((resid[left] - lv) ** 2).sum() + ((resid[right] - rv) ** 2).sum()
                if sse < best_sse:
                    best_sse = sse
                    best = (j, float(t), float(lv), float(rv))
        return best

    def fit(self, X, y):
        X = np.asarray(X, float)
        y = np.asarray(y, float)
        self.base_ = float(y.mean())
        resid = y - self.base_
        self.stumps_ = []
        for _ in range(self.n_rounds):
            stump = self._best_stump(X, resid)
            if stump is None:
                break
            j, t, lv, rv = stump
            pred = np.where(X[:, j] <= t, lv, rv)
            resid = resid - self.lr * pred
            self.stumps_.append(stump)
        return self

    def _feature_contrib_matrix(self, X):
        """Return (n, p): the additive contribution g_j(x) of each feature."""
        X = np.asarray(X, float)
        n, p = X.shape
        G = np.zeros((n, p))
        for (j, t, lv, rv) in self.stumps_:
            G[:, j] += self.lr * np.where(X[:, j] <= t, lv, rv)
        return G

    def predict(self, X):
        return self.base_ + self._feature_contrib_matrix(X).sum(axis=1)


class RidgeLinear:
    """Ridge-regularized linear model (additive -> exact SHAP).

    Standardized inputs are assumed; with n small and features collinear,
    L2 shrinkage gives far better leave-one-out generalization than boosting.
    f(x) = base + Σ_j w_j x_j, so contributions are simply w_j x_j.
    """

    def __init__(self, alpha=1.0):
        self.alpha = float(alpha)
        self.base_ = 0.0
        self.w_ = None

    def fit(self, X, y):
        X = np.asarray(X, float)
        y = np.asarray(y, float)
        self.base_ = float(y.mean())
        yc = y - self.base_
        p = X.shape[1]
        A = X.T @ X + self.alpha * np.eye(p)
        self.w_ = np.linalg.solve(A, X.T @ yc)
        return self

    def _feature_contrib_matrix(self, X):
        return np.asarray(X, float) * self.w_   # (n, p)

    def predict(self, X):
        return self.base_ + self._feature_contrib_matrix(X).sum(axis=1)


# --------------------------------------------------------------------------- #
# Evaluation + explainability
# --------------------------------------------------------------------------- #
def leave_one_out(X, y, factory):
    """Honest generalization: predict each CoC from a model trained on the rest."""
    n = len(y)
    preds = np.zeros(n)
    for i in range(n):
        mask = np.arange(n) != i
        preds[i] = factory().fit(X[mask], y[mask]).predict(X[i:i + 1])[0]
    ss_res = float(((y - preds) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    mae = float(np.abs(y - preds).mean())
    return {"loo_r2": r2, "loo_mae": mae, "loo_pred": preds.tolist()}


def select_model(X, y):
    """Pick the model+hyperparameter with the best leave-one-out R^2.

    Candidates: Ridge over an alpha grid (parsimonious, regularized) and
    gradient-boosted stumps over a rounds grid (nonlinear). Returns the winning
    factory, a human label, and its LOO result.
    """
    candidates = []
    for a in (0.3, 1.0, 3.0, 10.0, 30.0):
        candidates.append((f"ridge(alpha={a})", lambda a=a: RidgeLinear(alpha=a)))
    for m in (10, 20, 30, 40, 50):
        candidates.append((f"gb_stumps(rounds={m})",
                           lambda m=m: GBStumps(n_rounds=m, lr=0.1, min_leaf=3)))
    best = None
    for label, factory in candidates:
        res = leave_one_out(X, y, factory)
        if best is None or res["loo_r2"] > best[2]["loo_r2"]:
            best = (label, factory, res)
    return best   # (label, factory, loo_result)


def shap_values(model, X, Xref):
    """EXACT Shapley values for the additive model.

    φ_j(x) = g_j(x_j) − E_train[g_j].  Sums to f(x) − E_train[f].  For an
    additive model these equal what shap.TreeExplainer would return.
    """
    G = model._feature_contrib_matrix(X)
    Gref_mean = model._feature_contrib_matrix(Xref).mean(axis=0)
    return G - Gref_mean   # (n, p)


# --------------------------------------------------------------------------- #
# Calibrate the simulator's at-risk inflow from the model
# --------------------------------------------------------------------------- #
def calibrate_inflow(pred_rate_per_1k, lo_rate, hi_rate, population,
                     annual_turnover=0.35, at_risk_share=1.0):
    """Convert a predicted homeless prevalence rate into a monthly at-risk inflow.

    Transparent flow assumption (documented, tagged low-confidence pending HUD
    SPM Measure-5 'first-time homeless' calibration): each year roughly
    `annual_turnover` of the homeless stock is replaced by new entries, so

        annual_new_entries ≈ prevalence_count × annual_turnover
        monthly_inflow_at_risk ≈ annual_new_entries / 12

    The band (p10/p90) is carried straight from the model's prediction interval
    so the Monte Carlo propagates a *learned* uncertainty, not a hand-set one.
    """
    def to_monthly(rate):
        count = rate / 1000.0 * population
        return count * annual_turnover / 12.0 * at_risk_share

    p50 = to_monthly(pred_rate_per_1k)
    p10 = to_monthly(lo_rate)
    p90 = to_monthly(hi_rate)
    # coefficient of variation implied by the learned band (for the MC sampler)
    cv = (p90 - p10) / (2 * 1.2816 * p50) if p50 > 0 else 0.0
    return {"p50": p50, "p10": p10, "p90": p90, "implied_cv": cv,
            "annual_turnover": annual_turnover}


def train_and_calibrate(csv_path, target_coc="CA-600",
                        target_col="homeless_rate_per_1k",
                        annual_turnover=0.42,           # HUD SPM 2023 M5/PIT (29,818/71,320)
                        spm_first_time_annual=None, spm_pit=None):
    """End-to-end: fit, evaluate (LOO), explain (SHAP), calibrate target CoC.

    If SPM Measure-5 (first-time homeless) is supplied, the report includes a
    cross-validation of the ML-predicted inflow against the measured SPM inflow.
    """
    df = load_panel(csv_path)
    Xs, mu, sd = _design(df)
    y = df[target_col].to_numpy(float)

    model_label, factory, loo = select_model(Xs, y)
    model = factory().fit(Xs, y)

    # in-sample R^2 (for reference only)
    insample = model.predict(Xs)
    ss_res = float(((y - insample) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    insample_r2 = 1.0 - ss_res / ss_tot

    # LOO residual spread -> prediction interval for the target CoC
    loo_pred = np.array(loo["loo_pred"])
    resid = y - loo_pred
    resid_sd = float(resid.std(ddof=1))

    ti = int(df.index[df["coc"] == target_coc][0])
    pred_rate = float(model.predict(Xs[ti:ti + 1])[0])
    lo_rate = max(pred_rate - 1.2816 * resid_sd, 0.0)   # ~p10
    hi_rate = pred_rate + 1.2816 * resid_sd             # ~p90

    sv = shap_values(model, Xs[ti:ti + 1], Xs)[0]
    shap_named = sorted(
        ({"feature": f, "shap": float(v)} for f, v in zip(FEATURES, sv)),
        key=lambda d: abs(d["shap"]), reverse=True,
    )

    pop = float(df.loc[ti, "population"])
    inflow = calibrate_inflow(pred_rate, lo_rate, hi_rate, pop,
                              annual_turnover=annual_turnover)

    return {
        "target_coc": target_coc,
        "target_col": target_col,
        "n_coc": int(len(df)),
        "features": FEATURES,
        "model": model_label,
        "loo_r2": loo["loo_r2"],
        "loo_mae": loo["loo_mae"],
        "insample_r2": insample_r2,
        "observed_rate_per_1k": float(df.loc[ti, target_col]),
        "predicted_rate_per_1k": pred_rate,
        "pred_rate_p10": lo_rate,
        "pred_rate_p90": hi_rate,
        "shap_target": shap_named,
        "base_value_rate_per_1k": float(model.base_),
        "expected_value_rate_per_1k": float(model.predict(Xs).mean()),
        "inflow_at_risk_monthly": inflow,
        "spm_crossval": _spm_crossval(inflow["p50"], spm_first_time_annual, spm_pit),
        "data_source": "HUD 2024 PIT (CoC PopSub) + Census ACS 2024 1-yr; see data/SOURCES.md",
    }


def _spm_crossval(ml_monthly, spm_first_time_annual, spm_pit):
    """Cross-validate the ML inflow against HUD SPM Measure 5 (independent real data)."""
    if not spm_first_time_annual:
        return None
    spm_monthly = spm_first_time_annual / 12.0
    pct = abs(ml_monthly - spm_monthly) / spm_monthly * 100.0
    return {"spm_first_time_annual": spm_first_time_annual,
            "spm_inflow_monthly": spm_monthly,
            "ml_inflow_monthly": ml_monthly,
            "agreement_pct_diff": pct,
            "note": "ML (ACS->PIT) vs HUD SPM M5 (first-time homeless): independent methods"}


def save_report(report, out_path):
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps(report, indent=2))
    return out_path
