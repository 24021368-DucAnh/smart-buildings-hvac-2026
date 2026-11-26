"""Reproduce the B01 field/unit/chronology audit on public training scenarios.

Raw observation responses are read only here to check units. This module is an
offline audit tool, never an inference feature provider or a B03 data collector.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import subprocess

REPO = Path(__file__).resolve().parents[1]
DEVICE_SOURCES = {
    "VAV": "smart_buildings/smart_control/simulator/vav.py",
    "ahs": "smart_buildings/smart_control/simulator/air_handler.py",
    "hws": "smart_buildings/smart_control/simulator/hot_water_system.py",
}


def field_semantics(device: str, measurement: str) -> tuple[str, str]:
    """Assign source-checked native units; fail closed for unreviewed fields."""
    source = DEVICE_SOURCES.get(device.split("_")[0], "")
    if not source:
        raise ValueError(f"unreviewed device {device!r}")
    if "temperature" in measurement or measurement.endswith("water_setpoint"):
        return "K", source
    if "pressure" in measurement:
        return ("bar" if device == "hws" else "Pa"), source
    if "flowrate" in measurement:
        return "m^3/s", source
    if "percentage" in measurement:
        return "fraction [0,1]", source
    if "count" in measurement:
        return "count", source
    if "run_command" in measurement or "run_status" in measurement:
        return "binary {0,1}", source
    raise ValueError(f"unreviewed measurement {measurement!r}")


def verify_normalization(measurement: str, observed: float, native: float,
                         constants: dict) -> dict:
    constant = constants.get(measurement)
    mean, std = (constant["sample_mean"], constant["sample_std"]) if constant else (0., 1.)
    recovered = observed * std + mean
    if not math.isfinite(recovered) or not math.isclose(recovered, native, rel_tol=1e-5, abs_tol=2e-4):
        raise ValueError(f"normalization/native mismatch for {measurement}: {recovered} vs {native}")
    return dict(normalization="standard_score" if constant else "identity",
                mean=mean, std=std, reconstructed_native=recovered)


def verify_chronology(before: str, after: str, expected_seconds: float) -> None:
    elapsed = (datetime.fromisoformat(after) - datetime.fromisoformat(before)).total_seconds()
    if elapsed != expected_seconds:
        raise ValueError(f"wrong transition interval: {elapsed} vs {expected_seconds}")


def observation_rows(env, obs, meta, scenario):
    raw = {}
    for response in env._last_observation_response.single_observation_responses:
        request = response.single_observation_request
        raw[(request.device_id, request.measurement_name)] = response
    rows = []
    for index, field in enumerate(meta["observation_field_names"]):
        pair = env._id_map.inv.get(field)
        row = dict(scenario=scenario, kind="observation", index=index, field=field,
                   dtype="float32", available_at_inference=True,
                   missing_rule="carry previous valid response; error if no usable past value",
                   leakage_risk="use current/past only; future observation is a label")
        if pair in raw:
            response = raw[pair]
            device, measurement = pair
            unit, source = field_semantics(device, measurement)
            norm = verify_normalization(measurement, float(obs[index]), response.continuous_value,
                                        meta["observation_normalization_metadata"])
            row.update(device=device, measurement=measurement, native_unit=unit, source=source,
                       normalization=norm["normalization"], mean=norm["mean"], std=norm["std"],
                       observed_at_reset=float(obs[index]), native_at_reset=response.continuous_value)
        else:
            if field == "num_occupants":
                unit, transform = "count", "(native-125)/126"
            elif field in ("comfort_mode_now", "comfort_mode_soon"):
                unit, transform = "binary {0,1}", "identity; soon is current schedule +60 minutes"
            elif field.startswith(("hod_", "dow_")):
                unit, transform = "dimensionless", "cyclic sine/cosine"
            else:
                raise ValueError(f"unreviewed auxiliary field: {field}")
            row.update(device="environment", measurement=field, native_unit=unit,
                       source="smart_buildings/smart_control/environment/environment.py",
                       normalization=transform, mean="", std="", observed_at_reset=float(obs[index]), native_at_reset="")
        rows.append(row)
    return rows


def audit_scenario(pair: str, steps: int):
    import numpy as np
    from smart_buildings.evaluate import (POLICY_MAP, create_building_meta_data,
                                         initialize_policy, load_hybrid_environment, validate_action)
    from smart_buildings.smart_control.environment.hybrid_action_environment import is_discrete_action

    scenario_dir = REPO / "smart_buildings/training_scenarios" / pair
    env = load_hybrid_environment(scenario_dir / "config.gin")
    env._occupancy_normalization_constant = 125.
    try:
        obs, _ = env.reset()
        meta = create_building_meta_data(env, scenario_dir)
        if obs.dtype != np.float32 or not np.isfinite(obs).all():
            raise ValueError("invalid observation vector")
        rows = observation_rows(env, obs, meta, pair)
        counts = dict(continuous_action=0, discrete_action=0)
        for field in env.action_names:
            device, measurement = env._id_map.inv[field]
            unit, source = field_semantics(device, measurement)
            group = "discrete_action" if is_discrete_action(field) else "continuous_action"
            normalizer = env.action_normalizers[measurement]
            rows.append(dict(scenario=pair, kind=group, index=counts[group], field=field,
                             device=device, measurement=measurement, dtype="int32" if group == "discrete_action" else "float32",
                             native_unit=unit, source=source, available_at_inference=True,
                             normalization="0/1 hybrid command" if group == "discrete_action" else "bounded affine [-1,1]",
                             native_min=normalizer.min_native_value, native_max=normalizer.max_native_value,
                             missing_rule="reject missing or invalid action", leakage_risk="command is not measured position"))
            counts[group] += 1
        policy = initialize_policy(POLICY_MAP["pid_water"], meta, env.action_spec())
        transitions = []
        for _ in range(steps):
            before = env.current_simulation_timestamp.isoformat()
            action = validate_action(policy.get_action(obs.copy()), env.action_spec())
            next_obs, reward, terminated, truncated, _ = env.step(action)
            after = env.current_simulation_timestamp.isoformat()
            verify_chronology(before, after, env.time_step_sec)
            observation_rows(env, next_obs, meta, pair)  # verify all sensor units after stepping too
            zone = meta["zone_temp_indices"][0]
            field = meta["observation_field_names"][zone]
            measurement = env._id_map.inv[field][1]
            scale = meta["observation_normalization_metadata"][measurement]["sample_std"]
            transitions.append(dict(t=before, next_t=after, action_dtype_discrete=str(action["discrete_action"].dtype),
                                    action_dtype_continuous=str(action["continuous_action"].dtype),
                                    zone_field=field, delta_K=float((next_obs[zone] - obs[zone]) * scale),
                                    reward_finite=bool(np.isfinite(reward)),
                                    next_observation_finite=bool(np.isfinite(next_obs).all())))
            obs = next_obs
            if terminated or truncated:
                break
        return rows, dict(scenario=pair, fields=len(meta["observation_field_names"]),
                          **counts, transitions=transitions, all_sensor_unit_assertions_passed=True,
                          action_lag_note="step applies request before wait_time; no extra command queue observed in source. Physical response/clamping is not action equality.")
    finally:
        env.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPO / "artifacts/data_audit")
    parser.add_argument("--steps", type=int, choices=(1, 2), default=2)
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    rows, checks = [], []
    for pair in ("building_train_1/fairbanks_1", "building_train_8/fairbanks_8"):
        scenario_rows, check = audit_scenario(pair, args.steps)
        rows.extend(scenario_rows)
        checks.append(check)
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with (args.output_dir / "fields.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    report = dict(source_sha=sha, policy="pid_water (provisional)", scenarios=checks,
                  scope="B01 unit/chronology audit only; not control scoring, causal/action-variation evidence or B03 collection")
    (args.output_dir / "checks.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(dict(output_dir=str(args.output_dir), dictionary_rows=len(rows), scenarios=checks), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
