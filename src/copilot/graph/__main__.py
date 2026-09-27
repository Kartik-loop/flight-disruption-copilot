"""Run phase 4 from a terminal before the API and UI exist.

JSON form files run offline; free text uses the configured provider. Outputs are
the same typed response the later API will serialize, including all disclaimers.
"""

import argparse
from pathlib import Path

from pydantic import ValidationError

from copilot.graph.workflow import run_copilot
from copilot.schemas.flight import CopilotResponse, FlightDisruption
from copilot.schemas.requests import CopilotRequest


def main() -> None:
    """Make input and demo options explicit so network and data-source use stay visible."""
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text")
    group.add_argument("--file", type=Path, help="JSON FlightDisruption object")
    parser.add_argument("--predict", action="store_true")
    parser.add_argument("--no-letter", action="store_true")
    parser.add_argument("--allow-synthetic-prediction", action="store_true")
    args = parser.parse_args()
    try:
        disruption = (
            FlightDisruption.model_validate_json(args.file.read_text()) if args.file else None
        )
        response = run_copilot(
            CopilotRequest(
                text=args.text,
                disruption=disruption,
                want_prediction=args.predict,
                want_letter=not args.no_letter,
                allow_synthetic_prediction=args.allow_synthetic_prediction,
            )
        )
    except (ValidationError, OSError):
        response = CopilotResponse(
            status="error",
            warnings=[
                "Input is invalid or unreadable. Check the JSON file and required flight fields."
            ],
        )
    print(response.model_dump_json(indent=2))
    if response.status == "error":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
