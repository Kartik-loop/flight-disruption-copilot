"""Train and evaluate a small LightGBM delay classifier using an honest time split.

This module consumes the labelled sample from ml.data and saves preprocessing
with the model. The last calendar month is held out, while a plain-text report
and JSON metadata make the result easy to study without running a notebook.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from copilot.config import settings
from copilot.ml.data import (
    CATEGORICAL_FEATURES,
    DISCLAIMER,
    FEATURES,
    NUMERIC_FEATURES,
    TARGET,
    file_sha256,
)


def split_by_month(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hold out the latest full calendar month to mimic predicting future flights."""
    frame = frame.copy()
    frame["flight_date"] = pd.to_datetime(frame["flight_date"], errors="raise")
    months = frame["flight_date"].dt.to_period("M")
    if frame["flight_date"].isna().any() or months.nunique() < 2:
        raise ValueError("Need valid flight dates spanning at least two calendar months.")
    # LEARN: A random split would let future flights help predict past flights.
    # Keeping an entire later month unseen reveals changes in schedules and
    # conditions. No encoder or model is fitted on these held-out rows.
    train = frame.loc[months < months.max()].sort_values("flight_date")
    test = frame.loc[months == months.max()].sort_values("flight_date")
    if train[TARGET].nunique() < 2:
        raise ValueError("Training data must contain both delayed and on-time flights.")
    return train, test


