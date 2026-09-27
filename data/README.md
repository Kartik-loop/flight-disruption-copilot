# Data directory
The `raw/` and `processed/` subdirectories are gitignored. This README is tracked.

- `raw/` — Downloaded source data (e.g., BTS on-time performance CSVs)
- `processed/` — Cleaned, feature-engineered data ready for model training

Run `python -m copilot.ml.data` from the project root to download January–March
2025 BTS Reporting Carrier data and sample up to 20,000 completed flights per
month. Archives remain compressed and are processed in chunks. Re-running reuses
cached archives. A corrupt archive fails explicitly; remove that specific file
before retrying its download.

The output is `processed/bts_sample.csv` and `bts_sample.metadata.json`.
The metadata records sampling settings, source archive hashes, raw/usable row
counts, and the sample hash. Training checks that hash before fitting.

With `--allow-synthetic`, a network failure instead creates
`processed/synthetic_sample.csv` and its metadata. Synthetic data is visibly
labelled and replaces the entire sample, even if earlier downloads succeeded.
Malformed ZIPs or missing BTS columns fail rather than triggering fallback.

Sources: [BTS archives](https://transtats.bts.gov/PREZIP/) and
[field definitions](https://transtats.bts.gov/Fields.asp?gnoyr_VQ=FGJ).
