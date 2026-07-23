"""
CSV persistence for the extracted EIOPA RFR data.

Rather than a database, the full history is kept in three CSV files:
  - qb_vectors.csv        (reference_date, curve_type, country, term_index, qb_value)
  - curve_parameters.csv  (reference_date, curve_type, country, instrument_type,
                            coupon_freq, llp, convergence, ufr, alpha, cra, va)
  - yield_curves.csv      (reference_date, curve_type, country, term_index, spot_rate)

Loading is idempotent: if the CSV already contains rows for a given
(reference_date, curve_type), those rows are dropped and replaced with the
freshly parsed ones before writing back. That makes it safe to re-run the
pipeline for a month you've already loaded (e.g. if EIOPA republishes a
corrected file) without ending up with duplicate rows.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def _upsert_csv(csv_path: Path, new_df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop any existing rows for the same (reference_date, curve_type), then
    append new_df and rewrite the CSV. Shared by all output tables.
    """
    if new_df.empty:
        return new_df

    if not csv_path.exists():
        combined = new_df
    else:
        existing = pd.read_csv(csv_path)
        # Keys being refreshed by this run
        keys = new_df[["reference_date", "curve_type"]].drop_duplicates()
        key_index = pd.MultiIndex.from_frame(keys)
        existing_index = pd.MultiIndex.from_frame(
            existing[["reference_date", "curve_type"]]
        )
        # Keep rows whose (date, curve) is NOT being replaced
        keep = ~existing_index.isin(key_index)
        combined = pd.concat([existing.loc[keep], new_df], ignore_index=True)

    sort_cols = [
        c for c in ["reference_date", "curve_type", "country", "term_index"]
        if c in combined.columns
    ]
    combined = combined.sort_values(by=sort_cols).reset_index(drop=True)

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(csv_path, index=False)
    return combined


def save_qb_vectors(csv_path: Path, df: pd.DataFrame) -> pd.DataFrame:
    return _upsert_csv(csv_path, df)


def save_curve_parameters(csv_path: Path, df: pd.DataFrame) -> pd.DataFrame:
    return _upsert_csv(csv_path, df)


def save_yield_curves(csv_path: Path, df: pd.DataFrame) -> pd.DataFrame:
    return _upsert_csv(csv_path, df)
