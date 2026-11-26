# Member B Data Dictionary and Leakage Notes

Status: B01 source and runtime audit against group commit `78d8b62f6d13454dc83370b1adf7be88190b5720`, repeated on 21/11/2026. The field-level dictionary is [`data_dictionary_fields.csv`](data_dictionary_fields.csv): 807 observation/action rows across two different buildings. Runtime assertions and short transitions are in [`data_audit_checks.json`](data_audit_checks.json). Reproduce with `python -m team_tools.audit_data --output-dir artifacts/data_audit_new` from the repository root (new output path required). Field order is building-specific and must come from `building_meta_data["observation_field_names"]`.

## Policy-visible data

`TransferPolicy.__init__(building_meta_data, action_spec)` receives static layout/action metadata. Each `get_action(obs)` receives one current `float32` observation vector. Its positions are named by `observation_field_names`; use the supplied indices and normalization metadata instead of assuming a fixed building or zone layout.

| Observation group | Typical fields (one or more per device) | Representation / meaning | Availability and leakage rule |
| --- | --- | --- | --- |
| Zone/VAV sensors | Flattened names such as `VAV_1_zone_air_temperature_sensor`, plus heating/cooling setpoint sensors | Temperatures use native Kelvin before normalization. The response measurement name used for normalizing a VAV temperature is the bare `zone_air_temperature_sensor`; the flattened vector adds the VAV ID. | Current measurement/setpoint only. No simulator grid or future temperature. |
| Zone/VAV actuator readings | `supply_air_damper_percentage_command`, `reheat_valve_percentage_command`, `supply_air_flowrate_setpoint` | Current observable command/position and airflow setpoint. A command is not guaranteed to equal the physical position after simulator limits. | Current observation only. Do not substitute a future action or hidden actuator state. |
| AHU | Flattened names such as `ahs_ahu_1_supply_air_temperature_sensor`, per-AHU setpoints, pressure, flow, recirculation, cooling-request count and run status | Mix of temperature, pressure, flow, count and status. In the shipped configurations, prefixed AHU measurement names do not match bare normalization-map keys and can remain in native units. | Only fields in `obs`; do not inspect the simulator object or internal plant state. |
| Hot-water system | Supply-water temperature and setpoint; pump status/pressure fields where present | Temperature in Kelvin before normalization; other units follow the field metadata and native action/observation source. | Current observations only. |
| Outside air | `outside_air_temperature_sensor` | Native temperature in Kelvin. In the shipped example normalizer its mean is 295 K and standard deviation is 10 K. | Current sensor only; not future weather values from the scenario file. |
| Time and schedule | Cyclic hour/day features, `comfort_mode_now`, `comfort_mode_soon` | Time is represented by sine/cosine features; comfort flags are binary floats. `soon` refers to the simulator's current-time schedule 60 minutes ahead. | These are policy-visible current-time features. Do not read future schedule state from the environment. |
| Occupancy | `num_occupants` | One normalized building-level value: `(occupants - 125) / 126` in the evaluator setup. | Use this feature only. Do not call simulator occupancy generators or query latent occupant state. |

The environment returns a flat vector in `field_names` order. Its length scales with the number of zones and AHUs. Invalid/missing sensor responses may be filled from the previous valid observation by the environment; the vector does not add an explicit missingness mask. Preserve timestamps and data-quality counts in collected datasets so carry-forward values are visible during analysis.

## Normalization and units

For a field whose exact measurement name is present in the scenario's observation normalization map, the standard-score transform is:

`normalized = (native - sample_mean) / sqrt(sample_variance)`

The shipped `building_train_1/fairbanks_1` configuration uses the following examples:

| Exact measurement name | Native unit | Mean | Standard deviation | Notes |
| --- | --- | ---: | ---: | --- |
| `zone_air_temperature_sensor` | K | 295 | 5 K | Verify whether the runtime's exact field key matches; do not infer from a similar name. |
| `supply_air_temperature_sensor` | K | 290 | 5 K | Same exact-name rule. |
| `supply_air_temperature_setpoint` | K | 290 | 5 K | Related cooling/heating setpoint names are explicitly mapped in the shipped config. |
| `outside_air_temperature_sensor` | K | 295 | 10 K | Exact key in shipped config. |
| `supply_water_setpoint` | K | 330 | 20 K | Exact key in shipped config. |
| `differential_pressure_setpoint` | bar (HWS) | 10 | 6 | `pump.py` and `hot_water_system.py` define water pressure in bar. AHU static pressure is Pa. The generic environment display helper labels all pressure as Pascal; use the actual device source. |
| `run_status`, `supervisor_run_command` | status/command | 0.5 | 0.5 | Binary values become -1/+1. |
| `cooling_request_count` | count | 50 | 50 | Exact map key; the generated AHU prefix may cause a field to use identity normalization instead. |
| damper/reheat percentage commands | fraction | 0.5 | 0.5 | Exact map keys. |

The normalizer performs an exact lookup on the response measurement name. That name can differ from `field_names`, which contains a device prefix. A measurement name absent from the map uses mean 0 and variance 1, so it passes through unchanged. The group repo's own config comments warn that prefixed AHU measurements miss bare normalization keys. Runtime `observation_normalization_metadata` plus the field/device mapping are the source of truth; the flat field string alone is not enough. Do not apply Kelvin conversion to a value unless the mapping is verified. For a verified z-scored zone temperature, recover Kelvin as `native_K = normalized * sample_std + sample_mean`; a one-step delta can be recovered as `delta_K = (normalized_next - normalized_now) * sample_std` only when both values share the same field normalization.

