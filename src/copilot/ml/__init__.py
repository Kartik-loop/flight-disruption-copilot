"""
copilot.ml — Machine learning model for flight delay prediction.

This package contains the delay-prediction model: training pipeline,
evaluation, and a prediction interface that agents can call as a tool.

LEARN: The ML model is a supporting component, not the core product.
Its job is to give agents additional context ("flights on this route
are delayed 35% of the time"), which helps the eligibility explanation.
The model is trained on US BTS On-Time Performance data and predicts
binary arrival delay (15+ minutes late).

Key design decisions:
  - Time-based train/test split (not random) to avoid temporal leakage
  - Only pre-departure features to avoid data leakage
  - Saved with joblib alongside metadata for reproducibility

Phase 3 implements data.py (download, cleaning, sampling, labelled fallback)
and train.py (time-based evaluation, baseline, model and metadata persistence).
Phase 4 adds predict.py: a guarded prediction tool with explicit synthetic-demo
opt-in, provenance checks, and coverage checks for US domestic flight inputs.
"""
