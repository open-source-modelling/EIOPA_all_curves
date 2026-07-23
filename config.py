"""
Shared configuration / constants for the EIOPA RFR extraction pipeline.
"""
import re
from pathlib import Path

# EIOPA publishes files named like:
#   EIOPA_RFR_20241130_Qb_SW.xlsx
#   EIOPA_RFR_20241130_Term_Structures.xlsx
FILENAME_DATE_RE = re.compile(r"EIOPA_RFR_(\d{8})_")


def extract_reference_date(filename: str) -> str:
    """
    Pull the yyyymmdd reference date embedded in EIOPA's filename convention
    and return it as an ISO date string (YYYY-MM-DD).

    Raises ValueError if the filename doesn't match the expected pattern,
    so a mis-named/misplaced file fails loudly instead of silently
    corrupting the dataset with a wrong date.
    """
    m = FILENAME_DATE_RE.search(Path(filename).name)
    if not m:
        raise ValueError(
            f"Could not find an EIOPA_RFR_YYYYMMDD_ date stamp in filename: {filename}"
        )
    raw = m.group(1)
    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


# Default output locations
OUTPUT_DIR = Path(__file__).parent / "data"
QB_CSV_PATH = OUTPUT_DIR / "qb_vectors.csv"
PARAMS_CSV_PATH = OUTPUT_DIR / "curve_parameters.csv"
YIELD_CURVES_CSV_PATH = OUTPUT_DIR / "yield_curves.csv"
