"""Generate an explicitly synthetic, complete calculator input for reproducibility."""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from field_calculator import SCORE_GROUPS  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Write JSON; defaults to stdout")
    args = parser.parse_args()
    observations = {}
    for group, weights in SCORE_GROUPS.items():
        for name in weights:
            observations[name] = {
                "value": 0.5,
                "unit": "normalized_fraction",
                "confidence": 0.5,
                "evidence_class": (
                    "self_reported" if group == "HLI"
                    else "interpretive" if group in {"OC", "IR"}
                    else "measured"
                ),
            }
    payload = {
        "context": {
            "created_at": "2026-10-21T12:00:00Z",
            "location": "synthetic-scenario-no-real-person-or-place",
            "source": "synthetic_scenario_not_instrument_data",
            "source_class": "synthetic",
        },
        "observations": observations,
        "symbolic_notes": [
            {"evidence_class": "symbolic", "text": "Demonstration only; excluded from scores."}
        ],
    }
    result = json.dumps(payload, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
