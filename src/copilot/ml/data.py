"""Download and prepare a small BTS sample for the delay-model learning exercise.

The downloader keeps monthly ZIP files locally and reads them in chunks so a
laptop need not hold the full BTS table in memory. Synthetic fallback is opt-in,
clearly recorded, and replaces the entire sample rather than mixing sources.

Sources: https://transtats.bts.gov/PREZIP/
Field definitions: https://transtats.bts.gov/Fields.asp?gnoyr_VQ=FGJ
"""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from zipfile import ZipFile

import numpy as np
import pandas as pd

from copilot.config import settings

BTS_BASE_URL = "https://transtats.bts.gov/PREZIP/"
RAW_COLUMNS = [
    "FlightDate", "Reporting_Airline", "Origin", "Dest", "CRSDepTime",
    "ArrDelay", "Cancelled", "Diverted",
]
CATEGORICAL_FEATURES = ["airline", "origin", "destination"]
NUMERIC_FEATURES = ["scheduled_hour", "day_of_week", "month"]
FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES
TARGET = "arrival_delayed"
DISCLAIMER = "This is not legal advice. Delay predictions do not determine compensation rights."


def file_sha256(path: Path) -> str:
    """Fingerprint an input file so a saved model can be traced to its exact sample."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download_month(year: int, month: int, raw_dir: Path) -> Path:
    """Cache one official monthly archive, without treating a partial download as complete."""
    name = f"On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / name
    if path.exists():
        return path

    request = Request(BTS_BASE_URL + name, headers={"User-Agent": "FlightCopilot-Learning/0.1"})
    partial = path.with_suffix(".zip.part")
    try:
        with urlopen(request, timeout=45) as response, partial.open("wb") as output:
            total = 0
            while block := response.read(1024 * 1024):
                total += len(block)
                if total > 200 * 1024 * 1024:
                    raise ValueError("BTS archive exceeds the 200 MB download limit.")
                output.write(block)
        # NOTE: Open the ZIP before promoting it to the cache. Some servers return
        # an HTML error page with HTTP 200; it must never become a training file.
        with ZipFile(partial) as archive:
            if not any(name.lower().endswith(".csv") for name in archive.namelist()):
                raise ValueError("BTS archive contains no CSV file.")
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)
    return path


def prepare_rows(raw: pd.DataFrame) -> pd.DataFrame:
    """Build an explicit feature allowlist so post-flight information cannot leak into training."""
    missing = set(RAW_COLUMNS) - set(raw.columns)
    if missing:
        raise ValueError(f"Missing BTS columns: {sorted(missing)}")

    dates = pd.to_datetime(raw["FlightDate"], errors="coerce")
    scheduled = pd.to_numeric(raw["CRSDepTime"], errors="coerce")
    arrival_delay = pd.to_numeric(raw["ArrDelay"], errors="coerce")
    cancelled = pd.to_numeric(raw["Cancelled"], errors="coerce")
    diverted = pd.to_numeric(raw["Diverted"], errors="coerce")
    # LEARN: Actual departure delay is unavailable when someone plans a flight.
    # Including it would give training access to the future, making evaluation
    # misleading. ArrDelay is used ONLY to construct the answer (the target).
    result = pd.DataFrame({
        "flight_date": dates,
        "airline": raw["Reporting_Airline"].astype("string").str.strip().str.upper(),
        "origin": raw["Origin"].astype("string").str.strip().str.upper(),
        "destination": raw["Dest"].astype("string").str.strip().str.upper(),
        "scheduled_hour": (scheduled // 100) % 24,
        "day_of_week": dates.dt.dayofweek,
        "month": dates.dt.month,
        TARGET: (arrival_delay >= 15).astype(int),
    })
    # NOTE: Missing arrival outcomes, cancellations, and diversions are not
    # "on time". Excluding them makes this a completed-flight delay model,
    # not a predictor of every possible disruption.
    valid_clock = (
        (scheduled.between(0, 2359) & ((scheduled % 100) < 60)) | (scheduled == 2400)
    ) & (scheduled % 1 == 0)
    valid = (
        cancelled.eq(0) & diverted.eq(0) & np.isfinite(arrival_delay)
        & dates.notna() & valid_clock
    )
    for column in CATEGORICAL_FEATURES:
        valid &= result[column].notna() & result[column].ne("")
    result = result.loc[valid].copy()
    result[NUMERIC_FEATURES] = result[NUMERIC_FEATURES].astype(int)
    return result.reset_index(drop=True)


def sample_archive(path: Path, rows: int, seed: int) -> tuple[pd.DataFrame, dict]:
    """Sample uniformly across the whole month instead of taking the first flights in the file."""
    rng = np.random.default_rng(seed)
    kept = pd.DataFrame()
    raw_count = clean_count = 0
    with ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(names) != 1:
            raise ValueError("Expected exactly one BTS CSV in the archive.")
        with archive.open(names[0]) as stream:
            for chunk in pd.read_csv(stream, usecols=RAW_COLUMNS, chunksize=50_000):
                raw_count += len(chunk)
                clean = prepare_rows(chunk)
                clean_count += len(clean)
                # LEARN: Give each valid row a random priority and keep the smallest
                # priorities seen so far. Every row has the same chance of selection,
                # even when BTS sorts the file by airline rather than date.
                clean["_priority"] = rng.random(len(clean))
                kept = pd.concat([kept, clean], ignore_index=True).nsmallest(rows, "_priority")
    if kept.empty:
        raise ValueError(f"No usable completed flights in {path.name}.")
    return kept.drop(columns="_priority"), {
        "raw_rows": raw_count, "usable_rows": clean_count, "sample_rows": len(kept),
    }


def synthetic_month(year: int, month: int, rows: int, seed: int) -> pd.DataFrame:
    """Create reproducible teaching data; its metrics are never evidence about real flights."""
    rng = np.random.default_rng(seed)
    days = pd.date_range(f"{year}-{month:02d}-01", periods=1)[0].days_in_month
    dates = pd.to_datetime({
        "year": np.full(rows, year), "month": np.full(rows, month),
        "day": rng.integers(1, days + 1, rows),
    })
    airports = np.array(["JFK", "LAX", "ORD", "ATL", "DFW", "SFO"])
    origins = rng.integers(0, len(airports), rows)
    destinations = (origins + rng.integers(1, len(airports), rows)) % len(airports)
    hours = rng.integers(5, 24, rows)
    airlines = rng.choice(["UA", "DL", "AA", "WN"], rows)
    # NOTE: These invented relationships make a learnable exercise, not a
    # simulation validated against aviation data. Do not interpret them as facts.
    score = -2.3 + 0.14 * (hours - 5) + 0.55 * (origins == 2) + 0.35 * (airlines == "UA")
    delayed = rng.random(rows) < 1 / (1 + np.exp(-score))
    return prepare_rows(pd.DataFrame({
        "FlightDate": dates, "Reporting_Airline": airlines,
        "Origin": airports[origins], "Dest": airports[destinations],
        "CRSDepTime": hours * 100, "ArrDelay": np.where(delayed, 30, 0),
        "Cancelled": 0, "Diverted": 0,
    }))


def build_dataset(
    data_dir: Path, year: int = 2025, months: tuple[int, ...] = (1, 2, 3),
    rows_per_month: int = 20_000, seed: int = 42, allow_synthetic: bool = False,
) -> Path:
    """Save a sampled dataset and provenance together so fallback cannot be hidden from training."""
    months = tuple(sorted(set(months)))
    if not 1988 <= year <= 2100 or not months or any(not 1 <= m <= 12 for m in months):
        raise ValueError("Choose a year from 1988 to 2100 and months from 1 to 12.")
    if rows_per_month < 1:
        raise ValueError("rows_per_month must be positive.")
    frames, sources = [], []
    source, fallback_reason = "bts", None
    try:
        for month in months:
            print(f"Downloading/reading BTS {year}-{month:02d}...", flush=True)
            path = download_month(year, month, data_dir / "raw")
            frame, counts = sample_archive(path, rows_per_month, seed + month)
            if not (frame["flight_date"].dt.to_period("M") == f"{year}-{month:02d}").all():
                raise ValueError(f"Unexpected dates in {path.name}.")
            frames.append(frame)
            sources.append({"url": BTS_BASE_URL + path.name, "sha256": file_sha256(path), **counts})
    except (URLError, TimeoutError, socket.timeout) as exc:
        if not allow_synthetic:
            raise RuntimeError(
                "BTS download failed. Retry, or use --allow-synthetic for labelled teaching data."
            ) from exc
        source, fallback_reason = "synthetic", str(exc)
        print(f"WARNING: BTS unavailable ({exc}). Entire dataset will be SYNTHETIC.", flush=True)
        frames = [synthetic_month(year, month, rows_per_month, seed + month) for month in months]
        sources = []

    frame = pd.concat(frames, ignore_index=True).sort_values("flight_date").reset_index(drop=True)
    output_dir = data_dir / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{source}_sample.csv"
    frame.to_csv(path, index=False)
    manifest = {
        "data_source": source, "synthetic": source == "synthetic",
        "fallback_reason": fallback_reason, "year": year, "months": list(months),
        "seed": seed, "rows_per_month": rows_per_month, "rows": len(frame),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sha256": file_sha256(path), "archives": sources,
        "population": "Completed, non-diverted US domestic reporting-carrier flights",
    }
    path.with_suffix(".metadata.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Saved {len(frame):,} rows to {path} (source={source}).")
    return path


def main() -> None:
    """Provide a repeatable download command without requiring a notebook or API key."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--months", type=int, nargs="+", default=[1, 2, 3])
    parser.add_argument("--rows-per-month", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data-dir", type=Path, default=settings.data_dir)
    parser.add_argument("--allow-synthetic", action="store_true")
    args = parser.parse_args()
    build_dataset(
        args.data_dir, args.year, tuple(args.months), args.rows_per_month,
        args.seed, args.allow_synthetic,
    )
    print(DISCLAIMER)


if __name__ == "__main__":
    main()
