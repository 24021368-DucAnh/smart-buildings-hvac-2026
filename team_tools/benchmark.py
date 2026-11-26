"""Shared manifest and strict generated-result validation for Member B."""

from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path
import re
from typing import Any

FULL_STEPS = 8640


def config_fingerprint(config: dict[str, Any]) -> str:
    """Hash the exact JSON configuration snapshot stored with a run."""
    return hashlib.sha256(json.dumps(
        config, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()


class BenchmarkError(ValueError):
    """Raised when a benchmark suite or result tree is not scoreable."""


def scenario_key(pair: dict[str, Any]) -> str:
    """Return the canonical building/weather path for one manifest pair."""
    return f"{pair['building']}/{pair['weather']}"


def validate_scenarios(raw_scenarios: Any) -> list[dict[str, str]]:
    """Validate and normalize an explicit list of building/weather pairs."""
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise BenchmarkError("scenario manifest must contain at least one scenario")

    scenarios: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, pair in enumerate(raw_scenarios):
        if not isinstance(pair, dict):
            raise BenchmarkError(f"scenario {index} must be a mapping")
        building, weather = pair.get("building"), pair.get("weather")
        if not isinstance(building, str) or not isinstance(weather, str):
            raise BenchmarkError(
                f"scenario {index} requires string building and weather values"
            )
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", building) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_-]*", weather
        ):
            raise BenchmarkError(f"scenario {index} contains an unsafe path value")
        key = f"{building}/{weather}"
        folded_key = key.casefold()
        if folded_key in seen:
            raise BenchmarkError(f"duplicate scenario in manifest: {key}")
        seen.add(folded_key)
        scenarios.append({"building": building, "weather": weather})
    return scenarios


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    """Read one YAML object, with a useful error for malformed inputs."""
    try:
        import yaml
    except ImportError as error:
        raise BenchmarkError("PyYAML is required; install the project dependencies") from error
    try:
        with path.open(encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as error:
        raise BenchmarkError(f"cannot read YAML file {path}: {error}") from error
    if not isinstance(value, dict):
        raise BenchmarkError(f"YAML file must contain a mapping: {path}")
    return value


def validate_split_separation(manifest: dict[str, Any], repo_root: Path) -> None:
    """Check reserved generated/holdout seeds and weather strips stay separate."""
    suites = manifest.get("suites")
    if not isinstance(suites, dict):
        raise BenchmarkError("benchmark manifest requires a suites mapping")

    official_ref = suites.get("dev_full", {}).get("manifest")
    if not isinstance(official_ref, str):
        raise BenchmarkError("dev_full must reference the official training manifest")
    official_path = repo_root / official_ref
    official = load_yaml_mapping(official_path)
    official_pairs = validate_scenarios(official.get("scenarios"))
    official_buildings = {pair["building"].casefold() for pair in official_pairs}
    official_weather = {pair["weather"].casefold() for pair in official_pairs}

    generated = suites.get("generated_dev", {})
    holdout = suites.get("frozen_holdout", {})
    if not isinstance(generated, dict) or not isinstance(holdout, dict):
        raise BenchmarkError("generated_dev and frozen_holdout must be mappings")

    generated_seed = generated.get("seed_range_start")
    generated_count = generated.get("candidate_seed_count")
    holdout_seed = holdout.get("seed_range_start")
    holdout_count = holdout.get("candidate_seed_count")
    for label, seed, count in (("generated_dev", generated_seed, generated_count),
                               ("frozen_holdout", holdout_seed, holdout_count)):
        if type(seed) is not int or seed < 0 or type(count) is not int or count <= 0:
            raise BenchmarkError(f"{label} requires nonnegative seed start and positive integer seed count")
    generated_end = generated_seed + generated_count
    holdout_end = holdout_seed + holdout_count
    if max(generated_seed, holdout_seed) < min(generated_end, holdout_end):
        raise BenchmarkError("generated_dev and frozen_holdout seed ranges overlap")

    generated_buildings = {
        str(value).casefold() for value in generated.get("accepted_buildings", [])
    }
    holdout_buildings = {
        str(value).casefold() for value in holdout.get("accepted_buildings", [])
    }
    if generated_buildings & holdout_buildings:
        raise BenchmarkError("generated_dev and frozen_holdout buildings overlap")
    if generated_buildings & official_buildings or holdout_buildings & official_buildings:
        raise BenchmarkError("generated splits reuse official training buildings")

    generated_weather = {
        str(value).casefold() for value in generated.get("weather_strips", [])
    }
    holdout_weather = {
        str(value).casefold() for value in holdout.get("weather_strips", [])
    }
    if generated_weather & holdout_weather:
        raise BenchmarkError("generated_dev and frozen_holdout weather strips overlap")
    if generated_weather & official_weather or holdout_weather & official_weather:
        raise BenchmarkError("generated splits reuse official training weather strips")

    for suite_name, suite_data in (("generated_dev", generated),
                                   ("frozen_holdout", holdout)):
        pairs = suite_data.get("scenarios", [])
        if pairs:
            normalized = validate_scenarios(pairs)
            undeclared = {
                pair["building"].casefold() for pair in normalized
            } - {str(value).casefold() for value in suite_data.get("accepted_buildings", [])}
            if undeclared:
                raise BenchmarkError(
                    f"{suite_name} scenarios include unaccepted buildings: "
                    f"{', '.join(sorted(undeclared))}"
                )
            wrong_weather = {
                pair["weather"].casefold() for pair in normalized
            } - {str(value).casefold() for value in suite_data.get("weather_strips", [])}
            if wrong_weather:
                raise BenchmarkError(
                    f"{suite_name} scenarios include undeclared weather strips: "
                    f"{', '.join(sorted(wrong_weather))}"
                )


def load_suite(
    manifest_path: Path, suite_name: str, repo_root: Path
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Load one exact suite from the benchmark manifest."""
    manifest = load_yaml_mapping(manifest_path)
    validate_split_separation(manifest, repo_root)
    suites = manifest.get("suites", {})
    suite = suites.get(suite_name)
    if not isinstance(suite, dict):
        raise BenchmarkError(f"unknown suite {suite_name!r}")

    status = suite.get("status")
    if suite_name == "frozen_holdout":
        if status != "frozen" or not suite.get("opened_at"):
            raise BenchmarkError("frozen_holdout is closed; do not evaluate it yet")
        if suite.get("contaminated"):
            raise BenchmarkError("frozen_holdout is contaminated and cannot be scored")
    elif status != "ready":
        raise BenchmarkError(
            f"suite {suite_name!r} is {status!r}; exact scenarios are not ready"
        )

    if suite_name == "dev_full":
        reference = suite.get("manifest")
        if not isinstance(reference, str):
            raise BenchmarkError("dev_full must reference a training manifest")
        official = load_yaml_mapping(repo_root / reference)
        scenarios = validate_scenarios(official.get("scenarios"))
        expected_count = suite.get("expected_scenarios")
        if expected_count != len(scenarios):
            raise BenchmarkError(
                f"dev_full expected {expected_count!r} scenarios but manifest has "
                f"{len(scenarios)}"
            )
    else:
        scenarios = validate_scenarios(suite.get("scenarios"))

    return manifest, scenarios


def _object_without_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BenchmarkError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _read_summary(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream, object_pairs_hook=_object_without_duplicate_keys)
    except (OSError, json.JSONDecodeError) as error:
        raise BenchmarkError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise BenchmarkError(f"summary must contain a JSON object: {path}")
    return value


def score_results(
    results_dir: Path,
    expected_scenarios: Any,
    policy: str,
    expected_steps: int = FULL_STEPS,
) -> dict[str, Any]:
    """Score exactly the declared full-length scenarios; reject partial trees."""
    if expected_steps != FULL_STEPS:
        raise BenchmarkError(
            f"generated scoring requires {FULL_STEPS} steps; got {expected_steps}"
        )
    if not isinstance(policy, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", policy):
        raise BenchmarkError("policy must be a non-empty key without path separators")

    expected = validate_scenarios(expected_scenarios)
    expected_by_key = {scenario_key(pair): pair for pair in expected}
    if not results_dir.is_dir():
        raise BenchmarkError(f"results directory does not exist: {results_dir}")

    discovered: dict[str, Path] = {}
    for summary_path in results_dir.rglob("summary.json"):
        parts = summary_path.relative_to(results_dir).parts
        if len(parts) != 4:
            raise BenchmarkError(f"unexpected summary layout: {summary_path}")
        if parts[2] != policy:
            raise BenchmarkError(f"unexpected policy results: {parts[2]}")
        key = f"{parts[0]}/{parts[1]}"
        folded_key = key.casefold()
        prior = next((k for k in discovered if k.casefold() == folded_key), None)
        if prior is not None:
            raise BenchmarkError(f"duplicate scenario results: {prior} and {key}")
        discovered[key] = summary_path

    missing = sorted(set(expected_by_key) - set(discovered))
    extra = sorted(set(discovered) - set(expected_by_key))
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing scenarios: {', '.join(missing)}")
        if extra:
            details.append(f"extra scenarios: {', '.join(extra)}")
        raise BenchmarkError("; ".join(details))

    rows: list[dict[str, Any]] = []
    for key in sorted(expected_by_key):
        summary = _read_summary(discovered[key])
        if summary.get("policy") != policy:
            raise BenchmarkError(
                f"policy mismatch for {key}: expected {policy!r}, "
                f"got {summary.get('policy')!r}"
            )
        steps = summary.get("total_steps")
        if isinstance(steps, bool) or not isinstance(steps, int) or steps != FULL_STEPS:
            raise BenchmarkError(
                f"wrong or incomplete steps for {key}: expected {FULL_STEPS}, got {steps!r}"
            )
        reward = summary.get("total_reward")
        if isinstance(reward, bool) or not isinstance(reward, (int, float)):
            raise BenchmarkError(f"total_reward must be numeric for {key}")
        reward = float(reward)
        if not math.isfinite(reward):
            raise BenchmarkError(f"total_reward must be finite for {key}")
        rows.append(
            {
                "scenario": key,
                "total_reward": reward,
                "loss": abs(reward / FULL_STEPS),
            }
        )

    return {
        "policy": policy,
        "step_count": FULL_STEPS,
        "scenario_count": len(rows),
        "mean_loss": sum(row["loss"] for row in rows) / len(rows),
        "scenario_scores": rows,
    }
