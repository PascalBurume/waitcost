# notebooks/

**`WaitCost_model_and_visuals.ipynb`** — reproduces the quantitative core of WaitCost end to end:
the data, the learned inflow model (held-out leave-one-CoC-out R², exact SHAP), the face-validity
backtest, and the web-app decision charts. It imports the project's own modules (`model/`, `analysis/`,
`agent/`) so it can never drift from the shipped engine. Outputs are already embedded; *Run All* to
regenerate.

Run from the repo root (or this folder):

```bash
pip install numpy pandas matplotlib pyyaml jupyter
jupyter notebook notebooks/WaitCost_model_and_visuals.ipynb   # then Run All
```

`figures/` holds the rendered charts (`backtest.png`, `decision_charts.png`) for quick reference.
All data provenance is in `../data_sources/SOURCES_MANIFEST.md`.
