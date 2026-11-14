# AGENTS.md

### Overview & Scope

Python pipeline that extracts EIOPA Risk-Free Rate (RFR) monthly Excel releases into long-form CSV history under `data/`. Applies to the whole repo (single project; no nested `AGENTS.md`).

Sources: `input/EIOPA_RFR_YYYYMMDD_Qb_SW.xlsx` + `input/EIOPA_RFR_YYYYMMDD_Term_Structures.xlsx`. Outputs: `data/qb_vectors.csv`, `data/curve_parameters.csv`, `data/yield_curves.csv`. Validation / Smith-Wilson reconstruction lives in `TEST_RECALCULATION_ALL.ipynb`. Human-readable documentation: `README.md`.

### Agent Role

Act as an experienced Python data-engineering contributor for this EIOPA extraction stack (`pandas` + `openpyxl`).

Allowed: edit extractors, `main.py`, `config.py`, `csv_store.py`, notebooks, docs; run single-month or small-batch extractions; spot-check CSV samples.

Not allowed: invent dependency files or CI that do not exist; rewrite the storage model without asking; commit or push unless explicitly requested.

### Build, Test & Validation Commands

Dependencies are pinned in `requirements.txt` (`pandas`, `openpyxl`, `numpy`, `matplotlib`). No `pyproject.toml`, linter, or automated test suite.

```bash
# Install
pip install -r requirements.txt

# Process one month (safe smoke run)
python main.py --qb-file input/EIOPA_RFR_20241130_Qb_SW.xlsx --ts-file input/EIOPA_RFR_20241130_Term_Structures.xlsx

# Process all paired months in input/ (slow; one pair per month since 2014-12; rewrites large CSVs)
python main.py --input-dir input

# Smoke-test a single extractor
python extractors/qb_extractor.py input/EIOPA_RFR_20241130_Qb_SW.xlsx
python extractors/param_extractor.py input/EIOPA_RFR_20241130_Term_Structures.xlsx
python extractors/spot_extractor.py input/EIOPA_RFR_20241130_Term_Structures.xlsx
```

Validation of reconstructed vs official curves: open and run `TEST_RECALCULATION_ALL.ipynb` (not a CLI test).

### Conventions & Patterns

- Entry point: `main.py` → extractors → `csv_store._upsert_csv` (idempotent replace on `(reference_date, curve_type)`).
- Config / date parsing: `config.py` (`EIOPA_RFR_YYYYMMDD_` → ISO `YYYY-MM-DD`).
- Extractors live in `extractors/`; each maps sheet names to `curve_type` `no_VA` / `with_VA`.
- Prefer layout **detection** over hard-coded Excel rows when EIOPA shifts sheets (see `qb_extractor._find_header_row`).
- Keep Qb `term_index` as **float** (semi-annual countries use `0.5` steps).
- Country codes in CSVs match Qb labels: euro area is `EU` (sheet `EUR`); United Kingdom is `UK` (Term-Structures historically used `GB`, normalised on extract).
- Spot rates are decimals (e.g. `0.02607`), not percentages.
- `openpyxl.load_workbook(..., data_only=True)`; do **not** use `read_only=True` for Qb (random `.cell()` access is very slow).
- Pipeline only consumes `*_Qb_SW.xlsx` and `*_Term_Structures.xlsx`. `*_PD_Cod.xlsx` / `*_VA_portfolios.xlsx` in `input/` are unused by `main.py`.
- When searching code, ignore `.git/`, `.ipynb_checkpoints/`, `input/*.xlsx`, and large `data/*.csv` contents unless the task is about data itself.

### Dos and Don’ts

- Do keep upsert semantics in `csv_store.py` so re-runs never duplicate months.
- Do fail loudly on missing sheets, date mismatches between paired files, or unparseable filenames.
- Do reuse `_parse_country_code` / shared sheet constants from `param_extractor` when touching spot extraction.
- Don’t cast Qb `term_index` to `int`.
- Don’t assume header row numbers are fixed across all historical EIOPA files.
- Don’t add frameworks, databases, or new package managers without approval.
- Don’t hand-edit the large historical CSVs when a pipeline re-run can regenerate the month.

### Safety & Guardrails

- `input/` holds many large monthly workbooks; avoid copying/moving bulk files.
- `data/yield_curves.csv` and `data/qb_vectors.csv` are large; prefer filtering by `reference_date` / `country` over loading entire files into agent context.
- Safe to automate: single-file extractor smoke tests, small CSV head checks, code edits, notebook cell logic.
- Avoid by default: full `--input-dir` rebuilds, deleting `data/` or `input/`, mass-renaming EIOPA files.
- Do not edit generated notebook checkpoints under `.ipynb_checkpoints/`.
- No secrets in this repo; keep it that way. License is MIT (`LICENSE`).

### Git & PR Rules

- No formal branching model documented; keep changes focused and small.
- Recent commit style is short imperative / descriptive phrases (e.g. `Check for no_VA and after Nov 2015`). Match that: concise, why-focused subject lines.
- No CI; for PRs describe what was extracted/validated and which month file was used as the smoke sample.
- `.gitignore` excludes `__pycache__/` and `.ipynb_checkpoints/`; never commit those or secrets.
- Commit / push only when the user explicitly asks.

### Additional rules

- `README.md` documents the data files and how to use them; module docstrings give domain context.
- Keep this file factual: only document commands and conventions that exist in the tree.
