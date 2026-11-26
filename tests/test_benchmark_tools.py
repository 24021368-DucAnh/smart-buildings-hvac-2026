import json
import tempfile
import unittest
import hashlib
from pathlib import Path

from team_tools.benchmark import (
    BenchmarkError,
    load_suite,
    score_results,
    validate_scenarios,
)
from team_tools.score_generated import validate_run_receipt


class BenchmarkScenarioTests(unittest.TestCase):
    def test_rejects_duplicate_expected_pairs_even_with_case_difference(self):
        with self.assertRaisesRegex(BenchmarkError, "duplicate"):
            validate_scenarios(
                [
                    {"building": "building_0500", "weather": "phoenix_2"},
                    {"building": "BUILDING_0500", "weather": "PHOENIX_2"},
                ]
            )

    def test_rejects_empty_generated_manifest(self):
        with self.assertRaisesRegex(BenchmarkError, "at least one"):
            validate_scenarios([])

    def test_official_suite_resolves_exactly_thirty_paired_scenarios(self):
        repo_root = Path(__file__).resolve().parents[1]
        manifest, pairs = load_suite(
            repo_root / "configs" / "benchmark_manifest.yaml", "dev_full", repo_root
        )
        self.assertEqual(manifest["full_steps"], 8640)
        self.assertEqual(len(pairs), 30)
        self.assertEqual(len({f"{p['building']}/{p['weather']}" for p in pairs}), 30)

    def test_reserved_holdout_cannot_be_run_before_opening(self):
        repo_root = Path(__file__).resolve().parents[1]
        with self.assertRaisesRegex(BenchmarkError, "closed"):
            load_suite(
                repo_root / "configs" / "benchmark_manifest.yaml",
                "frozen_holdout",
                repo_root,
            )


class GeneratedScoreTests(unittest.TestCase):
    def _write_summary(self, root: Path, pair: tuple[str, str], policy: str,
                       total_reward: float, total_steps: int) -> None:
        building, weather = pair
        output = root / building / weather / policy
        output.mkdir(parents=True)
        (output / "summary.json").write_text(
            json.dumps({
                "policy": policy,
                "total_reward": total_reward,
                "total_steps": total_steps,
            }),
            encoding="utf-8",
        )

    def test_scores_equal_weight_mean_absolute_reward_per_step(self):
        pairs = [
            {"building": "building_0500", "weather": "atlanta_4"},
            {"building": "building_0500", "weather": "denver_1"},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_summary(root, ("building_0500", "atlanta_4"),
                                "pid_water", -8640.0, 8640)
            self._write_summary(root, ("building_0500", "denver_1"),
                                "pid_water", -17280.0, 8640)

            result = score_results(root, pairs, "pid_water", expected_steps=8640)

        self.assertEqual(result["scenario_count"], 2)
        self.assertAlmostEqual(result["mean_loss"], 1.5)

    def test_rejects_missing_scenario(self):
        pairs = [
            {"building": "building_0500", "weather": "atlanta_4"},
            {"building": "building_0500", "weather": "denver_1"},
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_summary(Path(temp_dir),
                                ("building_0500", "atlanta_4"),
                                "pid_water", -8640.0, 8640)

            with self.assertRaisesRegex(BenchmarkError, "missing"):
                score_results(Path(temp_dir), pairs, "pid_water", 8640)

    def test_rejects_extra_scenario(self):
        pairs = [{"building": "building_0500", "weather": "atlanta_4"}]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_summary(root, ("building_0500", "atlanta_4"),
                                "pid_water", -8640.0, 8640)
            self._write_summary(root, ("building_0501", "denver_1"),
                                "pid_water", -8640.0, 8640)

            with self.assertRaisesRegex(BenchmarkError, "extra"):
                score_results(root, pairs, "pid_water", 8640)

    def test_rejects_case_mismatched_scenario_key(self):
        pairs = [{"building": "building_0500", "weather": "atlanta_4"}]
        with tempfile.TemporaryDirectory() as temp_dir:
            self._write_summary(Path(temp_dir),
                                ("BUILDING_0500", "atlanta_4"),
                                "pid_water", -8640.0, 8640)

            with self.assertRaisesRegex(BenchmarkError, "missing.*extra"):
                score_results(Path(temp_dir), pairs, "pid_water", 8640)

    def test_rejects_wrong_steps_and_non_finite_reward(self):
        pairs = [{"building": "building_0500", "weather": "atlanta_4"}]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_summary(root, ("building_0500", "atlanta_4"),
                                "pid_water", -8640.0, 288)
            with self.assertRaisesRegex(BenchmarkError, "steps"):
                score_results(root, pairs, "pid_water", 8640)

            summary = root / "building_0500" / "atlanta_4" / "pid_water" / "summary.json"
            summary.write_text(
                '{"policy":"pid_water","total_reward":NaN,"total_steps":8640}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(BenchmarkError, "finite"):
                score_results(root, pairs, "pid_water", 8640)

    def test_rejects_duplicate_json_fields(self):
        pairs = [{"building": "building_0500", "weather": "atlanta_4"}]
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "building_0500" / "atlanta_4" / "pid_water"
            output.mkdir(parents=True)
            (output / "summary.json").write_text(
                '{"policy":"pid_water","total_reward":-1,"total_reward":-2,"total_steps":8640}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(BenchmarkError, "duplicate JSON field"):
                score_results(Path(temp_dir), pairs, "pid_water", 8640)

    def test_run_receipt_must_cover_the_exact_full_suite(self):
        pair = {"building": "building_0500", "weather": "atlanta_4"}
        with tempfile.TemporaryDirectory() as temp_dir:
            run_root = Path(temp_dir)
            results = run_root / "results"
            results.mkdir()
            (run_root / "run.json").write_text(
                json.dumps({
                    "status": "SUCCEEDED_FULL",
                    "suite": "generated_dev",
                    "policy": "pid_water",
                    "step_count": 8640,
                    "scenario_count_expected": 1,
                    "scenario_runs": [{
                        "scenario": "building_0500/atlanta_4",
                        "status": "SUCCEEDED",
                    }],
                    "commit_sha": "a" * 40,
                    "manifest_sha256": "b" * 64,
                    "run_config": {"suite": "generated_dev", "policy": "pid_water", "steps": 8640,
                                   "manifest_sha256": "b" * 64, "scenarios": ["building_0500/atlanta_4"]},
                }),
                encoding="utf-8",
            )
            receipt_path = run_root / "run.json"
            value = json.loads(receipt_path.read_text())
            value["config_hash"] = hashlib.sha256(json.dumps(value["run_config"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            receipt_path.write_text(json.dumps(value), encoding="utf-8")
            receipt = validate_run_receipt(results, "generated_dev", "pid_water", [pair], "b" * 64)
            self.assertEqual(receipt["status"], "SUCCEEDED_FULL")

            incomplete = json.loads((run_root / "run.json").read_text(encoding="utf-8"))
            incomplete["status"] = "FAILED"
            (run_root / "run.json").write_text(json.dumps(incomplete), encoding="utf-8")
            with self.assertRaisesRegex(BenchmarkError, "successful full-length"):
                validate_run_receipt(results, "generated_dev", "pid_water", [pair], "b" * 64)


if __name__ == "__main__":
    unittest.main()