def build_pipeline(seed: int = 42) -> Pipeline:
    """Package feature encoding with the classifier so later inference uses identical transforms."""
    # LEARN: One-hot encoding gives each known airline/airport its own column.
    # Unknown categories become all-zero vectors rather than crashing inference.
    # The encoder learns categories from training data only, inside this pipeline.
    preprocessing = ColumnTransformer(
        [
            ("categories", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
            ("schedule", "passthrough", NUMERIC_FEATURES),
        ]
    )
    # NOTE: Small fixed settings keep the exercise fast. We deliberately do not
    # tune against the test month; doing so would make it a validation set.
    classifier = LGBMClassifier(
        n_estimators=150,
        learning_rate=0.05,
        num_leaves=15,
        min_child_samples=50,
        reg_lambda=1.0,
        random_state=seed,
        n_jobs=2,
        verbosity=-1,
        deterministic=True,
        force_col_wise=True,
    )
    return Pipeline([("preprocess", preprocessing), ("classifier", classifier)])


def classification_metrics(y_true: pd.Series, probabilities: np.ndarray) -> dict:
    """Report multiple views of quality because accuracy alone can reward ignoring delays."""
    predicted = probabilities >= 0.5
    # LEARN: Precision asks how many flagged flights really were delayed;
    # recall asks how many delayed flights we found. ROC-AUC evaluates ranking
    # across thresholds, but is undefined if the test set contains only one class.
    return {
        "accuracy": float(accuracy_score(y_true, predicted)),
        "precision": float(precision_score(y_true, predicted, zero_division=0)),
        "recall": float(recall_score(y_true, predicted, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, probabilities)) if y_true.nunique() == 2 else None,
    }


def describe_split(frame: pd.DataFrame) -> dict:
    """Record the population and dates behind a score so the number has useful context."""
    return {
        "rows": len(frame),
        "start": str(frame["flight_date"].min().date()),
        "end": str(frame["flight_date"].max().date()),
        "delay_rate": float(frame[TARGET].mean()),
    }


def write_report(metadata: dict, path: Path) -> None:
    """Render exploration and evaluation as Markdown alongside machine-readable metadata."""
    lines = [
        "# Delay model — latest evaluation",
        "",
        f"Data source: **{'REAL BTS' if metadata['data_source'] == 'bts' else 'SYNTHETIC'}**",
        "",
        "SYNTHETIC DEMO ONLY — scores do not measure real-world performance."
        if metadata["data_source"] == "synthetic"
        else "BTS sample: completed, non-diverted US domestic reporting-carrier flights.",
        "",
        "## Time split",
        "",
    ]
    for name in ("train", "test"):
        split = metadata["split"][name]
        lines.append(
            f"- {name.title()}: {split['start']} to {split['end']}; "
            f"{split['rows']:,} flights; {split['delay_rate']:.1%} delayed."
        )
    lines += [
        "",
        "## Held-out scores",
        "",
        "Decision threshold: 0.5 (fixed before evaluation).",
        "",
        "| Model | Accuracy | Precision | Recall | ROC-AUC |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, scores in metadata["metrics"].items():
        values = ["undefined" if v is None else f"{v:.4f}" for v in scores.values()]
        lines.append(f"| {name} | " + " | ".join(values) + " |")
    model_scores = metadata["metrics"]["lightgbm"]
    baseline_scores = metadata["metrics"]["always_on_time"]
    difference = model_scores["accuracy"] - baseline_scores["accuracy"]
    lines += [
        "",
        f"Accuracy difference versus always-on-time: {difference * 100:+.3f} percentage points. "
        f"Recall at the fixed threshold: {model_scores['recall']:.2%}. "
        "A score above baseline ROC-AUC does not by itself make the default classifier useful.",
    ]
    lines += ["", "## Exploration", "", "| Month | Flights | Delay rate |", "|---|---:|---:|"]
    for month, stats in metadata["exploration"]["by_month"].items():
        lines.append(f"| {month} | {stats['rows']:,} | {stats['delay_rate']:.1%} |")
    lines += [
        "",
        f"Airlines: {metadata['exploration']['airlines']}; "
        f"routes: {metadata['exploration']['routes']}.",
        "",
        "## Interpretation and limits",
        "",
        "Always-on-time accuracy can be high simply because delays are uncommon. Compare recall "
        "and ROC-AUC as well; zero baseline recall means it never finds a delayed flight.",
        "",
        "These are uncalibrated model scores. One held-out month does not establish performance "
        "in other seasons or years. The model excludes cancellations/diversions and has no live "
        "weather, airport congestion, or aircraft rotation inputs. It should not be generalized "
        "to international flights. Synthetic results validate the pipeline only.",
        "",
        "Features: " + ", ".join(metadata["features"]) + ".",
        "",
        "Source and field definitions: https://transtats.bts.gov/Fields.asp?gnoyr_VQ=FGJ",
        "",
        DISCLAIMER,
        "",
    ]
    path.write_text("\n".join(lines))


def train_model(data_path: Path, output_dir: Path, seed: int = 42) -> dict:
    """Fit once, evaluate on future data, and persist the result with verified data provenance."""
    manifest_path = data_path.with_suffix(".metadata.json")
    if not manifest_path.exists():
        raise ValueError("Missing data manifest. Prepare a sample with python -m copilot.ml.data.")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("data_source") not in {"bts", "synthetic"}:
        raise ValueError("Data manifest must explicitly identify BTS or synthetic data.")
    if manifest.get("sha256") != file_sha256(data_path):
        raise ValueError("Dataset hash differs from its manifest. Rebuild the sample.")
    frame = pd.read_csv(data_path)
    required = set(FEATURES + [TARGET, "flight_date"])
    if required - set(frame.columns):
        raise ValueError(f"Missing prepared columns: {sorted(required - set(frame.columns))}")
    if frame[list(required)].isna().any().any() or not frame[TARGET].isin([0, 1]).all():
        raise ValueError("Prepared data must have complete features and binary targets.")
    train, test = split_by_month(frame)
    pipeline = build_pipeline(seed)
    pipeline.fit(train[FEATURES], train[TARGET])
    probabilities = pipeline.predict_proba(test[FEATURES])[:, 1]
    baseline = DummyClassifier(strategy="constant", constant=0)
    baseline.fit(train[FEATURES], train[TARGET])
    baseline_probabilities = baseline.predict_proba(test[FEATURES])[:, 1]
    monthly = frame.assign(month_key=pd.to_datetime(frame["flight_date"]).dt.strftime("%Y-%m"))
    metadata = {
        "model_type": "LightGBM",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_source": manifest["data_source"],
        "source": "real" if manifest["data_source"] == "bts" else "synthetic",
        "data_manifest": manifest,
        "data_sha256": manifest["sha256"],
        "features": FEATURES,
        "target": "arrival delay >= 15 minutes",
        "decision_threshold": 0.5,
        "seed": seed,
        "split": {
            "strategy": "last_calendar_month",
            "train": describe_split(train),
            "test": describe_split(test),
        },
        "metrics": {
            "lightgbm": classification_metrics(test[TARGET], probabilities),
            "always_on_time": classification_metrics(test[TARGET], baseline_probabilities),
        },
        "exploration": {
            "airlines": int(frame["airline"].nunique()),
            "routes": len(frame[["origin", "destination"]].drop_duplicates()),
            "by_month": {
                str(month): {"rows": len(group), "delay_rate": float(group[TARGET].mean())}
                for month, group in monthly.groupby("month_key")
            },
        },
        "versions": {
            package: version(package)
            for package in ["pandas", "scikit-learn", "lightgbm", "numpy", "joblib"]
        },
        "disclaimer": DISCLAIMER,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    # LEARN: Saving the entire pipeline preserves its learned category mapping.
    # A model saved without its encoder could interpret future inputs differently.
    # Joblib files execute Python when loaded: load only artifacts you trust.
    model_path = output_dir / "delay_model.joblib"
    joblib.dump(pipeline, model_path)
    metadata["model_sha256"] = file_sha256(model_path)
    (output_dir / "model_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    write_report(metadata, output_dir / "evaluation.md")
    return metadata


def main() -> None:
    """Expose a training command whose printed scores can be compared with the saved report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=settings.models_dir)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    metadata = train_model(args.data, args.output_dir, args.seed)
    print(f"Data source: {metadata['data_source'].upper()}")
    print(json.dumps(metadata["metrics"], indent=2))
    print(f"Saved model, metadata, and evaluation.md to {args.output_dir}")
    print(DISCLAIMER)


if __name__ == "__main__":
    main()
