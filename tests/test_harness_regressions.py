"""Regression tests for review findings; fixtures are synthetic, never scores."""

import contextlib
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml

from team_tools.benchmark import BenchmarkError, score_results, validate_split_separation
import team_tools.run_batch as runner
from team_tools.score_generated import main as score_main

REPO = Path(__file__).resolve().parents[1]


class ScorerRegressions(unittest.TestCase):
    def test_extra_scenario_without_building_prefix_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for building in ("building_0500", "unexpected_building"):
                p = root / building / "atlanta_4" / "pid_water" / "summary.json"
                p.parent.mkdir(parents=True)
                p.write_text(json.dumps(dict(policy="pid_water", total_steps=8640,
                                             total_reward=-8640)), encoding="utf-8")
            with self.assertRaisesRegex(BenchmarkError, "extra"):
                score_results(root, [dict(building="building_0500", weather="atlanta_4")], "pid_water")

    def make_run(self, root):
        manifest = yaml.safe_load((REPO / "configs/benchmark_manifest.yaml").read_text())
        manifest["suites"]["dev_full"]["manifest"] = str(REPO / "smart_buildings/training_set.yaml")
        pair = dict(building="building_0500", weather="atlanta_4")
        manifest["suites"]["generated_dev"].update(status="ready", accepted_buildings=["building_0500"], scenarios=[pair])
        mp = root / "manifest.yaml"
        mp.write_text(yaml.safe_dump(manifest), encoding="utf-8")
        results = root / "results"
        summary = results / "building_0500/atlanta_4/pid_water/summary.json"
        summary.parent.mkdir(parents=True)
        summary.write_text(json.dumps(dict(policy="pid_water", total_steps=8640, total_reward=-8640)), encoding="utf-8")
        mh = hashlib.sha256(mp.read_bytes()).hexdigest()
        config = dict(suite="generated_dev", policy="pid_water", steps=8640, manifest_sha256=mh,
                      scenarios=["building_0500/atlanta_4"], scenario_config_hashes=[dict(scenario="building_0500/atlanta_4", hashes={"config.gin": "b" * 64})])
        receipt = dict(status="SUCCEEDED_FULL", suite="generated_dev", policy="pid_water", step_count=8640,
                       scenario_count_expected=1, scenario_runs=[dict(scenario="building_0500/atlanta_4", status="SUCCEEDED")],
                       commit_sha="a" * 40, config_hash=hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                       manifest_sha256=mh, run_config=config)
        (root / "run.json").write_text(json.dumps(receipt), encoding="utf-8")
        return mp, results, receipt

    def test_cli_rejects_receipt_for_a_different_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mp, results, receipt = self.make_run(root)
            receipt["manifest_sha256"] = "0" * 64
            (root / "run.json").write_text(json.dumps(receipt), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = score_main([str(results), "--manifest", str(mp), "--suite", "generated_dev"])
            self.assertEqual(result, 2)

    def test_cli_rejects_changed_config_fingerprint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mp, results, receipt = self.make_run(root)
            receipt["config_hash"] = "0" * 64
            (root / "run.json").write_text(json.dumps(receipt), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                result = score_main([str(results), "--manifest", str(mp), "--suite", "generated_dev"])
            self.assertEqual(result, 2)

    def test_valid_synthetic_full_suite_can_be_scored(self):
        with tempfile.TemporaryDirectory() as temp:
            mp, results, _ = self.make_run(Path(temp))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = score_main([str(results), "--manifest", str(mp), "--suite", "generated_dev"])
            self.assertEqual(result, 0)
            self.assertIn('"mean_loss": 1.0', output.getvalue())

    def test_cli_rejects_malformed_scenario_in_receipt_without_crashing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mp, results, receipt = self.make_run(root)
            receipt["scenario_runs"][0]["scenario"] = None
            (root / "run.json").write_text(json.dumps(receipt), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(score_main([str(results), "--manifest", str(mp), "--suite", "generated_dev"]), 2)

    def test_invalid_seed_range_is_rejected(self):
        manifest = yaml.safe_load((REPO / "configs/benchmark_manifest.yaml").read_text())
        for value in ("bad", -1, True):
            with self.subTest(value=value):
                manifest["suites"]["generated_dev"]["candidate_seed_count"] = value
                with self.assertRaises(BenchmarkError):
                    validate_split_separation(manifest, REPO)


class RunnerRegressions(unittest.TestCase):
    def test_generated_suite_uses_its_scenario_directory_and_records_actual_policy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            mp, _, _ = ScorerRegressions().make_run(root)
            manifest = yaml.safe_load(mp.read_text())
            scenario_dir = root / "generated_scenarios"
            config = scenario_dir / "building_0500/atlanta_4/config.gin"
            config.parent.mkdir(parents=True)
            for name in ('weather.csv','floor_plan.npy','zone_map.npy','config.yaml'):
                (config.parent/name).write_text('synthetic input bytes')
            config.write_text(''.join(f"{key} = '{(config.parent/name).as_posix()}'\n" for key,name in
                [('weather_csv_path','weather.csv'),('floor_plan_filepath','floor_plan.npy'),('zone_map_filepath','zone_map.npy')]))
            manifest["suites"]["generated_dev"]["scenarios_dir"] = str(scenario_dir)
            mp.write_text(yaml.safe_dump(manifest))
            args = runner.build_parser().parse_args(["--manifest", str(mp), "--suite", "generated_dev", "--policy", "other_policy", "--output-root", str(root / "runs"), "--experiment-id", "generated-probe"])
            original_run = subprocess.run

            def evaluate_fixture(command, **kwargs):
                if "smart_buildings.evaluate" not in command:
                    return original_run(command, **kwargs)
                self.assertEqual(Path(command[command.index("--scenarios-dir") + 1]), scenario_dir)
                self.assertEqual(kwargs["env"]["NUMBA_NUM_THREADS"], "1")
                output = Path(command[command.index("--results-dir") + 1]) / "building_0500/atlanta_4/other_policy/summary.json"
                output.parent.mkdir(parents=True)
                output.write_text(json.dumps(dict(policy="other_policy", total_steps=8640, total_reward=-8640)))
                Path(command[3]).write_text(json.dumps(dict(process_cpu_s=0.25)))
                return subprocess.CompletedProcess(command, 0, "fixture stdout", "")

            with patch.object(runner, "REGISTRY_PATH", root / "registry.csv"), patch.object(runner.subprocess, "run", side_effect=evaluate_fixture), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.run_batch(args), 0)
            with (root / "registry.csv").open(encoding="utf-8") as stream:
                row = next(csv.DictReader(stream))
            self.assertIn("other_policy", row["module_flags"])
            self.assertNotIn("pid_water", row["module_flags"])
            self.assertAlmostEqual(float(row["cpu_core_hours"]), 0.25 / 3600)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(score_main([str(root / "runs/generated-probe/results"), "--manifest", str(mp), "--suite", "generated_dev", "--policy", "other_policy"]), 0)

    def test_process_launch_failure_is_terminal_and_registered(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = runner.build_parser().parse_args(["--suite", "dev_small", "--scenario", "building_train_1/fairbanks_1", "--steps", "288", "--output-root", str(root), "--experiment-id", "launch-error"])
            original_run = subprocess.run

            def cannot_launch(command, **kwargs):
                if "smart_buildings.evaluate" in command:
                    raise OSError("simulated process creation failure")
                return original_run(command, **kwargs)

            with patch.object(runner, "REGISTRY_PATH", root / "registry.csv"), patch.object(runner.subprocess, "run", side_effect=cannot_launch), contextlib.redirect_stdout(io.StringIO()):
                code = runner.run_batch(args)
            self.assertEqual(code, 1)
            receipt = json.loads((root / "launch-error/run.json").read_text())
            self.assertEqual(receipt["status"], "FAILED_EXECUTION")
            self.assertEqual(receipt["scenario_runs"][0]["status"], "FAILED_EXECUTION")

    def test_unsafe_policy_is_rejected_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = runner.build_parser().parse_args(["--policy", "../pid_water", "--output-root", str(root)])
            with patch.object(runner, "REGISTRY_PATH", root / "registry.csv"), self.assertRaises(BenchmarkError):
                runner.run_batch(args)
            self.assertEqual(list(root.iterdir()), [])

    def test_timeout_bytes_are_saved_and_both_receipts_are_terminal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = runner.build_parser().parse_args(["--suite", "dev_small", "--scenario", "building_train_1/fairbanks_1", "--steps", "288", "--output-root", str(root), "--experiment-id", "timeout-probe"])
            original_run = subprocess.run

            def timeout_evaluator(command, **kwargs):
                if "smart_buildings.evaluate" in command:
                    raise subprocess.TimeoutExpired(command, 1, output=b"partial stdout", stderr=b"partial stderr")
                return original_run(command, **kwargs)

            with patch.object(runner, "REGISTRY_PATH", root / "registry.csv"), patch.object(runner.subprocess, "run", side_effect=timeout_evaluator), contextlib.redirect_stdout(io.StringIO()):
                code = runner.run_batch(args)
            self.assertEqual(code, 1)
            receipt = json.loads((root / "timeout-probe/run.json").read_text())
            self.assertEqual(receipt["status"], "TIMED_OUT")
            self.assertEqual(receipt["scenario_runs"][0]["status"], "TIMED_OUT")
            self.assertEqual((root / "timeout-probe/building_train_1__fairbanks_1.stdout.log").read_text(), "partial stdout")
            with (root / "registry.csv").open(encoding="utf-8") as stream:
                self.assertEqual(next(csv.DictReader(stream))["status"], "TIMED_OUT")


if __name__ == "__main__":
    unittest.main()
