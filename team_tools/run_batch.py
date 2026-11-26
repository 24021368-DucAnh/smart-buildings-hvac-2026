"""Run a bounded, sequential batch through the official evaluator."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
import zipfile
import ast

from team_tools.benchmark import BenchmarkError, config_fingerprint, load_suite, scenario_key

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "configs" / "benchmark_manifest.yaml"
DEFAULT_SCENARIOS = REPO_ROOT / "smart_buildings" / "training_scenarios"
DEFAULT_OUTPUT = REPO_ROOT / "artifacts" / "benchmark_runs"
REGISTRY_PATH = REPO_ROOT / "experiments" / "registry.csv"
REGISTRY_FIELDS = [
    "experiment_id", "utc_time", "owner", "branch", "commit_sha", "base_sha",
    "module_flags", "config_hash", "simulator_sha", "scenario_manifest",
    "step_count", "scenario_count", "mean_loss", "mean_delta_vs_base",
    "worst_case_loss", "regressed_scenarios", "runtime_wall_s", "cpu_core_hours",
    "status", "artifact_uri", "notes",
]
THREAD_LIMITS = {name: "1" for name in (
    "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
    "NUMBA_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
)}
EVALUATOR_BOOTSTRAP = """
import json, runpy, sys, time
from pathlib import Path
runtime = Path(sys.argv[1])
sys.argv = sys.argv[2:]
started = time.process_time()
try:
    runpy.run_module('smart_buildings.evaluate', run_name='__main__')
finally:
    runtime.write_text(json.dumps({'process_cpu_s': time.process_time()-started}), encoding='utf-8')
