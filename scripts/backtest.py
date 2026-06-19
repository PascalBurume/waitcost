"""Run the CA-600 face-validity backtest and print the result.

    python scripts/backtest.py

Seeds the model with real 2023 HUD PIT compartments and checks the 12-month
forward run brackets the observed 2024 PIT total (71,201).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml  # noqa: E402
from model.backtest import backtest  # noqa: E402


def main():
    params = yaml.safe_load(open("config/params.yaml"))
    r = backtest(params)
    print("WaitCost backtest — CA-600 face validity")
    print(f"  seed: real 2023 PIT compartments (total {r['seed_total']:,})")
    print(f"  12-month forward run, status quo, calibrated SPM rates")
    print(f"  predicted 2024 active homeless: P50 {r['predicted_active_p50']:,.0f} "
          f"[P10 {r['predicted_active_p10']:,.0f}, P90 {r['predicted_active_p90']:,.0f}]")
    print(f"  observed 2024 PIT total:        {r['observed_2024_total']:,}")
    print(f"  central error: {r['abs_pct_error_p50']:.1f}%   observed within band: {r['within_band']}")


if __name__ == "__main__":
    main()
