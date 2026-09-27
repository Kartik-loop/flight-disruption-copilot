"""Exercise the ML pipeline's guarantees with tiny local data, never network downloads.

These tests focus on failure modes that can make an apparently successful model
misleading: leakage, time overlap, hidden synthetic data, and lost preprocessing.
"""

import json
from urllib.error import URLError
from zipfile import ZipFile

import pytest

# NOTE: The ML dependency group is optional. People studying only the rules
# engine can run its tests with [dev]; these tests run when [ml] is installed.
joblib = pytest.importorskip("joblib")
np = pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")
pytest.importorskip("sklearn")
pytest.importorskip("lightgbm")

from copilot.ml import data  # noqa: E402
from copilot.ml.train import (  # noqa: E402
    classification_metrics,
    split_by_month,
    train_model,
)


@pytest.fixture
def raw_rows():
    """Include unusable outcomes and clocks to verify that cleaning does not invent labels."""
    return pd.DataFrame({
        "FlightDate": ["2025-01-01"] * 7,
        "Reporting_Airline": ["UA"] * 7,
        "Origin": ["JFK"] * 7,
        "Dest": ["LAX"] * 7,
        "CRSDepTime": [700, 2400, 800, 900, 1000, 1260, 1200.5],
        "ArrDelay": [14, 15, None, 90, 30, 0, 0],
        "Cancelled": [0, 0, 0, 1, 0, 0, 0],
        "Diverted": [0, 0, 0, 0, 1, 0, 0],
        "DepDelay": [100] * 7,
        "WeatherDelay": [100] * 7,
    })


def test_cleaning_target_and_clock(raw_rows):
    """Missing outcomes must not become on-time labels, and 2400 means midnight."""
    clean = data.prepare_rows(raw_rows)
    assert clean[data.TARGET].tolist() == [0, 1]
    assert clean["scheduled_hour"].tolist() == [7, 0]
    assert clean["day_of_week"].tolist() == [2, 2]
    assert set(clean.columns) == {"flight_date", data.TARGET, *data.FEATURES}


def test_post_departure_fields_do_not_change_features(raw_rows):
    """Changing actual departure information must have no effect on model inputs."""
    original = data.prepare_rows(raw_rows)
    raw_rows["DepDelay"] = 999
    raw_rows["WeatherDelay"] = -999
    raw_rows["ArrDelay"] = 300
    changed = data.prepare_rows(raw_rows)
    pd.testing.assert_frame_equal(
        original[data.FEATURES], changed.loc[:1, data.FEATURES],
    )


def test_missing_raw_columns_raise(raw_rows):
    """A changed source schema should stop preparation instead of silently guessing columns."""
    with pytest.raises(ValueError, match="Missing BTS columns"):
        data.prepare_rows(raw_rows.drop(columns="FlightDate"))


def test_uniform_sample_reads_beyond_first_chunk(tmp_path):
    """BTS file order must not confine the sample to the first airline or day."""
    count = 50_100
    raw = pd.DataFrame({
        "FlightDate": ["2025-01-01"] * 50_000 + ["2025-01-31"] * 100,
        "Reporting_Airline": ["UA"] * count, "Origin": ["JFK"] * count,
        "Dest": ["LAX"] * count, "CRSDepTime": [900] * count,
        "ArrDelay": [15] * count, "Cancelled": [0] * count, "Diverted": [0] * count,
    })
    archive = tmp_path / "sample.zip"
    with ZipFile(archive, "w") as output:
        output.writestr("flights.csv", raw.to_csv(index=False))
    sample, counts = data.sample_archive(archive, rows=5_000, seed=42)
    repeated, _ = data.sample_archive(archive, rows=5_000, seed=42)
    assert len(sample) == 5_000
    assert counts["raw_rows"] == count
    assert sample["flight_date"].max() == pd.Timestamp("2025-01-31")
    pd.testing.assert_frame_equal(sample, repeated)


def blocked_download(*args, **kwargs):
    """Simulate an unavailable BTS server without depending on internet access in tests."""
    raise URLError("BTS unavailable in test")


