#!/usr/bin/env python3
"""
download_and_filter_licences.py

PURPOSE
-------
A GitHub-friendly (automation-ready) script that downloads Alberta "Water licences: active"
from Open Alberta, filters it to a sub-basin (e.g., 05CC), excludes DAUT Director
Authorizations, and writes clean outputs for downstream mapping and analysis.

WHY THIS SCRIPT EXISTS
----------------------
You want a repeatable pipeline that can run in:
- Local Python
- GitHub Codespaces
- GitHub Actions (scheduled daily/weekly)

This script intentionally:
- Uses a stable "latest" output filename (great for PowerBI pointing at a URL)
- Can also write a timestamped copy (great for audit trail)
- Can write TWO outputs:
    1) Allocation-level (long) table (keeps all allocation rows / PODs)
    2) Licence-level (collapsed) table (one row per Authorization Number) for mapping

KEY IDEA: TWO OUTPUTS
---------------------
In licensing datasets, one Authorization Number may appear multiple times because each
allocation / point of diversion is a separate row.

You eventually want those allocation-level rows for joining:
- allocation usage
- points of diversion ATS
- licence conditions per allocation

But for mapping right now, you want one point per licence:
- collapse duplicate Authorization Numbers
- add a "Number of allocations" count column

So:
- allocations_out = long table (keep everything)
- out = collapsed mapping table (one row per Authorization Number)

DATA ASSUMPTIONS (CURRENT PROTOTYPE)
------------------------------------
- Sub-basin filter uses column: "Water Allocation Use River Sub Basin Code"
- "AER only" is approximated by excluding Director Authorizations: Authorization Number starting with "DAUT"
  (DAUT = Director Authorization, typically AEP-issued Water Act administrative authorizations)

ATS TO LAT/LON
--------------
This script does NOT convert ATS to lat/long yet.
This keeps it focused and reliable. The next pipeline stage can read the allocations file,
parse ATS, join to ATS polygons, and compute centroids.

TYPICAL RUNS
------------
Collapsed mapping + keep allocations:
  python src/scripts/download_and_filter_licences.py \
    --subbasin 05CC \
    --collapse \
    --out outputs/licences_05CC_licences_latest.csv \
    --allocations-out outputs/licences_05CC_allocations_latest.csv \
    --timestamped-copy

Only collapsed mapping (no allocations output):
  python src/scripts/download_and_filter_licences.py \
    --subbasin 05CC \
    --collapse \
    --allocations-out ""

Only allocations output (no collapsing):
  python src/scripts/download_and_filter_licences.py \
    --no-collapse \
    --out outputs/licences_05CC_allocations_latest.csv \
    --allocations-out ""


REQUIREMENTS
------------
pip install pandas requests
(or add to requirements.txt)
"""

from __future__ import annotations

import argparse
import io
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

# ---------------------------------------------------------------------
# Default Open Alberta "Water licences: active" direct CSV download URL
# (If this URL ever changes, update it here or pass --url)
# ---------------------------------------------------------------------
DEFAULT_ACTIVE_LICENCES_CSV_URL = (
    "https://open.alberta.ca/dataset/47dbabf8-38e1-4692-aa7d-064acc85d450/"
    "resource/1f8d54e0-179b-4520-abce-2611f4a63d22/download/epa-water-licences-active.csv"
)

# These are the column names you have been working with.
# If upstream schema changes, you can pass overrides via CLI args.
DEFAULT_SUBBASIN_COL = "Water Allocation Use River Sub Basin Code"
DEFAULT_AUTH_COL = "Authorization Number"

# Stable "browser-like" user agent (helps avoid HTTP 403 blocks)
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class RunConfig:
    """All runtime settings parsed from CLI args."""

    url: str
    subbasin: str
    subbasin_col: str
    auth_col: str

    # Outputs
    licences_out_path: Path                 # collapsed mapping-friendly output ("latest")
    allocations_out_path: Optional[Path]    # long allocation-level output (or None to disable)

    # Behavior flags
    collapse: bool                          # whether to collapse to licence-level
    timestamped_copy: bool                  # also write a timestamped copy for audit trail

    # HTTP / parsing config
    timeout_seconds: int
    user_agent: str

    # logging
    verbose: bool


