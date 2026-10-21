"""SOVRINT Field Calculator v1: provenance-aware, deterministic prototype.

Implements APPLICATIONS/SOVRINT_FIELD_CALCULATOR/CALCULATION_SPEC_v1.yaml.
All inputs are normalized or explicitly converted to [0,1]. The resulting
scores are proposed software indices, not physical or medical measurements.
No network, telemetry, persistence, or high-impact automation is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

VERSION = "1.0.0"
ARTIFACT_ID = "SOVRINT-FIELD-CALC-001"
SPEC_PATH = Path(__file__).with_name("CALCULATION_SPEC_v1.yaml")

# These weights reproduce CALCULATION_SPEC_v1.yaml exactly.
EAS_WEIGHTS = {
    "pressure_change": 0.15,
    "wind_intensity": 0.10,
    "precipitation_severity": 0.10,
    "temperature_stress": 0.10,
    "humidity_stress": 0.10,
    "air_quality_severity": 0.15,
    "geomagnetic_activity": 0.15,
    "solar_alert_severity": 0.15,
}
TSS_WEIGHTS = {
    "packet_loss": 0.20,
    "latency_deviation": 0.20,
    "rf_noise_elevation": 0.20,
    "outage_severity": 0.15,
    "gnss_degradation": 0.10,
    "equipment_anomaly_rate": 0.15,
}
HLI_WEIGHTS = {
    "sleep_debt": 0.30,
    "cognitive_load": 0.25,
    "emotional_load": 0.20,
    "physical_stress": 0.15,
    "attentional_fragmentation": 0.10,
}
OC_WEIGHTS = {
    "source_quality": 0.40,
    "data_recency": 0.25,
    "layer_coverage": 0.20,
    "source_agreement": 0.15,
}
IR_WEIGHTS = {
    "evidence_gap": 0.35,
    "human_load": 0.25,  # computed from HLI; do not permit a duplicate user input
    "anomaly_density": 0.20,
    "source_disagreement": 0.20,
}
FCS_WEIGHTS = {
    "environmental_stability": 0.30,
    "technical_stability": 0.25,
    "human_readiness": 0.20,
    "observability_confidence": 0.25,
}
SCORE_GROUPS = {
    "EAS": EAS_WEIGHTS,
    "TSS": TSS_WEIGHTS,
    "HLI": HLI_WEIGHTS,
    "OC": OC_WEIGHTS,
    "IR": {k: v for k, v in IR_WEIGHTS.items() if k != "human_load"},
}
EXPECTED_INPUTS = {
    field: group for group, weights in SCORE_GROUPS.items() for field in weights
}
ALLOWED_EVIDENCE = {
    "EAS": {"measured"},
    "TSS": {"measured"},
    "HLI": {"measured", "self_reported"},
    "OC": {"measured", "interpretive"},
    "IR": {"measured", "interpretive"},
}
BANDS = (
    (0, 19, "CRITICAL_INSTABILITY"),
    (20, 39, "HIGH_DISTURBANCE"),
    (40, 59, "MIXED_TRANSITIONAL"),
    (60, 79, "STABLE_WITH_ACTIVE_VARIABLES"),
    (80, 100, "HIGH_COHERENCE"),
)


class CalculationError(ValueError):
    """Raised on incomplete, ambiguous or unsupported calculator inputs."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalculationError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise CalculationError(f"{label} must be finite")
    return result


def _unit_interval(value: Any, label: str) -> float:
    result = _number(value, label)
    if not 0.0 <= result <= 1.0:
        raise CalculationError(f"{label} must be in [0,1]")
    return result


