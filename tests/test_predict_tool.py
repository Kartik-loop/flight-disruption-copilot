"""Check provenance, scope, and feature consistency at the trained-model tool boundary.

A tiny locally trained artifact exercises actual model loading and prediction.
No test depends on the developer's saved model or downloads external flight data.
"""

import json
import shutil
from datetime import date, datetime

import pytest

pytest.importorskip("lightgbm")
pd = pytest.importorskip("pandas")

from copilot.ml.data import file_sha256, synthetic_month  # noqa: E402
from copilot.ml.predict import PredictionUnavailableError, predict_delay  # noqa: E402
from copilot.ml.train import train_model  # noqa: E402
from copilot.schemas.flight import FlightInfo  # noqa: E402


@pytest.fixture(scope="module")
def model_dir(tmp_path_factory):
    """Train once on tiny synthetic data so tests verify the real serialization contract."""
    root = tmp_path_factory.mktemp("prediction-model")
    frame = pd.concat([synthetic_month(2025, month, 250, month) for month in (1, 2, 3)])
    path = root / "sample.csv"
    frame.to_csv(path, index=False)
    path.with_suffix(".metadata.json").write_text(
        json.dumps(
            {
                "data_source": "synthetic",
                "sha256": file_sha256(path),
            }
        )
    )
    train_model(path, root / "models")
    return root / "models"


def us_flight(**changes):
    """Use a supported domestic route and explicitly local scheduled departure time."""
    values = dict(
        airline="UA",
        departure_airport="JFK",
        arrival_airport="LAX",
        flight_date=date(2025, 4, 1),
        scheduled_departure=datetime(2025, 4, 1, 9, 30),
    )
    values.update(changes)
    return FlightInfo(**values)


def test_synthetic_requires_opt_in_and_keeps_label(model_dir):
    """A teaching model must never silently appear as a real travel-risk estimate."""
    with pytest.raises(PredictionUnavailableError, match="SYNTHETIC"):
        predict_delay(us_flight(), models_dir=model_dir)
    result = predict_delay(us_flight(), models_dir=model_dir, allow_synthetic=True)
    assert result.data_source == "synthetic"
    assert 0 <= result.probability_delayed <= 1
    assert result.features_used["scheduled_hour"] == "9"
    assert "SYNTHETIC DEMO ONLY" in result.limitations[0]


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"arrival_airport": "CDG"}, "US domestic"),
        ({"scheduled_departure": None}, "local time"),
        ({"flight_date": date(2025, 4, 2)}, "disagree"),
        ({"airline": "United Airlines"}, "training coverage"),
    ],
)
def test_unsupported_or_ambiguous_features_are_not_guessed(model_dir, changes, match):
    """Do not invent airline mappings, missing hours, or international-model applicability."""
    with pytest.raises(PredictionUnavailableError, match=match):
        predict_delay(us_flight(**changes), models_dir=model_dir, allow_synthetic=True)


def test_missing_model_and_mismatched_hash(tmp_path, model_dir):
    """Missing or accidentally corrupted artifacts must fail before deserialization."""
    with pytest.raises(PredictionUnavailableError, match="missing"):
        predict_delay(us_flight(), models_dir=tmp_path)
    copied = tmp_path / "corrupt"
    shutil.copytree(model_dir, copied)
    (copied / "delay_model.joblib").write_bytes(b"not a model")
    with pytest.raises(PredictionUnavailableError, match="do not match"):
        predict_delay(us_flight(), models_dir=copied, allow_synthetic=True)