"""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def git_value(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def numeric_source_pin() -> dict[str,str]:
    names=subprocess.check_output(['git','ls-files','-z','--','smart_buildings','team/policy','team/evaluate_a.py','score_leaderboard.py'],cwd=REPO_ROOT).decode('utf-8').strip('\0').split('\0')
    if 'smart_buildings/evaluate.py' not in names:raise BenchmarkError('cannot identify numerical source tree')
    for folder in ('smart_buildings','team/policy'):
        names.extend(str(p.relative_to(REPO_ROOT)).replace('\\','/') for p in (REPO_ROOT/folder).rglob('*.py')
                     if not {'metrics','results','__pycache__'} & set(p.parts))
    return {name:sha256_bytes((REPO_ROOT/name).read_bytes()) for name in sorted(set(names)) if name}


def verify_numeric_pin(pin,repo=None):
    repo=repo or REPO_ROOT
    for name,checksum in pin.items():
        path=repo/name
        if not path.is_file() or sha256_bytes(path.read_bytes())!=checksum:
            raise BenchmarkError('numerical source/input changed during run: '+name)


def scenario_input_pin(scenarios_dir,scenarios,repo=None):
    from team_tools.dataset import portable_gin_config
    repo=repo or REPO_ROOT
    paths=set()
    for pair in scenarios:
        directory=scenarios_dir/pair['building']/pair['weather']
        paths.update(directory/name for name in ('config.gin','config.yaml','floor_plan.npy','zone_map.npy'))
        text,_=portable_gin_config((directory/'config.gin').read_text(encoding='utf-8'))
        for field in ('weather_csv_path','floor_plan_filepath','zone_map_filepath'):
            match=re.search(rf'(?m)^\s*{field}\s*=\s*([\x22\x27].*[\x22\x27])\s*(?:#.*)?$',text)
            if not match:raise BenchmarkError('cannot pin scenario input macro: '+field)
            path=Path(ast.literal_eval(match[1]));paths.add(path if path.is_absolute() else repo/path)
    return {str(path.resolve()).replace('\\','/'):sha256_bytes(path.read_bytes()) for path in paths}


def changed_source_paths():
    tracked=git_value('diff','--name-only','--no-renames','-z','HEAD')
    untracked=git_value('ls-files','-z','--others','--exclude-standard')
    return sorted(set((tracked+'\0'+untracked).strip('\0').split('\0'))-{''})


def current_worktree_fingerprint() -> tuple[bool, str]:
    """Hash current changed files so a dirty run still has a reproducible ID."""
    records: list[tuple[str, str]] = []
    for relative in changed_source_paths():
        path = REPO_ROOT / relative
        digest = sha256_bytes(path.read_bytes()) if path.is_file() else "DELETED"
        records.append((relative.replace("\\", "/"), digest))
    status = git_value("status", "--porcelain", "--untracked-files=all")
    fingerprint = sha256_bytes(
        json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    return bool(status), fingerprint


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def append_registry(row: dict[str, Any]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    exists = REGISTRY_PATH.exists() and REGISTRY_PATH.stat().st_size > 0
    with REGISTRY_PATH.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=REGISTRY_FIELDS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in REGISTRY_FIELDS})


def _parse_pair(value: str, expected: list[dict[str, str]]) -> dict[str, str]:
    if value.count("/") != 1:
        raise BenchmarkError("--scenario must use BUILDING/WEATHER form")
    building, weather = value.split("/", 1)
    match = next(
        (pair for pair in expected if scenario_key(pair).casefold() == value.casefold()),
        None,
    )
    if match is None:
        raise BenchmarkError(f"scenario is not declared in the selected suite: {value}")
    return match


def _validate_summary(path: Path, policy: str, steps: int) -> None:
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise BenchmarkError(f"evaluator did not write a valid summary at {path}: {error}") from error
    if not isinstance(summary, dict) or summary.get("policy") != policy:
        raise BenchmarkError(f"evaluator summary policy mismatch at {path}")
    if summary.get("total_steps") != steps:
        raise BenchmarkError(
            f"evaluator summary has {summary.get('total_steps')!r} steps at {path}; "
            f"expected {steps}"
        )
    reward = summary.get("total_reward")
    if isinstance(reward, bool) or not isinstance(reward, (int, float)) or not math.isfinite(reward):
        raise BenchmarkError(f"evaluator summary has invalid total_reward at {path}")


def run_batch(args: argparse.Namespace) -> int:
    if args.steps not in (288, 8640):
        raise BenchmarkError("steps must be 288 (smoke) or 8640 (full episode)")
    if args.timeout_seconds <= 0:
        raise BenchmarkError("timeout-seconds must be positive")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.policy):
        raise BenchmarkError("policy must be a safe key without path separators")

    manifest_path = args.manifest.resolve()
    manifest, declared_pairs = load_suite(manifest_path, args.suite, REPO_ROOT)
    scenarios = (
        [_parse_pair(args.scenario, declared_pairs)]
        if args.scenario
        else declared_pairs
    )
    scenarios_dir = (args.scenarios_dir or REPO_ROOT / manifest["suites"][args.suite].get(
        "scenarios_dir", str(DEFAULT_SCENARIOS)
    )).resolve()
    for pair in scenarios:
        config = scenarios_dir / pair["building"] / pair["weather"] / "config.gin"
        if not config.is_file():
            raise BenchmarkError(f"scenario config.gin is missing: {config}")

    experiment_id = args.experiment_id or (
        f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", experiment_id):
        raise BenchmarkError("experiment ID must be 1–64 safe filename characters")
    run_root = (args.output_root.resolve() / experiment_id)
    if run_root.exists():
        raise BenchmarkError(f"run output already exists; refusing to overwrite: {run_root}")

    numeric_pin=numeric_source_pin()
    numeric_pin.update(scenario_input_pin(scenarios_dir,scenarios))
    run_root.mkdir(parents=True)
    (run_root / "manifest.yaml").write_bytes(manifest_path.read_bytes())
    results_dir = run_root / "results"
    dirty, worktree_hash = current_worktree_fingerprint()
    # Preserve changed source bytes, not just a hash of a dirty checkout.
    patch_bytes = subprocess.check_output(["git", "diff", "--binary", "HEAD"], cwd=REPO_ROOT)
    (run_root / "tracked_changes.patch").write_bytes(patch_bytes)
    with zipfile.ZipFile(run_root / "changed_files.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for relative in changed_source_paths():
            path = REPO_ROOT / relative
            if path.is_file():
                archive.write(path, relative)
    commit_sha = git_value("rev-parse", "HEAD")
    configs = []
    for pair in scenarios:
        scenario_dir = scenarios_dir / pair["building"] / pair["weather"]
        config_hashes = {}
        for filename in ("config.gin", "config.yaml", "floor_plan.npy", "zone_map.npy"):
            path = scenario_dir / filename
            if path.is_file():
                config_hashes[filename] = sha256_bytes(path.read_bytes())
        configs.append({"scenario": scenario_key(pair), "hashes": config_hashes})

    manifest_hash = sha256_bytes(manifest_path.read_bytes())
    run_config = {
        "suite": args.suite,
        "policy": args.policy,
        "steps": args.steps,
        "manifest_sha256": manifest_hash,
        "scenarios": [scenario_key(pair) for pair in scenarios],
        "scenario_config_hashes": configs,
    }
    config_hash = config_fingerprint(run_config)
    now = datetime.now(timezone.utc).isoformat()
    record: dict[str, Any] = {
        "source_guard": "before_after_sha256_v1",
        "numeric_sources_sha256": numeric_pin,
        "evaluator_bootstrap": EVALUATOR_BOOTSTRAP,
        "experiment_id": experiment_id,
        "started_at_utc": now,
        "owner": "B",
        "branch": git_value("branch", "--show-current"),
        "commit_sha": commit_sha,
        "simulator_sha": commit_sha,
        "upstream_sha": manifest.get("upstream_sha"),
        "working_tree_dirty": dirty,
        "working_tree_sha256": worktree_hash,
        "suite": args.suite,
        "policy": args.policy,
        "step_count": args.steps,
        "scenario_count_expected": len(scenarios),
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_hash,
        "config_hash": config_hash,
        "run_config": run_config,
        "scenario_configs": configs,
        "runtime_wall_s": None,
        "status": "RUNNING",
        "results_dir": str(results_dir),
        "workers": 1,
        "runtime_environment": {
            "python": sys.version, "executable": sys.executable, "platform": platform.platform(),
            "packages": sorted(f"{dist.metadata['Name']}=={dist.version}" for dist in importlib.metadata.distributions()),
            "uv_lock_sha256": sha256_bytes((REPO_ROOT / "uv.lock").read_bytes()),
            "thread_limits": THREAD_LIMITS, "PYTHONHASHSEED": "0",
        },
        "scenario_runs": [],
    }
    metadata_path = run_root / "run.json"
    atomic_write_json(metadata_path, record)
    start_time = time.perf_counter()

    try:
        for pair in scenarios:
            verify_numeric_pin(numeric_pin)
            key = scenario_key(pair)
            scenario_started = time.perf_counter()
            run_item: dict[str, Any] = {
                "scenario": key,
                "status": "RUNNING",
                "config_hashes": next(
                    item["hashes"] for item in configs if item["scenario"] == key
                ),
            }
            record["scenario_runs"].append(run_item)
            atomic_write_json(metadata_path, record)

            cpu_path = run_root / f"{pair['building']}__{pair['weather']}.runtime.json"
            command = [
                sys.executable, "-c", EVALUATOR_BOOTSTRAP, str(cpu_path), "smart_buildings.evaluate",
                "--policies", args.policy,
                "--scenarios-dir", str(scenarios_dir),
                "--results-dir", str(results_dir),
                "--buildings", pair["building"],
                "--weathers", pair["weather"],
                "--steps", str(args.steps),
            ]
            child_env = os.environ.copy()
            child_env["PYTHONUTF8"] = "1"
            child_env["PYTHONIOENCODING"] = "utf-8"
            child_env.update(THREAD_LIMITS)
            child_env["PYTHONHASHSEED"] = "0"
            try:
                completed = subprocess.run(
                    command,
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=child_env,
                    timeout=args.timeout_seconds,
                    check=False,
                )
                run_item["return_code"] = completed.returncode
                if cpu_path.is_file():
                    run_item["process_cpu_s"] = json.loads(cpu_path.read_text())["process_cpu_s"]
                (run_root / f"{pair['building']}__{pair['weather']}.stdout.log").write_text(
                    completed.stdout, encoding="utf-8"
                )
                (run_root / f"{pair['building']}__{pair['weather']}.stderr.log").write_text(
                    completed.stderr, encoding="utf-8"
                )
                if completed.returncode != 0:
                    run_item["status"] = "FAILED"
                    record["status"] = "FAILED"
                    record["failure"] = f"evaluator exited {completed.returncode} on {key}"
                    record["scenario_runs"][-1]["runtime_wall_s"] = round(
                        time.perf_counter() - scenario_started, 3
                    )
                    atomic_write_json(metadata_path, record)
                    break
            except subprocess.TimeoutExpired as error:
                run_item["status"] = "TIMED_OUT"
                run_item["runtime_wall_s"] = round(time.perf_counter() - scenario_started, 3)
                run_item["timeout_seconds"] = args.timeout_seconds
                record["status"] = "TIMED_OUT"
                record["failure"] = f"scenario exceeded {args.timeout_seconds}s: {key}"
                (run_root / f"{pair['building']}__{pair['weather']}.stdout.log").write_text(
                    error.stdout.decode("utf-8", errors="replace") if isinstance(error.stdout, bytes)
                    else error.stdout or "", encoding="utf-8"
                )
                (run_root / f"{pair['building']}__{pair['weather']}.stderr.log").write_text(
                    error.stderr.decode("utf-8", errors="replace") if isinstance(error.stderr, bytes)
                    else error.stderr or "", encoding="utf-8"
                )
                atomic_write_json(metadata_path, record)
                break

            run_item["runtime_wall_s"] = round(time.perf_counter() - scenario_started, 3)
            summary_path = results_dir / pair["building"] / pair["weather"] / args.policy / "summary.json"
            _validate_summary(summary_path, args.policy, args.steps)
            verify_numeric_pin(numeric_pin)
            run_item["summary_sha256"] = sha256_bytes(summary_path.read_bytes())
            run_item["status"] = "SUCCEEDED"
            run_item["summary_path"] = str(summary_path)
            atomic_write_json(metadata_path, record)
        else:
            record["status"] = "SUCCEEDED_SMOKE" if args.steps == 288 else "SUCCEEDED_FULL"
    except BenchmarkError as error:
        record["status"] = "FAILED_VALIDATION"
        record["failure"] = str(error)
        if record["scenario_runs"]:
            record["scenario_runs"][-1]["status"] = "FAILED_VALIDATION"
    except OSError as error:
        record["status"] = "FAILED_EXECUTION"
        record["failure"] = str(error)
        if record["scenario_runs"]:
            record["scenario_runs"][-1]["status"] = "FAILED_EXECUTION"
    finally:
        if record["status"] == "RUNNING":
            record["status"] = "FAILED_INTERNAL"
            record["failure"] = "run interrupted by an unexpected error; inspect process traceback"
            if record["scenario_runs"] and record["scenario_runs"][-1]["status"] == "RUNNING":
                record["scenario_runs"][-1]["status"] = "FAILED_INTERNAL"
        record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        record["runtime_wall_s"] = round(time.perf_counter() - start_time, 3)
        cpu_values = [item.get("process_cpu_s") for item in record["scenario_runs"]]
        record["cpu_core_hours"] = (
            sum(cpu_values) / 3600 if cpu_values and all(isinstance(v, (int, float)) for v in cpu_values)
            else None
        )
        atomic_write_json(metadata_path, record)
        registry_status = record["status"]
        append_registry(
            {
                "experiment_id": experiment_id,
                "utc_time": now,
                "owner": "B",
                "branch": record["branch"],
                "commit_sha": commit_sha,
                "base_sha": "",
                "module_flags": f"policy={args.policy}; provisional; suite={args.suite}",
                "config_hash": config_hash,
                "simulator_sha": commit_sha,
                "scenario_manifest": f"{manifest_path}; suite={args.suite}; sha256={manifest_hash}",
                "step_count": args.steps,
                "scenario_count": len(scenarios),
                "runtime_wall_s": record["runtime_wall_s"],
                "cpu_core_hours": record["cpu_core_hours"] if record["cpu_core_hours"] is not None else "",
                "status": registry_status,
                "artifact_uri": str(run_root),
                "notes": "Scores left blank unless a full declared suite is scored.",
            }
        )

    print(json.dumps({
        "experiment_id": experiment_id,
        "status": record["status"],
        "scenarios_completed": sum(item["status"] == "SUCCEEDED" for item in record["scenario_runs"]),
        "scenarios_expected": len(scenarios),
        "steps": args.steps,
        "runtime_wall_s": record["runtime_wall_s"],
        "run_metadata": str(metadata_path),
    }, indent=2))
    return 0 if record["status"] in ("SUCCEEDED_SMOKE", "SUCCEEDED_FULL") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--suite", choices=("dev_small", "dev_full", "generated_dev", "frozen_holdout"), default="dev_small")
    parser.add_argument("--policy", default="pid_water")
    parser.add_argument("--steps", type=int, choices=(288, 8640), default=8640)
    parser.add_argument("--scenario", help="Optional single declared pair, BUILDING/WEATHER")
    parser.add_argument("--scenarios-dir", type=Path, help="Override the selected suite's scenario directory")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--experiment-id")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        return run_batch(build_parser().parse_args(argv))
    except BenchmarkError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
