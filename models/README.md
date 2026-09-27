# Models directory
This directory stores a trained model binary (gitignored) and reviewable metadata/reports.

Each model save includes:
- `delay_model.joblib` — Fitted preprocessing and LightGBM model (gitignored)
- `model_metadata.json` — Features, training date, metrics, split, versions, source and hashes
- `evaluation.md` — Readable exploration, baseline comparison, and limitations

Generate these with `python -m copilot.ml.train --data data/processed/bts_sample.csv`.
Training holds out the last calendar month and does not tune on that test set.
Metadata and the report are small and can be committed to document a run.
Training again replaces the outputs; use `--output-dir` to retain separate runs.

Only load joblib files you trust: deserialization can execute Python code.
Synthetic-model scores are teaching results only. Delay-model probabilities are
not yet calibrated and do not determine legal eligibility.


Current checked artifact: **REAL BTS**, retrained September 27, 2026 on the
January–March 2025 sample. Metadata uses `source: real` for human clarity and
`data_source: bts` for the prediction contract. Its manifest sets `synthetic: false`.
At the fixed threshold, recall is only 1.29% and accuracy is below the always-on-time
baseline; see `evaluation.md`. The prior synthetic artifact has been replaced.