# -------------------------
# Logging / diagnostics
# -------------------------
def setup_logging(verbose: bool) -> None:
    """Initialize logging format and verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# -------------------------
# Download + load
# -------------------------
def download_csv(url: str, timeout_seconds: int, user_agent: str) -> pd.DataFrame:
    """
    Download the CSV over HTTP and load into a pandas DataFrame.

    Why not pd.read_csv(url)?
    - Some portals block unknown/default user-agents and return HTTP 403.
    - requests lets us supply headers to look like a normal browser.

    We also:
    - set low_memory=False (reduces dtype warning noise, more consistent inference)
    - strip column names (prevents KeyErrors from hidden leading/trailing spaces)
    """
    headers = {"User-Agent": user_agent, "Accept": "text/csv,text/plain,*/*"}

    logging.info("Downloading active licences CSV…")
    logging.debug("URL: %s", url)

    resp = requests.get(url, headers=headers, allow_redirects=True, timeout=timeout_seconds)
    resp.raise_for_status()

    df = pd.read_csv(io.StringIO(resp.text), low_memory=False)

    # IMPORTANT: normalize column headers to avoid accidental mismatch:
    # e.g. "Authorization Number " vs "Authorization Number"
    df.columns = df.columns.astype(str).str.strip()

    logging.info("Downloaded rows: %s", f"{len(df):,}")
    logging.debug("Downloaded columns: %s", len(df.columns))

    return df


def require_column(df: pd.DataFrame, col: str) -> None:
    """Fail fast with a helpful message if a required column is missing."""
    if col in df.columns:
        return

    # quick heuristic suggestions
    lower = col.lower().replace(" ", "")
    candidates = [c for c in df.columns if lower in c.lower().replace(" ", "")]
    raise KeyError(
        f"Expected column not found: '{col}'.\n"
        f"Closest matches: {candidates[:10]}\n"
        f"First 40 columns: {list(df.columns)[:40]}"
    )


# -------------------------
# Filtering steps
# -------------------------
def filter_by_subbasin(df: pd.DataFrame, subbasin_col: str, subbasin: str) -> pd.DataFrame:
    """
    Keep only records whose subbasin column equals the target (case/whitespace safe).
    """
    require_column(df, subbasin_col)

    target = str(subbasin).strip().upper()
    s = df[subbasin_col].astype(str).str.strip().str.upper()

    out = df.loc[s == target].copy()
    logging.info("Filtered to subbasin %s: %s rows", target, f"{len(out):,}")
    return out


def exclude_daut_authorizations(df: pd.DataFrame, auth_col: str) -> pd.DataFrame:
    """
    Exclude Director Authorizations, typically identified by Authorization Numbers starting with 'DAUT'.

    Why:
    - DAUT records tend to represent Director Authorizations issued under delegated authority.
    - For your current scope ("AER/industry-style licences"), you want to remove these.

    Implementation detail:
    - Convert to string, strip, uppercase (robust to blanks/NaNs)
    - Remove rows where auth starts with 'DAUT'
    """
    require_column(df, auth_col)

    s = df[auth_col].astype(str).str.strip().str.upper()
    mask_keep = ~s.str.startswith("DAUT")

    out = df.loc[mask_keep].copy()
    removed = len(df) - len(out)
    logging.info("Excluded DAUT* Director Authorizations: removed %s rows", f"{removed:,}")
    return out


# -------------------------
# Collapsing duplicates for mapping (prototype)
# -------------------------
def collapse_by_authorization_number(
    df: pd.DataFrame,
    auth_col: str,
    count_col: str = "Number of allocations",
) -> pd.DataFrame:
    """
    Collapse to ONE row per Authorization Number and add "Number of allocations".

    Why you want this (right now):
    - PowerBI mapping often looks better with one point per licence (one per authorization)
    - You still want to know how many allocation rows were rolled up

    IMPORTANT LIMITATION:
    - We keep the "first" row per authorization after sorting.
    - This means you are NOT preserving all ATS/POD variants in this collapsed table.
    - That’s okay for the "map layer" prototype, because the allocation-level file is also saved.

    Future upgrade:
    - Choose the "best" representative allocation row (e.g., most complete ATS, highest volume)
    - Or output a multi-geometry mapping approach (one licence -> multiple points/polygons)
    """
    require_column(df, auth_col)

    out = df.copy()

    # Use a normalized key so grouping isn't broken by case/spacing differences
    out["_auth_norm"] = out[auth_col].astype(str).str.strip().str.upper()

    # Count number of rows per authorization
    counts = out["_auth_norm"].value_counts(dropna=False)
    out[count_col] = out["_auth_norm"].map(counts).astype("Int64")

    # Reproducible selection: sort then keep first
    out = out.sort_values(by=["_auth_norm"]).drop_duplicates(subset=["_auth_norm"], keep="first")

    # Cleanup
    out = out.drop(columns=["_auth_norm"])

    logging.info("Collapsed to unique Authorization Numbers: %s rows", f"{len(out):,}")
    return out


# -------------------------
# Output writing
# -------------------------
def write_csv(df: pd.DataFrame, out_path: Path) -> None:
    """Write a DataFrame to CSV with parent dirs created."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    logging.info("Wrote: %s", out_path.as_posix())