## Runtime checks performed

Environment reset and two successive steps were inspected for `building_train_1/fairbanks_1` and `building_train_8/fairbanks_8`. The resulting observation vectors were finite `float32`, with 352 vs 283 fields and action dimensions `(discrete, continuous)` of `(5, 92)` vs `(4, 71)`. The script verifies every sensor against the already-captured raw response at reset and after each step, without re-reading stateful sensors. This confirms code must use runtime metadata rather than fixed offsets. The CSV includes exact device/measurement keys, source, units, dtype, normalization, inference availability, missingness rule and leakage risk for each field, plus native bounds for every action.

For `VAV_1_zone_air_temperature_sensor`, both environments returned `-0.2`. Using the exact VAV normalizer (`mean=295 K`, `std=5 K`) reconstructs `294 K`; an audit-only read of simulator state was also `294 K`. For `ahs_ahu_1_supply_air_temperature_sensor`, the vector value was `298 K`, matching its native audit-only sensor value; the prefixed AHU field is therefore observed in identity/native units in these configurations despite the bare `supply_air_temperature_sensor` normalization entry. Hidden simulator state was used only to validate unit conversion and is not an allowed model feature.

Continuous **actions** use separate per-actuator bounded normalization to `[-1, 1]`; the discrete AHU/pump run commands are `0/1`. Zero continuous action means the midpoint of the native range, not equipment-off. The environment converts normalized actions back to native commands before applying them.

Four short transitions passed exact 300-second timestamp advancement and finite observation/reward checks. The first observed zone temperature was unchanged in the first step in both buildings; this is a measured simulator result, not evidence of a shifted record. `step()` applies the request before `wait_time()` advances the simulator; source inspection found no additional action-delay queue. Equipment dynamics and ventilation/reheat clamps still make a command different from measured position. This audit establishes API chronology and units, not a causal response model or sufficient action excitation.

B03 phase audit (22/11) explains the first unchanged reading: in
`SimulatorFlexibleGeometries.execute_step_sim`, `vav.update_settings` latches the
zone sensor before `finite_differences_timestep` updates the thermal field. After
one step the VAV_1 policy sensor was still about 294 K, while the audit-only grid
average was 294.06242 K; at the next step the sensor became 294.06241 K. Thus a
policy-visible sensor returned after a step generally reflects the pre-solve
physical state. The API transition remains `(obs_t, action_t, obs_t+1)`; the
one-step target is a **sensor** delta, and current action's thermal effect may
only become visible at a later sensor update. B04 should consider previous
action features and explicit horizons, using only observed history. Do not shift
rows silently, claim instantaneous actuator causality, or replace sensor labels
with hidden grid values. Grid values were used only in this offline audit and
are excluded from the dataset features. The detailed evidence is included in
the B03 verification report.

## Transition timing and permitted targets

At time index `t`, collect the current observation `obs_t`, ask the policy for `action_t`, then call the environment step. That step applies the action, advances the simulation and returns `obs_t+1` and reward. Store the pair `(obs_t, action_t, obs_t+1)` without shifting timestamps. The default one-step learning target is the zone-specific `ΔT[t+1] = T[t+1] - T[t]` in Kelvin. Reward, `info`, tracker internals, floor-plan temperature grids and any `obs_t+1` field are labels/diagnostics only; they are not inference features.

Use building IDs and seed IDs to define group splits and diagnostics, never as model features. Split by building (and keep generated-dev and reserved holdout seeds and weather strips disjoint); a random row split leaks adjacent transitions from the same episodes. Baseline data may not include enough action variation to support causal claims about actuator response.

## Audit checklist

- [x] Observation source, normalization implementation, action scaling and step ordering inspected in source.
- [x] Latent simulator fields and future observations excluded from the policy-input contract.
- [x] Field-level observation/action dictionary and reproducible runtime audit saved for two different buildings.
- [x] Native-unit normalization assertions checked for all sensor observations at reset and after two steps per building.
- [x] Short API chronology, variable dimensions and action dtypes verified on real simulator transitions.
- [x] `obs_t`, `action_t`, `obs_t+1` chronology and action variation validated on six full B03 trajectories (23/11/2026): 51,840 transitions, 3,568,320 zone-transition labels; see `B03_checks.json`.


B03 follow-up (23/11): all six episodes passed exact 300-second chronology,
field/source mapping, native-unit and target assertions. No raw-invalid sensor
values, masked labels, duplicate timestamps or nonfinite values were found; no
rows were dropped. This is a structural/unit audit, not proof of comfort or
physical plausibility: Atlanta includes a valid sensor delta of -15.6831 K in
five minutes (VAV_7, step 1260). Preserve it and investigate before B04 model
claims; do not silently clip/filter or infer causality from these baseline logs.
The 807-row CSV remains a representative two-building dictionary; each B03
metadata file supplies exact field order/normalizers/mapping for that layout.
Hidden building IDs and future/latent state remain excluded from inference.
