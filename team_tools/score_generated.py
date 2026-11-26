"""Strict full-length scorer for an explicitly declared generated suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import re
from pathlib import Path

from team_tools.benchmark import (
    BenchmarkError,
    _read_summary,
    config_fingerprint,
    load_suite,
    scenario_key,
    score_results,
    validate_scenarios,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "configs" / "benchmark_manifest.yaml"


def validate_run_receipt(
    results_dir: Path,
    suite_name: str,
    policy: str,
    expected_scenarios: list[dict[str, str]],
    manifest_sha256: str,
) -> dict:
    """Require a completed full-suite run receipt beside the results tree."""
    receipt_path = results_dir.parent / "run.json"
    try:
        receipt = _read_summary(receipt_path)
    except (OSError, json.JSONDecodeError) as error:
        raise BenchmarkError(f"cannot read run receipt {receipt_path}: {error}") from error
    if not isinstance(receipt, dict):
        raise BenchmarkError("run receipt must be a JSON object")
    if receipt.get("status") != "SUCCEEDED_FULL":
        raise BenchmarkError("run receipt is not a successful full-length run")
    if receipt.get("suite") != suite_name or receipt.get("policy") != policy:
        raise BenchmarkError("run receipt suite or policy does not match the requested score")
    if receipt.get("step_count") != 8640 or receipt.get("scenario_count_expected") != len(expected_scenarios):
        raise BenchmarkError("run receipt has the wrong step count or expected scenario count")
    completed = receipt.get("scenario_runs")
    if not isinstance(completed, list) or any(
        not isinstance(item, dict) or item.get("status") != "SUCCEEDED"
        for item in completed
    ):
        raise BenchmarkError("run receipt contains an incomplete scenario")
    if any(not isinstance(item.get("scenario"), str) or item["scenario"].count("/") != 1
           for item in completed):
        raise BenchmarkError("run receipt has a malformed scenario key")
    actual = validate_scenarios(
        [
            {"building": item.get("scenario", "").split("/", 1)[0],
             "weather": item.get("scenario", "").split("/", 1)[1]
             if "/" in item.get("scenario", "") else ""}
            for item in completed
        ]
    )
    if sorted(map(scenario_key, actual)) != sorted(map(scenario_key, expected_scenarios)):
        raise BenchmarkError("run receipt scenarios do not exactly match the manifest")
    if len(actual) != receipt.get("scenario_count_expected"):
        raise BenchmarkError("run receipt has duplicate or missing scenarios")
    for item in completed:
        summary_path=results_dir/item['scenario']/policy/'summary.json'
        binding=item.get('summary_sha256')
        if receipt.get('source_guard')=='before_after_sha256_v1' and not re.fullmatch('[0-9a-f]{64}',str(binding)):
            raise BenchmarkError('new producer receipt is missing a summary checksum')
        if binding is not None:
            try:observed=hashlib.sha256(summary_path.read_bytes()).hexdigest()
            except OSError as error:raise BenchmarkError('missing producer-bound summary') from error
            if observed!=binding:raise BenchmarkError('producer-bound summary checksum mismatch')
    if receipt.get('source_guard')=='before_after_sha256_v1':
        pin=receipt.get('numeric_sources_sha256')
        if (not isinstance(pin,dict) or not pin or any(not isinstance(k,str) or not re.fullmatch('[0-9a-f]{64}',str(v)) for k,v in pin.items())
                or not isinstance(receipt.get('evaluator_bootstrap'),str) or not receipt['evaluator_bootstrap']):
            raise BenchmarkError('new producer receipt is missing numerical source proof')
    if not re.fullmatch(r"[0-9a-f]{40}", str(receipt.get("commit_sha", ""))):
        raise BenchmarkError("run receipt is missing source or config fingerprints")
    if receipt.get("manifest_sha256") != manifest_sha256:
        raise BenchmarkError("run receipt manifest fingerprint does not match the scoring manifest")
    snapshot = receipt.get("run_config")
    if not isinstance(snapshot, dict):
        raise BenchmarkError("run receipt is missing its config snapshot")
    if not isinstance(snapshot.get("scenarios"), list) or any(
        not isinstance(key, str) for key in snapshot["scenarios"]
    ):
        raise BenchmarkError("run configuration has malformed scenario keys")
    if config_fingerprint(snapshot) != receipt.get("config_hash"):
        raise BenchmarkError("run receipt config fingerprint does not match its snapshot")
    if (snapshot.get("manifest_sha256") != manifest_sha256
            or snapshot.get("suite") != suite_name or snapshot.get("policy") != policy
            or snapshot.get("steps") != 8640
            or sorted(snapshot.get("scenarios", [])) != sorted(map(scenario_key, expected_scenarios))):
        raise BenchmarkError("run configuration snapshot does not match the requested full suite")
    return receipt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_dir", type=Path)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--suite", choices=("generated_dev", "frozen_holdout"), required=True)
    parser.add_argument("--policy", default="pid_water")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest_path = args.manifest.resolve()
    try:
        manifest, scenarios = load_suite(manifest_path, args.suite, REPO_ROOT)
        if manifest.get("full_steps") != 8640:
            raise BenchmarkError("manifest full_steps must be exactly 8640")
        manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        validate_run_receipt(args.results_dir.resolve(), args.suite, args.policy, scenarios, manifest_hash)
        result = score_results(args.results_dir.resolve(), scenarios, args.policy, 8640)
    except BenchmarkError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    result["suite"] = args.suite
    result["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    print(json.dumps(result, indent=2, allow_nan=False))
    print(
        f"\n{args.policy}: mean absolute per-step reward = "
        f"{result['mean_loss']:.8f} across {result['scenario_count']} full scenarios "
        "(lower is better)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