def maybe_write_timestamped_copy(df: pd.DataFrame, out_path: Path, enabled: bool) -> None:
    """
    Optionally write a timestamped copy next to the stable 'latest' file.

    Why:
    - Helpful for debugging / auditing changes over time
    - Optional because it can clutter the repo if you commit them
    """
    if not enabled:
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stamped = out_path.with_name(out_path.stem + f"_{stamp}" + out_path.suffix)
    write_csv(df, stamped)


# -------------------------
# CLI / config
# -------------------------
def parse_args(argv: Optional[list[str]] = None) -> RunConfig:
    p = argparse.ArgumentParser(
        description="Download and filter Alberta active water licences (automation-ready)."
    )

    # Inputs
    p.add_argument("--url", default=DEFAULT_ACTIVE_LICENCES_CSV_URL, help="Direct CSV download URL")
    p.add_argument("--subbasin", default="05CC", help="Subbasin code to keep (e.g., 05CC)")
    p.add_argument("--subbasin-col", default=DEFAULT_SUBBASIN_COL, help="Subbasin column name")
    p.add_argument("--auth-col", default=DEFAULT_AUTH_COL, help="Authorization Number column name")

    # Outputs
    p.add_argument(
        "--out",
        default="outputs/licences_05CC_licences_latest.csv",
        help=(
            "Licence-level output path (stable name recommended for PowerBI), "
            "e.g. outputs/licences_05CC_licences_latest.csv"
        ),
    )
    p.add_argument(
        "--allocations-out",
        default="outputs/licences_05CC_allocations_latest.csv",
        help=(
            "Allocation-level output path (keeps ALL rows). "
            "Set to empty string '' to disable writing the allocation-level file."
        ),
    )

    # Behavior
    p.add_argument(
        "--collapse",
        action="store_true",
        help="Collapse duplicate Authorization Numbers into one row per authorization for mapping.",
    )
    p.add_argument(
        "--no-collapse",
        action="store_true",
        help="Explicitly disable collapse (useful if you want only allocation-level output).",
    )
    p.add_argument(
        "--timestamped-copy",
        action="store_true",
        help="Also write timestamped copies (in addition to stable latest filenames).",
    )

    # HTTP / reliability
    p.add_argument("--timeout", type=int, default=120, help="HTTP timeout seconds")
    p.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="User-Agent header string")

    # Logging
    p.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = p.parse_args(argv)

    # collapse logic:
    # - if --no-collapse is set, it wins
    collapse = args.collapse and not args.no_collapse

    allocations_out_path = None
    if str(args.allocations_out).strip() != "":
        allocations_out_path = Path(args.allocations_out)

    cfg = RunConfig(
        url=args.url,
        subbasin=args.subbasin,
        subbasin_col=args.subbasin_col,
        auth_col=args.auth_col,
        licences_out_path=Path(args.out),
        allocations_out_path=allocations_out_path,
        collapse=collapse,
        timestamped_copy=args.timestamped_copy,
        timeout_seconds=args.timeout,
        user_agent=args.user_agent,
        verbose=args.verbose,
    )

    setup_logging(cfg.verbose)
    logging.debug("Config: %s", cfg)

    return cfg


# -------------------------
# Main pipeline
# -------------------------
def main(argv: Optional[list[str]] = None) -> int:
    """
    Pipeline order:
    1) download active licences
    2) filter to subbasin
    3) exclude DAUT
    4) write allocation-level (optional)
    5) collapse for mapping (optional)
    6) write licence-level (always)
    """
    cfg = parse_args(argv)

    # 1) Download
    df = download_csv(cfg.url, cfg.timeout_seconds, cfg.user_agent)

    # 2) Subbasin filter
    df = filter_by_subbasin(df, cfg.subbasin_col, cfg.subbasin)

    # 3) Exclude DAUT
    df = exclude_daut_authorizations(df, cfg.auth_col)

    # 4) Write allocation-level output (optional but recommended)
    # This preserves all allocation rows for future usage/conditions joins.
    if cfg.allocations_out_path is not None:
        write_csv(df, cfg.allocations_out_path)
        maybe_write_timestamped_copy(df, cfg.allocations_out_path, cfg.timestamped_copy)

    # 5) Collapse to licence-level for mapping (optional)
    df_licences = df
    if cfg.collapse:
        df_licences = collapse_by_authorization_number(df, cfg.auth_col)

    # 6) Write licence-level output (the file PowerBI will likely point to)
    write_csv(df_licences, cfg.licences_out_path)
    maybe_write_timestamped_copy(df_licences, cfg.licences_out_path, cfg.timestamped_copy)

    logging.info("Done.")
    logging.info("Final allocation-level rows: %s", f"{len(df):,}")
    logging.info("Final licence-level rows: %s", f"{len(df_licences):,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
