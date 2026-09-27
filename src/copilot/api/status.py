"""Report saved-model provenance without loading executable model files or contacting an LLM."""

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from copilot.config import get_settings
from copilot.schemas.flight import DISCLAIMER


class ModelStatus(BaseModel):
    """Give every interface an explicit source label, including when no model is usable."""

    available: bool = False
    data_source: Literal["bts", "synthetic", "unknown"] = "unknown"
    message: str = "Delay model unavailable. Train a model before requesting a prediction."
    disclaimer: str = DISCLAIMER


def model_status(models_dir: Path | None = None) -> ModelStatus:
    """Check the saved artifact pair so stale metadata cannot advertise a different model."""
    root = models_dir or get_settings().models_dir
    try:
        metadata = json.loads((root / "model_metadata.json").read_text())
        if not isinstance(metadata, dict):
            return ModelStatus()
        source = metadata.get("data_source")
        if source not in {"bts", "synthetic"}:
            return ModelStatus()
        with (root / "delay_model.joblib").open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != metadata.get("model_sha256"):
            return ModelStatus(message="Model files do not match. Retrain before predicting.")
    except (OSError, ValueError):
        return ModelStatus()
    # LEARN: This reads bytes to check provenance; it never unpickles the model.
    # A matching hash detects accidental mismatches, not a malicious artifact.
    # The source label describes training data, not forecast quality or calibration.
    message = (
        "REAL BTS DATA — trained on a historical US domestic sample. "
        "Uncalibrated estimates, not a live flight forecast."
        if source == "bts"
        else "SYNTHETIC DEMO ONLY — predictions do not measure real-world flight risk."
    )
    return ModelStatus(available=True, data_source=source, message=message)
