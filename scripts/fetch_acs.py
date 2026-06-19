"""Reproducible ACS ingestion — pull the model's economic features straight from
the U.S. Census API (no manual transcription).

This replaces the one-time Census Reporter transcription with an auditable API
fetch. It rebuilds the ACS-derived columns of data/coc_panel.csv for all 17 CoCs,
writes a side file, and prints a diff vs. the existing (transcribed) values so the
fetch doubles as a verification of the original data.

USAGE
-----
    export CENSUS_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    python scripts/fetch_acs.py                 # -> data/coc_panel_acs_refresh.csv + diff report
    python scripts/fetch_acs.py --year 2024     # choose ACS 1-year vintage (default 2024)
    python scripts/fetch_acs.py --write         # overwrite data/coc_panel.csv (after you've reviewed the diff)

Get a free key (instant): https://api.census.gov/data/key_signup.html
Pure stdlib + pandas (already a project dependency). Homeless PIT columns are NOT
touched — those come from HUD, not the Census.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = os.path.join(REPO, "data", "coc_panel.csv")
REFRESH = os.path.join(REPO, "data", "coc_panel_acs_refresh.csv")

# ACS variable -> panel column. Median home value / income / household size etc.
VARS = {
    "B01003_001E": "population",
    "B19301_001E": "per_capita_income",
    "B19013_001E": "median_household_income",
    "B25077_001E": "median_home_value",
    "B25010_001E": "persons_per_household",
    "B17001_002E": "_pov_below",     # persons below poverty (numerator)
    "B17001_001E": "_pov_universe",  # poverty universe (denominator)
}
ACS_COLS = ["population", "per_capita_income", "median_household_income",
            "poverty_rate", "median_home_value", "persons_per_household",
            "pop_density_sqmi"]

# CoC -> Census geography (FIPS) + land area (sq mi, from the Census Gazetteer; ~constant year to year).
# Most CoCs ~ a single county; NYC and Chicago use the principal *place*; DC is a county-equivalent.
GEO = {
    "CA-600": {"kind": "county", "state": "06", "geo": "037", "land_sqmi": 4060.2},
    "CA-601": {"kind": "county", "state": "06", "geo": "073", "land_sqmi": 4210.3},
    "CA-501": {"kind": "county", "state": "06", "geo": "075", "land_sqmi": 46.7},
    "WA-500": {"kind": "county", "state": "53", "geo": "033", "land_sqmi": 2115.7},
    "AZ-502": {"kind": "county", "state": "04", "geo": "013", "land_sqmi": 9202.6},
    "CA-500": {"kind": "county", "state": "06", "geo": "085", "land_sqmi": 1291.1},
    "OR-501": {"kind": "county", "state": "41", "geo": "051", "land_sqmi": 431.0},
    "NV-500": {"kind": "county", "state": "32", "geo": "003", "land_sqmi": 7891.0},
    "NY-600": {"kind": "place",  "state": "36", "geo": "51000", "land_sqmi": 300.5},
    "DC-500": {"kind": "county", "state": "11", "geo": "001", "land_sqmi": 61.1},
    "MN-500": {"kind": "county", "state": "27", "geo": "053", "land_sqmi": 554.0},
    "TN-502": {"kind": "county", "state": "47", "geo": "093", "land_sqmi": 508.3},
    "FL-600": {"kind": "county", "state": "12", "geo": "086", "land_sqmi": 1899.9},
    "PA-500": {"kind": "county", "state": "42", "geo": "101", "land_sqmi": 134.3},
    "IL-510": {"kind": "place",  "state": "17", "geo": "14000", "land_sqmi": 227.7},
    "CA-503": {"kind": "county", "state": "06", "geo": "067", "land_sqmi": 965.3},
    "AZ-501": {"kind": "county", "state": "04", "geo": "019", "land_sqmi": 9184.9},
}

BASE = "https://api.census.gov/data/{year}/acs/acs1"


def fetch_one(year, spec, key):
    """Call the ACS 1-year API for one geography; return {panel_col: value}."""
    get = "NAME," + ",".join(VARS)
    if spec["kind"] == "county":
        geo_q = {"for": f"county:{spec['geo']}", "in": f"state:{spec['state']}"}
    else:  # place
        geo_q = {"for": f"place:{spec['geo']}", "in": f"state:{spec['state']}"}
    url = BASE.format(year=year) + "?" + urllib.parse.urlencode({"get": get, "key": key, **geo_q})
    with urllib.request.urlopen(url, timeout=30) as r:
        rows = json.loads(r.read().decode("utf-8"))
    header, data = rows[0], rows[1]
    rec = dict(zip(header, data))
    out = {}
    for var, col in VARS.items():
        v = rec.get(var)
        out[col] = float(v) if v not in (None, "", "null") else float("nan")
    # derived
    out["poverty_rate"] = round(out.pop("_pov_below") / out.pop("_pov_universe") * 100.0, 1)
    out["pop_density_sqmi"] = round(out["population"] / spec["land_sqmi"], 1)
    out["population"] = int(out["population"])
    for c in ("per_capita_income", "median_household_income", "median_home_value"):
        out[c] = int(out[c])
    out["persons_per_household"] = round(out["persons_per_household"], 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--write", action="store_true", help="overwrite data/coc_panel.csv after review")
    args = ap.parse_args()

    key = os.environ.get("CENSUS_API_KEY")
    if not key:
        sys.exit("CENSUS_API_KEY not set. Get one at https://api.census.gov/data/key_signup.html "
                 "then: export CENSUS_API_KEY=...")

    cur = pd.read_csv(PANEL).set_index("coc")
    new = cur.copy()
    print(f"Fetching ACS {args.year} 1-year for {len(GEO)} CoCs ...\n")
    print(f"{'CoC':7s} {'column':24s} {'transcribed':>14s} {'API':>14s} {'%diff':>8s}")
    flagged = []
    fetched = 0
    for coc, spec in GEO.items():
        try:
            vals = fetch_one(args.year, spec, key)
        except Exception as e:
            print(f"  {coc}: FETCH ERROR — {e}")
            continue
        fetched += 1
        for col in ACS_COLS:
            old = cur.loc[coc, col]
            nv = vals[col]
            pct = (nv - old) / old * 100.0 if old else float("nan")
            mark = "  <-- check" if abs(pct) >= 5 else ""
            if abs(pct) >= 5:
                flagged.append((coc, col, old, nv, pct))
            print(f"{coc:7s} {col:24s} {old:>14,.1f} {nv:>14,.1f} {pct:>7.1f}%{mark}")
            new.loc[coc, col] = nv
        new.loc[coc, "acs_release"] = f"ACS {args.year} 1-yr (API)"
        print()

    if fetched == 0:
        print("\nCould not reach the Census API — 0/%d geographies fetched." % len(GEO))
        print("This usually means a restricted/sandboxed network. Run it on your own machine:")
        print("    export CENSUS_API_KEY=...  &&  python scripts/fetch_acs.py")
        return

    new.reset_index().to_csv(REFRESH, index=False)
    print(f"\nFetched {fetched}/{len(GEO)} CoCs. Wrote refreshed feature columns -> {REFRESH}")
    if flagged:
        print(f"\n{len(flagged)} value(s) differ >=5% from the transcribed panel — review before committing:")
        for coc, col, old, nv, pct in flagged:
            print(f"  {coc} {col}: {old:,.1f} -> {nv:,.1f} ({pct:+.1f}%)")
    elif fetched == len(GEO):
        print("\nAll API values within 5% of the transcribed panel — original data verified. ✓")
    else:
        print(f"\n(Only {fetched}/{len(GEO)} fetched — partial verification.)")

    if args.write and fetched == len(GEO):
        new.reset_index().to_csv(PANEL, index=False)
        print(f"\n--write: overwrote {PANEL} with API-sourced values. "
              f"Re-run scripts/train_inflow.py to refit the model.")
    elif args.write:
        print(f"\n--write ignored: only {fetched}/{len(GEO)} geographies fetched; panel left unchanged.")
    else:
        print("\n(Default: did not modify coc_panel.csv. Re-run with --write once the diff looks right.)")


if __name__ == "__main__":
    main()
