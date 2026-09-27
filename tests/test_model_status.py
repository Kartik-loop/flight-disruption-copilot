"""Ensure provenance banners never advertise synthetic or missing artifacts as real data."""

import hashlib
import json

import pytest

from copilot.api.status import model_status


@pytest.mark.parametrize("source,label", [("bts", "REAL BTS"), ("synthetic", "SYNTHETIC DEMO")])
def test_verified_status(tmp_path, source, label):
    """A banner should be derived from a matching saved pair without executing model bytes."""
    blob = b"not executable model data"
    (tmp_path / "delay_model.joblib").write_bytes(blob)
    (tmp_path / "model_metadata.json").write_text(
        json.dumps(
            {
                "data_source": source,
                "model_sha256": hashlib.sha256(blob).hexdigest(),
            }
        )
    )
    status = model_status(tmp_path)
    assert status.available
    assert status.data_source == source
    assert label in status.message


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        "broken JSON",
        "[]",
        '{"data_source":"real"}',
        '{"data_source":"bts","model_sha256":"wrong"}',
    ],
)
def test_unavailable_status(tmp_path, metadata):
    """Missing, invalid or mismatched provenance must produce an unknown banner, not a guess."""
    if metadata is not None:
        (tmp_path / "model_metadata.json").write_text(metadata)
    (tmp_path / "delay_model.joblib").write_bytes(b"different model")
    status = model_status(tmp_path)
    assert not status.available
    assert status.data_source == "unknown"
