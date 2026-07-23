"""
Orchestrates monthly extraction of EIOPA Risk-Free Rate data.

Usage:
    python main.py --qb-file EIOPA_RFR_20241130_Qb_SW.xlsx \
                    --ts-file EIOPA_RFR_20241130_Term_Structures.xlsx

    # Or point it at a folder containing many months of both files:
    python main.py --input-dir /path/to/eiopa_monthly_downloads

Each run:
  1. Parses the reference date out of the filename.
  2. Extracts Qb vectors and curve parameters.
  3. Upserts them into data/qb_vectors.csv and data/curve_parameters.csv
     (any rows already present for that month/curve get replaced, so
     re-running is safe and never duplicates rows).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from config import OUTPUT_DIR, PARAMS_CSV_PATH, QB_CSV_PATH, extract_reference_date
from csv_store import save_curve_parameters, save_qb_vectors
from extractors.param_extractor import extract_parameters
from extractors.qb_extractor import extract_qb_vectors


def process_file_pair(qb_file: Path, ts_file: Path):
    qb_date = extract_reference_date(qb_file.name)
    ts_date = extract_reference_date(ts_file.name)
    if qb_date != ts_date:
        raise ValueError(
            f"Date mismatch between paired files: {qb_file.name} ({qb_date}) "
            f"vs {ts_file.name} ({ts_date})"
        )

    print(f"[{qb_date}] extracting Qb vectors from {qb_file.name} ...")
    qb_df = extract_qb_vectors(str(qb_file), qb_date)
    qb_full = save_qb_vectors(QB_CSV_PATH, qb_df)
    print(f"  -> {len(qb_df)} rows parsed ({qb_df['country'].nunique()} countries); "
          f"{QB_CSV_PATH.name} now has {len(qb_full)} rows total")

    print(f"[{ts_date}] extracting curve parameters from {ts_file.name} ...")
    params_df = extract_parameters(str(ts_file), ts_date)
    params_full = save_curve_parameters(PARAMS_CSV_PATH, params_df)
    print(f"  -> {len(params_df)} rows parsed ({params_df['country'].nunique()} countries); "
          f"{PARAMS_CSV_PATH.name} now has {len(params_full)} rows total")


def discover_pairs(input_dir: Path) -> list[tuple[Path, Path]]:
    qb_files = sorted(input_dir.glob("EIOPA_RFR_*_Qb_SW.xlsx"))
    pairs = []
    for qb_file in qb_files:
        date_token = qb_file.name.split("_Qb_SW.xlsx")[0]  # EIOPA_RFR_YYYYMMDD
        ts_file = input_dir / f"{date_token}_Term_Structures.xlsx"
        if ts_file.exists():
            pairs.append((qb_file, ts_file))
        else:
            print(f"WARNING: no matching Term_Structures file for {qb_file.name}, skipping")
    return pairs


def main():
    parser = argparse.ArgumentParser(description="EIOPA RFR monthly extraction pipeline")
    parser.add_argument("--qb-file", type=Path, help="Path to a single Qb_SW.xlsx file")
    parser.add_argument("--ts-file", type=Path, help="Path to a single Term_Structures.xlsx file")
    parser.add_argument(
        "--input-dir", type=Path, help="Folder containing one or more monthly file pairs"
    )
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.input_dir:
        pairs = discover_pairs(args.input_dir)
    elif args.qb_file and args.ts_file:
        pairs = [(args.qb_file, args.ts_file)]
    else:
        parser.error("Provide either --input-dir, or both --qb-file and --ts-file")
        return

    for qb_file, ts_file in pairs:
        process_file_pair(qb_file, ts_file)


if __name__ == "__main__":
    main()
