"""Standard-library regression tests for the SOVRINT Field Calculator v1."""
import copy
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from field_calculator import (  # noqa: E402
    EAS_WEIGHTS, TSS_WEIGHTS, HLI_WEIGHTS, OC_WEIGHTS, IR_WEIGHTS,
    FCS_WEIGHTS, CalculationError, calculate, classify, normalize,
)


def fixture(value=0.5):
    from field_calculator import SCORE_GROUPS
    observations = {}
    for group, weights in SCORE_GROUPS.items():
        for name in weights:
            observations[name] = {
                "value": value,
                "evidence_class": (
                    "self_reported" if group == "HLI"
                    else "interpretive" if group in {"OC", "IR"}
                    else "measured"
                ),
                "confidence": 0.6,
            }
    return {
        "context": {
            "created_at": "2026-10-21T12:00:00Z",
            "location": "synthetic-test-only",
            "source": "synthetic_fixture_not_observed_data",
            "source_class": "synthetic",
        },
        "observations": observations,
    }


class FieldCalculatorTests(unittest.TestCase):
    def test_specification_weights_are_normalized(self):
        for weights in (
            EAS_WEIGHTS, TSS_WEIGHTS, HLI_WEIGHTS,
            OC_WEIGHTS, IR_WEIGHTS, FCS_WEIGHTS,
        ):
            self.assertAlmostEqual(sum(weights.values()), 1.0)

    def test_halfway_state_has_six_halfway_scores(self):
        scores = calculate(fixture())["state_vector"]
        self.assertEqual(list(scores), ["EAS", "TSS", "HLI", "OC", "IR", "FCS"])
        for score in scores.values():
            self.assertAlmostEqual(score, 50.0)

    def test_extreme_values_have_expected_directions(self):
        low = calculate(fixture(0.0))["state_vector"]
        high = calculate(fixture(1.0))["state_vector"]
        self.assertAlmostEqual(low["EAS"], 0)
        self.assertAlmostEqual(low["TSS"], 100)
        self.assertAlmostEqual(low["HLI"], 0)
        self.assertAlmostEqual(low["OC"], 0)
        self.assertAlmostEqual(low["IR"], 0)
        self.assertAlmostEqual(low["FCS"], 75)
        self.assertAlmostEqual(high["EAS"], 100)
        self.assertAlmostEqual(high["TSS"], 0)
        self.assertAlmostEqual(high["HLI"], 100)
        self.assertAlmostEqual(high["OC"], 100)
        self.assertAlmostEqual(high["IR"], 100)
        self.assertAlmostEqual(high["FCS"], 25)

    def test_field_coherence_is_decomposed_from_four_stated_inputs(self):
        report = calculate(fixture())
        decomp = report["decomposition"]["FCS"]["normalized_inputs"]
        self.assertEqual(set(decomp), set(FCS_WEIGHTS))
        self.assertAlmostEqual(sum(FCS_WEIGHTS[k] * decomp[k] for k in decomp) * 100, 50.0)

    def test_human_load_used_in_risk_is_derived_not_user_supplied(self):
        case = fixture(0)
        case["observations"]["sleep_debt"]["value"] = 1.0
        report = calculate(case)
        self.assertAlmostEqual(report["state_vector"]["HLI"], 30.0)
        self.assertAlmostEqual(report["state_vector"]["IR"], 7.5)
        self.assertAlmostEqual(report["decomposition"]["IR"]["normalized_inputs"]["human_load"], 0.3)

    def test_cannot_override_derived_human_load(self):
        case = fixture()
        case["observations"]["human_load"] = {"value": 0, "evidence_class": "interpretive"}
        with self.assertRaisesRegex(CalculationError, "unknown"):
            calculate(case)

    def test_raw_minmax_normalization_and_clamping(self):
        self.assertEqual(normalize({"raw": -4, "minimum": 0, "maximum": 10}, "x"), 0)
        self.assertEqual(normalize({"raw": 40, "minimum": 0, "maximum": 10}, "x"), 1)
        self.assertEqual(normalize({"raw": 5, "minimum": 0, "maximum": 10}, "x"), 0.5)
        with self.assertRaises(CalculationError):
            normalize({"raw": 5, "minimum": 5, "maximum": 5}, "x")
        with self.assertRaises(CalculationError):
            normalize({"value": .5, "raw": 3, "minimum": 0, "maximum": 5}, "x")

    def test_raw_observation_provenance_preserved(self):
        case = fixture()
        case["observations"]["wind_intensity"] = {
            "raw": 5, "minimum": 0, "maximum": 10,
            "evidence_class": "measured", "unit": "m/s",
            "source": "synthetic demo anemometer", "confidence": .5,
        }
        record = calculate(case)["observations"]["wind_intensity"]
        self.assertEqual(record["raw_input"]["raw"], 5)
        self.assertEqual(record["value"], .5)
        self.assertEqual(record["unit"], "m/s")

    def test_missing_input_does_not_default_to_zero(self):
        case = fixture()
        del case["observations"]["packet_loss"]
        with self.assertRaisesRegex(CalculationError, "missing"):
            calculate(case)

    def test_unknown_key_does_not_get_ignored(self):
        case = fixture()
        case["observations"]["ghost_metric"] = {"value": 1, "evidence_class": "symbolic"}
        with self.assertRaisesRegex(CalculationError, "unknown"):
            calculate(case)

    def test_symbolic_input_cannot_influence_numeric_score(self):
        case = fixture()
        case["observations"]["wind_intensity"]["evidence_class"] = "symbolic"
        with self.assertRaisesRegex(CalculationError, "symbolic inputs never score"):
            calculate(case)

    def test_symbolic_notes_are_preserved_but_do_not_score(self):
        original = fixture()
        decorated = copy.deepcopy(original)
        decorated["symbolic_notes"] = [{
            "evidence_class": "symbolic", "text": "A philosophical reading, not evidence",
        }]
        a, b = calculate(original), calculate(decorated)
        self.assertEqual(a["state_vector"], b["state_vector"])
        self.assertEqual(len(b["symbolic_notes_excluded_from_scoring"]), 1)

    def test_measured_inputs_required_for_environment_and_technical(self):
        case = fixture()
        case["observations"]["packet_loss"]["evidence_class"] = "interpretive"
        with self.assertRaises(CalculationError):
            calculate(case)

    def test_evidence_class_wrong_type_fails_closed(self):
        case = fixture()
        case["observations"]["packet_loss"]["evidence_class"] = ["measured"]
        with self.assertRaises(CalculationError):
            calculate(case)

    def test_nonfinite_boolean_negative_and_over_one_rejected(self):
        for value in [True, -0.01, 1.01, float("nan"), float("inf")]:
            case = fixture()
            case["observations"]["packet_loss"]["value"] = value
            with self.subTest(value=value), self.assertRaises(CalculationError):
                calculate(case)

    def test_utc_time_required(self):
        case = fixture()
        case["context"]["created_at"] = "2026-10-21T12:00:00-04:00"
        with self.assertRaisesRegex(CalculationError, "UTC"):
            calculate(case)

    def test_replay_produces_same_hashes_and_scores(self):
        case = fixture()
        first, second = calculate(case), calculate(copy.deepcopy(case))
        self.assertEqual(first, second)
        self.assertEqual(len(first["provenance"]["core_result_sha256"]), 64)
        self.assertEqual(first["observations"]["packet_loss"]["source_class"], "synthetic")
        self.assertIsNone(first["observations"]["packet_loss"]["source_url"])

    def test_score_boundaries_have_no_decimal_gap(self):
        self.assertEqual(classify(19.99), "CRITICAL_INSTABILITY")
        self.assertEqual(classify(20.0), "HIGH_DISTURBANCE")
        self.assertEqual(classify(39.999), "HIGH_DISTURBANCE")
        self.assertEqual(classify(80), "HIGH_COHERENCE")
        self.assertEqual(classify(100), "HIGH_COHERENCE")

    def test_cli_output_and_error_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            inpath = Path(temp) / "input.json"
            outpath = Path(temp) / "report.json"
            inpath.write_text(json.dumps(fixture()), encoding="utf-8")
            done = subprocess.run(
                [sys.executable, str(ROOT / "field_calculator.py"),
                 "--input", str(inpath), "--output", str(outpath)],
                capture_output=True, text=True,
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(json.loads(outpath.read_text(encoding="utf-8"))["state_vector"]["FCS"], 50.0)
            inpath.write_text("{}", encoding="utf-8")
            bad = subprocess.run(
                [sys.executable, str(ROOT / "field_calculator.py"),
                 "--input", str(inpath)],
                capture_output=True, text=True,
            )
            self.assertEqual(bad.returncode, 2)
            self.assertIn("calculation failed", bad.stderr)


if __name__ == "__main__":
    unittest.main()
