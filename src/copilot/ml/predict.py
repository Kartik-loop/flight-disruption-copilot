"""Expose a trained local delay model as a guarded tool for the predictor specialist.

The model is optional context, never evidence for compensation. Its training
source and limitations travel with the score so a synthetic demo cannot become
an apparently real travel forecast when wrapped by an agent.
"""

import hashlib
import json
from pathlib import Path

from copilot.config import get_settings
from copilot.rules.airports import is_us_airport
from copilot.schemas.flight import DelayPrediction, FlightInfo


class PredictionUnavailableError(ValueError):
    """Explain an expected missing capability without failing the eligibility workflow."""


def predict_delay(
    flight: FlightInfo,
    *,
    models_dir: Path | None = None,
    allow_synthetic: bool = False,
) -> DelayPrediction:
    """Validate model provenance and input scope before returning a labelled probability."""
    root = models_dir or get_settings().models_dir
    model_path, metadata_path = root / "delay_model.joblib", root / "model_metadata.json"
    if not model_path.exists() or not metadata_path.exists():
        raise PredictionUnavailableError("Delay model is missing. Run phase-3 training first.")
    if not (is_us_airport(flight.departure_airport) and is_us_airport(flight.arrival_airport)):
        raise PredictionUnavailableError(
            "The delay model supports known US domestic airports only."
        )
    if flight.scheduled_departure is None:
        raise PredictionUnavailableError(
            "Prediction needs the scheduled departure-airport local time."
        )
    if flight.scheduled_departure.date() != flight.flight_date:
        raise PredictionUnavailableError("Scheduled local departure and flight date disagree.")
    metadata = json.loads(metadata_path.read_text())
    source = metadata.get("data_source")
    if source not in {"bts", "synthetic"}:
        raise PredictionUnavailableError("Model metadata has no supported data-source label.")
    if source == "synthetic" and not allow_synthetic:
        raise PredictionUnavailableError(
            "The saved model is SYNTHETIC. Enable the explicit demo option to see a teaching score."
        )
    with model_path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != metadata.get("model_sha256"):
            raise PredictionUnavailableError("Model and metadata do not match. Retrain the model.")
    # LEARN: Lazy imports let the rest of the copilot work without the optional
    # ML packages. The hash detects accidental mismatches, not malicious pickle
    # files: only load artifacts trained locally or from a trusted source.
    try:
        import joblib
        import pandas as pd

        from copilot.ml.data import FEATURES
    except ImportError as exc:
        raise PredictionUnavailableError(
            "Install the [ml] dependency group for delay prediction."
        ) from exc
    if metadata.get("features") != FEATURES:
        raise PredictionUnavailableError("The saved model uses a different feature contract.")
    pipeline = joblib.load(model_path)
    features = {
        "airline": flight.airline.strip().upper(),
        "origin": flight.departure_airport,
        "destination": flight.arrival_airport,
        "scheduled_hour": flight.scheduled_departure.hour,
        "day_of_week": flight.flight_date.weekday(),
        "month": flight.flight_date.month,
    }
    categories = pipeline.named_steps["preprocess"].named_transformers_["categories"].categories_
    for name, known in zip(["airline", "origin", "destination"], categories, strict=True):
        if features[name] not in known:
            raise PredictionUnavailableError(f"No training coverage for {name}: {features[name]}.")
    probability = float(pipeline.predict_proba(pd.DataFrame([features])[FEATURES])[0, 1])
    # NOTE: These bands are UI labels, not calibrated statistical guarantees.
    # TODO(next): Calibrate on a separate later validation period before travel use.
    risk = "low" if probability < 0.2 else "medium" if probability < 0.5 else "high"
    limitations = [
        "Uncalibrated score from a small historical sample; no live weather or airport data.",
        "Only completed, non-diverted US domestic flights were used in training.",
        "Individual categories were seen in training; route combinations may still be unseen.",
        "Delay probability does not establish compensation rights.",
    ]
    if source == "synthetic":
        limitations.insert(0, "SYNTHETIC DEMO ONLY: not a real-world flight-risk estimate.")
    return DelayPrediction(
        probability_delayed=probability,
        risk_level=risk,
        data_source=source,
        features_used={key: str(value) for key, value in features.items()},
        limitations=limitations,
    )
