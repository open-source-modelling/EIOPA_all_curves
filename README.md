# EIOPA RFR curves

Python pipeline and historical dataset for [EIOPA](https://www.eiopa.europa.eu/) Risk-Free Rate (RFR) term structures.

Each month EIOPA publishes Excel workbooks with Smith–Wilson calibration vectors (`Qb`), curve parameters (UFR, α, LLP, …), and official spot rates. This repo extracts those releases into tidy CSV history so you can look up or rebuild a yield curve for any covered reference date and country without opening the original spreadsheets.

`qb_vectors.csv` and `curve_parameters.csv` currently cover monthly reference dates from **2014-12-31** through **2026-02-28** (135 months), for both `no_VA` and `with_VA`. Official spots in `yield_curves.csv` are present for the earlier part of that history; for later months, rebuild the curve from \(Qb\) + parameters (Option B below), or re-run the pipeline to extend the spot CSV.

## Repository layout

| Path | Role |
|------|------|
| `main.py` | CLI entry point: extract one month or a folder of monthly file pairs |
| `config.py` | Paths and `EIOPA_RFR_YYYYMMDD_` → ISO date parsing |
| `csv_store.py` | Idempotent CSV upserts keyed by `(reference_date, curve_type)` |
| `extractors/` | Excel parsers for Qb, parameters, and official spots |
| `input/` | Monthly EIOPA workbooks (`*_Qb_SW.xlsx`, `*_Term_Structures.xlsx`, …) |
| `data/` | Long-form CSV outputs (the usable dataset) |
| `CHECK_SINGLE_v2.ipynb` | Rebuild a curve with Smith–Wilson and compare to official spots |
| `pipeline_explained.html` | Walkthrough of how the extractors work |
| `requirements.txt` | Python dependencies |

## Data files

All rates and parameters live under `data/`:

### `yield_curves.csv` — official EIOPA spot rates

| Column | Description |
|--------|-------------|
| `reference_date` | ISO date (`YYYY-MM-DD`) |
| `curve_type` | `no_VA` or `with_VA` |
| `country` | Country / currency code (euro area = `EU`) |
| `term_index` | Maturity in years (typically 1…150) |
| `spot_rate` | Zero-coupon spot rate as a **decimal** (e.g. `0.02607` = 2.607%) |

### `curve_parameters.csv` — Smith–Wilson scalars per country

Includes `instrument_type`, `coupon_freq`, `llp`, `convergence`, `ufr`, `alpha`, `cra`, `va`.

Note: `ufr` is stored in **percent** (e.g. `3.45`). Divide by 100 before use in the Smith–Wilson formula.

### `qb_vectors.csv` — Smith–Wilson calibration vector \(Qb\)

| Column | Description |
|--------|-------------|
| `term_index` | Observation maturity (float; some markets use 0.5 steps) |
| `qb_value` | Calibration weight for that maturity |

Country codes are aligned across all three files (`EU` for the euro area).

## Setup

```bash
pip install -r requirements.txt
```

### Refresh / extend the CSVs from Excel

Place monthly pairs in `input/` (or pass explicit paths):

```bash
# One month
python main.py --qb-file input/EIOPA_RFR_20241130_Qb_SW.xlsx \
               --ts-file input/EIOPA_RFR_20241130_Term_Structures.xlsx

# Every paired month in a folder (re-runs are safe; same months are replaced)
python main.py --input-dir input
```

Expected filenames: `EIOPA_RFR_YYYYMMDD_Qb_SW.xlsx` and `EIOPA_RFR_YYYYMMDD_Term_Structures.xlsx`.

## Using the data to produce a yield curve

Pick a monthly `reference_date` that appears in the CSVs, a `curve_type` (`no_VA` or `with_VA`), and one or more country codes (euro area = `EU`). You can either read official published spots or rebuild the curve from Smith–Wilson inputs.

### Option A — Official EIOPA spots (when present in `yield_curves.csv`)

```python
import pandas as pd

yields = pd.read_csv("data/yield_curves.csv")

reference_date = "2015-01-31"   # must exist in yield_curves.csv
curve_type = "no_VA"            # or "with_VA"

# One country
eu = yields.query(
    "reference_date == @reference_date and curve_type == @curve_type and country == 'EU'"
).sort_values("term_index")
# Columns: term_index (years), spot_rate (decimal)

# All countries for that month → long or wide
all_countries = yields.query(
    "reference_date == @reference_date and curve_type == @curve_type"
)
spot_grid = all_countries.pivot(index="term_index", columns="country", values="spot_rate")
```

List what is available:

```python
dates = sorted(yields["reference_date"].unique())
countries = sorted(
    yields.loc[yields["reference_date"] == reference_date, "country"].unique()
)
```

### Option B — Reconstruct with Smith–Wilson (full history, any country)

This is the recommended path for **any historical date** covered by `qb_vectors.csv` / `curve_parameters.csv`. It rebuilds the spot curve from EIOPA’s \(Qb\) vector and \((ufr, \alpha)\), matching `CHECK_SINGLE_v2.ipynb`. The reconstruction follows the same algorithm as the original [Smith & Wilson implementation](https://github.com/open-source-modelling/insurance_python/tree/main/smith_wilson) in `open-source-modelling/insurance_python`.

```python
import numpy as np
import pandas as pd

def sw_extrapolate(m_target, m_obs, qb, ufr, alpha):
    """Smith–Wilson spot rates for maturities m_target (EIOPA technical docs §132 / §147)."""
    u = np.asarray(m_target, dtype=float).reshape(-1, 1)
    v = np.asarray(m_obs, dtype=float).reshape(1, -1)
    qb = np.asarray(qb, dtype=float).reshape(-1, 1)

    h = 0.5 * (
        alpha * (u + v)
        + np.exp(-alpha * (u + v))
        - alpha * np.abs(u - v)
        - np.exp(-alpha * np.abs(u - v))
    )
    discount = np.exp(-np.log(1 + ufr) * u) + np.diag(
        np.exp(-np.log(1 + ufr) * u.ravel())
    ) @ h @ qb
    return (discount.ravel() ** (-1.0 / u.ravel())) - 1.0


def curve_for(qb, params, reference_date, country, curve_type="no_VA", maturities=None):
    one_qb = qb.query(
        "reference_date == @reference_date and country == @country and curve_type == @curve_type"
    ).sort_values("term_index")
    one_p = params.query(
        "reference_date == @reference_date and country == @country and curve_type == @curve_type"
    )
    if one_qb.empty or one_p.empty:
        raise ValueError(f"No data for {reference_date=} {country=} {curve_type=}")

    m_obs = one_qb["term_index"].to_numpy()
    qb_vec = one_qb["qb_value"].to_numpy()
    ufr = float(one_p["ufr"].iloc[0]) / 100.0  # CSV stores percent
    alpha = float(one_p["alpha"].iloc[0])

    if maturities is None:
        maturities = np.arange(1, 151)  # 1Y … 150Y

    spots = sw_extrapolate(maturities, m_obs, qb_vec, ufr, alpha)
    return pd.DataFrame(
        {
            "reference_date": reference_date,
            "curve_type": curve_type,
            "country": country,
            "term_index": maturities,
            "spot_rate": spots,
        }
    )


qb = pd.read_csv("data/qb_vectors.csv")
params = pd.read_csv("data/curve_parameters.csv")

reference_date = "2024-11-30"  # any month in qb / params
curve_type = "no_VA"

# One country
eu_curve = curve_for(qb, params, reference_date, "EU", curve_type)

# Every country EIOPA published for that month
countries = params.query(
    "reference_date == @reference_date and curve_type == @curve_type"
)["country"].unique()

all_curves = pd.concat(
    [curve_for(qb, params, reference_date, c, curve_type) for c in countries],
    ignore_index=True,
)
# Long-form yield curves for all countries on that date
```

Typical absolute difference vs published spots (where both exist) is on the order of \(10^{-6}\).

For interactive checks (plot reconstructed vs official spots), open `CHECK_SINGLE_v2.ipynb`, set `reference_date_str`, `country`, and `is_va_str`, then run the notebook.

## Notes

- Prefer filtering CSVs by `reference_date` / `country` — `yield_curves.csv` and `qb_vectors.csv` are large.
- Not every country code exists on every date (EIOPA’s country set evolves over time). Always take the country list from the selected month.
- Raw monthly Excel files also include `*_PD_Cod.xlsx` and `*_VA_portfolios.xlsx`; the pipeline does not ingest those.

## License

MIT — see [`LICENSE`](LICENSE).
