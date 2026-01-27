from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd


ACTIVE_LICENCES_CSV_URL = (
    "https://open.alberta.ca/dataset/47dbabf8-38e1-4692-aa7d-064acc85d450/"
    "resource/1f8d54e0-179b-4520-abce-2611f4a63d22/download/epa-water-licences-active.csv"
)

SUBBASIN_COL = "Water Allocation Use River Sub Basin Code"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--subbasin", default="05CC", help="Sub-basin code to keep (e.g., 05CC)")
    p.add_argument("--url", default=ACTIVE_LICENCES_CSV_URL, help="CSV URL to download")
    p.add_argument("--out_dir", default="data/processed", help="Output directory")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading active licences CSV…")
    df = pd.read_csv(args.url)
    print(f"Rows downloaded: {len(df):,}")

    if SUBBASIN_COL not in df.columns:
        raise SystemExit(
            f"Expected column not found: {SUBBASIN_COL}\n"
            f"Closest matches: {[c for c in df.columns if 'Sub Basin' in c or 'Basin' in c][:10]}"
        )

    sub = str(args.subbasin).strip().upper()

    filtered = df[
        df[SUBBASIN_COL]
        .astype(str)
        .str.strip()
        .str.upper()
        == sub
    ].copy()

    out_path = out_dir / f"epa_water_licences_active_subbasin_{sub}.csv"
    filtered.to_csv(out_path, index=False)

    print(f"\nSaved filtered dataset only:")
    print(f"  {out_path}")
    print(f"Filtered rows (subbasin {sub}): {len(filtered):,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