def _utc_timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CalculationError(f"{label} must be an ISO-8601 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise CalculationError(f"{label} is not a valid UTC timestamp") from exc
    if parsed.utcoffset().total_seconds() != 0:
        raise CalculationError(f"{label} must be UTC")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CalculationError(f"{label} must be a nonempty string")
    return value


def normalize(record: dict[str, Any], name: str) -> float:
    """Normalized inputs use 'value'; raw inputs use raw/minimum/maximum."""
    has_value = "value" in record
    has_raw = any(key in record for key in ("raw", "minimum", "maximum"))
    if has_value == has_raw:
        raise CalculationError(f"{name}: supply value OR raw/minimum/maximum")
    if has_value:
        return _unit_interval(record["value"], f"{name}.value")
    if not all(key in record for key in ("raw", "minimum", "maximum")):
        raise CalculationError(f"{name}: raw, minimum and maximum are all required")
    raw = _number(record["raw"], f"{name}.raw")
    minimum = _number(record["minimum"], f"{name}.minimum")
    maximum = _number(record["maximum"], f"{name}.maximum")
    if maximum <= minimum:
        raise CalculationError(f"{name}: maximum must exceed minimum")
    return max(0.0, min(1.0, (raw - minimum) / (maximum - minimum)))


def weighted(values: dict[str, float], weights: dict[str, float]) -> float:
    total = sum(weights.values())
    if total <= 0:
        raise CalculationError("weights must have a positive sum")
    return sum(values[name] * w for name, w in weights.items()) / total


def classify(score: float) -> str:
    # YAML bands use integer endpoints; floor fills otherwise ambiguous decimal gaps.
    bucket = min(100, math.floor(score))
    for minimum, maximum, label in BANDS:
        if minimum <= bucket <= maximum:
            return label
    raise CalculationError("calculated score outside expected classification bands")


def calculate(payload: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic scores, decompositions and provenance.

    No generation-time clock is embedded: identical input and code replay
    produces identical output. All output evidence classes remain visible.
    """
    if not isinstance(payload, dict):
        raise CalculationError("input must be a JSON object")
    if set(payload) - {"context", "observations", "symbolic_notes"}:
        raise CalculationError("unknown top-level input fields")
    context = payload.get("context")
    provided = payload.get("observations")
    if not isinstance(context, dict) or not isinstance(provided, dict):
        raise CalculationError("context and observations must be objects")
    created = _utc_timestamp(context.get("created_at"), "context.created_at")
    location = _text(context.get("location"), "context.location")
    default_source = _text(context.get("source"), "context.source")
    default_source_class = _text(context.get("source_class"), "context.source_class")

    expected, actual = set(EXPECTED_INPUTS), set(provided)
    if expected != actual:
        raise CalculationError(
            f"observation keys mismatch: missing={sorted(expected - actual)} "
            f"unknown={sorted(actual - expected)}"
        )

    values: dict[str, float] = {}
    observation_records: dict[str, dict[str, Any]] = {}
    for name in EXPECTED_INPUTS:
        item = provided[name]
        if not isinstance(item, dict):
            raise CalculationError(f"{name} must be an object")
        group = EXPECTED_INPUTS[name]
        evidence = item.get("evidence_class")
        if not isinstance(evidence, str) or evidence not in ALLOWED_EVIDENCE[group]:
            raise CalculationError(
                f"{name} ({group}): evidence_class must be one of "
                f"{sorted(ALLOWED_EVIDENCE[group])}; symbolic inputs never score"
            )
        source = _text(item.get("source", default_source), f"{name}.source")
        source_class = _text(item.get("source_class", default_source_class), f"{name}.source_class")
        source_url = item.get("source_url")
        if source_url is not None and not isinstance(source_url, str):
            raise CalculationError(f"{name}.source_url must be string or null")
        notes = item.get("user_notes", "")
        if not isinstance(notes, str):
            raise CalculationError(f"{name}.user_notes must be string")
        unit = _text(item.get("unit", "normalized_fraction"), f"{name}.unit")
        observed_at = _utc_timestamp(item.get("created_at", created), f"{name}.created_at")
        retrieved_at = _utc_timestamp(item.get("retrieved_at", created), f"{name}.retrieved_at")
        confidence = item.get("confidence")
        confidence = None if confidence is None else _unit_interval(confidence, f"{name}.confidence")
        value = normalize(item, name)
        values[name] = value
        basis = {"field": name, "input": item, "context": context}
        observation_records[name] = {
            "observation_id": sha256_bytes(canonical_json(basis).encode("utf-8"))[:24],
            "created_at": observed_at,
            "location": location,
            "layer": group,
            "value": value,
            "unit": unit,
            "source": source,
            "source_url": source_url,
            "source_class": source_class,
            "retrieved_at": retrieved_at,
            "confidence": confidence,
            "evidence_class": evidence,
            "user_notes": notes,
            "calculation_version": VERSION,
        }
        if "raw" in item:
            observation_records[name]["raw_input"] = {
                key: item[key] for key in ("raw", "minimum", "maximum")
            }

    symbolic_notes = payload.get("symbolic_notes", [])
    if not isinstance(symbolic_notes, list):
        raise CalculationError("symbolic_notes must be a list")
    for note in symbolic_notes:
        if not isinstance(note, dict) or note.get("evidence_class") != "symbolic":
            raise CalculationError("each symbolic note must have evidence_class='symbolic'")
        _text(note.get("text"), "symbolic note text")

    eas = 100 * weighted(values, EAS_WEIGHTS)
    tss = 100 * (1 - weighted(values, TSS_WEIGHTS))
    hli = 100 * weighted(values, HLI_WEIGHTS)
    oc = 100 * weighted(values, OC_WEIGHTS)
    ir_values = {**values, "human_load": hli / 100}
    ir = 100 * weighted(ir_values, IR_WEIGHTS)
    fcs_values = {
        "environmental_stability": 1 - eas / 100,
        "technical_stability": tss / 100,
        "human_readiness": 1 - hli / 100,
        "observability_confidence": oc / 100,
    }
    fcs = 100 * weighted(fcs_values, FCS_WEIGHTS)
    scores = {"EAS": eas, "TSS": tss, "HLI": hli, "OC": oc, "IR": ir, "FCS": fcs}
    for label, score in scores.items():
        if not 0 <= score <= 100:
            raise CalculationError(f"{label}: score is outside [0,100]")

    decomposition = {
        "EAS": {"weights": EAS_WEIGHTS, "normalized_inputs": {k: values[k] for k in EAS_WEIGHTS}},
        "TSS": {"weights": TSS_WEIGHTS, "normalized_disturbances": {k: values[k] for k in TSS_WEIGHTS}},
        "HLI": {"weights": HLI_WEIGHTS, "normalized_inputs": {k: values[k] for k in HLI_WEIGHTS}},
        "OC": {"weights": OC_WEIGHTS, "normalized_inputs": {k: values[k] for k in OC_WEIGHTS}},
        "IR": {"weights": IR_WEIGHTS, "normalized_inputs": {k: ir_values[k] for k in IR_WEIGHTS},
               "human_load_source": "derived:HLI/100"},
        "FCS": {"weights": FCS_WEIGHTS, "normalized_inputs": fcs_values},
    }
    core = {
        "artifact_id": ARTIFACT_ID,
        "calculation_version": VERSION,
        "specification_version": "1.0",
        "research_status": "proposed_indices_not_empirically_validated",
        "state_vector": scores,
        "classification": classify(fcs),
        "decomposition": decomposition,
        "observations": observation_records,
        "symbolic_notes_excluded_from_scoring": symbolic_notes,
    }
    if not SPEC_PATH.is_file():
        raise CalculationError(f"required specification not found: {SPEC_PATH.name}")
    return {
        **core,
        "provenance": {
            "hash_algorithm": "SHA-256",
            "source_sha256": sha256_bytes(Path(__file__).read_bytes()),
            "specification_sha256": sha256_bytes(SPEC_PATH.read_bytes()),
            "input_sha256": sha256_bytes(canonical_json(payload).encode("utf-8")),
            "core_result_sha256": sha256_bytes(canonical_json(core).encode("utf-8")),
            "hash_notice": "Content hashes verify bytes, not provenance authenticity or scientific validity.",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SOVRINT Field Calculator v1 (local, offline)")
    parser.add_argument("--input", required=True, type=Path, help="JSON observations")
    parser.add_argument("--output", type=Path, help="Optional JSON report; no automatic persistence")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        report = calculate(payload)
        encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(encoded, encoding="utf-8")
            print(f"report saved to {args.output}", file=sys.stderr)
        else:
            sys.stdout.write(encoded)
        return 0
    except (CalculationError, ValueError, OSError) as exc:
        print(f"calculation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