def test_fallback_is_explicit_and_reproducible(tmp_path, monkeypatch):
    """Network failure must produce a visibly synthetic dataset only when explicitly enabled."""
    monkeypatch.setattr(data, "download_month", blocked_download)
    with pytest.raises(RuntimeError, match="download failed"):
        data.build_dataset(tmp_path, rows_per_month=50)
    path = data.build_dataset(tmp_path, rows_per_month=50, allow_synthetic=True)
    manifest = json.loads(path.with_suffix(".metadata.json").read_text())
    assert path.name == "synthetic_sample.csv"
    assert manifest["data_source"] == "synthetic"
    assert manifest["synthetic"] is True
    assert manifest["archives"] == []
    assert "BTS unavailable" in manifest["fallback_reason"]
    assert manifest["sha256"] == data.file_sha256(path)
    pd.testing.assert_frame_equal(
        data.synthetic_month(2025, 1, 50, 42), data.synthetic_month(2025, 1, 50, 42),
    )


def test_fallback_does_not_hide_invalid_archives(tmp_path, monkeypatch):
    """Schema or data corruption must remain a failure even when network fallback is allowed."""
    def invalid_archive(*args, **kwargs):
        """Represent a server response with the wrong data rather than a network outage."""
        raise ValueError("Invalid BTS archive")

    monkeypatch.setattr(data, "download_month", invalid_archive)
    with pytest.raises(ValueError, match="Invalid BTS archive"):
        data.build_dataset(tmp_path, allow_synthetic=True)


def test_time_split_is_strictly_ordered():
    """Shuffled input still must keep the entire last month out of training."""
    frame = pd.concat([data.synthetic_month(2025, m, 200, m) for m in (1, 2, 3)])
    train, test = split_by_month(frame.sample(frac=1, random_state=42))
    assert train["flight_date"].max() < test["flight_date"].min()
    assert set(train["month"]) == {1, 2}
    assert set(test["month"]) == {3}


def test_split_rejects_one_month_and_one_training_class():
    """An uninformative split should fail before fitting or claiming evaluation success."""
    frame = data.synthetic_month(2025, 1, 200, 42)
    with pytest.raises(ValueError, match="two calendar months"):
        split_by_month(frame)
    frame = pd.concat([frame, data.synthetic_month(2025, 2, 200, 42)])
    frame.loc[frame["month"] == 1, data.TARGET] = 0
    with pytest.raises(ValueError, match="both delayed and on-time"):
        split_by_month(frame)


def test_baseline_and_undefined_auc():
    """An always-on-time classifier has zero delay recall; one-class ROC-AUC is undefined."""
    scores = classification_metrics(pd.Series([0, 0, 0, 1]), np.zeros(4))
    assert scores == {"accuracy": 0.75, "precision": 0.0, "recall": 0.0, "roc_auc": 0.5}
    assert classification_metrics(pd.Series([0, 0]), np.zeros(2))["roc_auc"] is None


def test_training_artifacts_reload_and_provenance(tmp_path, monkeypatch):
    """A saved pipeline must predict with unseen categories and preserve its synthetic label."""
    monkeypatch.setattr(data, "download_month", blocked_download)
    path = data.build_dataset(tmp_path / "data", rows_per_month=250, allow_synthetic=True)
    output = tmp_path / "models"
    metadata = train_model(path, output)
    model = joblib.load(output / "delay_model.joblib")
    inputs = data.synthetic_month(2025, 4, 5, 42)[data.FEATURES]
    inputs["airline"] = "UNSEEN"
    probabilities = model.predict_proba(inputs)[:, 1]
    assert len(probabilities) == 5
    assert np.isfinite(probabilities).all()
    assert ((probabilities >= 0) & (probabilities <= 1)).all()
    encoder = model.named_steps["preprocess"].named_transformers_["categories"]
    assert "UNSEEN" not in encoder.categories_[0]
    assert metadata["data_source"] == "synthetic"
    assert metadata["features"] == data.FEATURES
    assert metadata["model_sha256"] == data.file_sha256(output / "delay_model.joblib")
    assert "SYNTHETIC DEMO ONLY" in (output / "evaluation.md").read_text()
    saved_metadata = json.loads((output / "model_metadata.json").read_text())
    assert saved_metadata["metrics"] == metadata["metrics"]

    # LEARN: A filename is not provenance. Changing the dataset without updating
    # its manifest must be detected before a second model can claim that source.
    with path.open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="hash differs"):
        train_model(path, output)
