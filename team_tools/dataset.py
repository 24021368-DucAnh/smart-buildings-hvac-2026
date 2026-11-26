"""B03 transition schema, group splits, and strict offline dataset validation."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import zipfile
import ast

import numpy as np

from team_tools.benchmark import BenchmarkError, load_suite, load_yaml_mapping, scenario_key, validate_scenarios

SCHEMA_VERSION = 1
ROOT_FILES = {"dataset_manifest.yaml", "benchmark_manifest.yaml", "schema.json", "tracked_changes.patch", "changed_files.zip"}
EPISODE_FILES = {"arrays.npz", "metadata.json", "quality.json", "episode.json"}
ARRAY_SCHEMA = {
    "observations": ("float32", "(T+1,D): normalized policy-visible observations"),
    "observations_native": ("float64", "(T+1,D): reconstructed native units, never latent state"),
    "observation_valid": ("bool", "(T+1,D): validity before carry-forward; auxiliary features true"),
    "continuous_action": ("float32", "(T,C): chosen normalized command at t"),
    "continuous_action_native": ("float64", "(T,C): affine conversion of chosen command"),
    "discrete_action": ("int32", "(T,K): chosen 0/1 command at t"),
    "zone_temperature_K": ("float64", "(T+1,Z): reconstructed zone temperature in Kelvin"),
    "delta_temperature_K": ("float32", "(T,Z): label T[t+1]-T[t]"),
    "target_valid": ("bool", "(T,Z): both zone observations valid before imputation"),
    "rewards": ("float64", "(T,): diagnostics only, never inference features"),
    "timestamps": ("unicode", "(T+1,): simulator-native ISO timestamps; naive remains naive"),
    "step_index": ("int32", "(T,): unique transition index, zero based"),
    "terminated": ("bool", "(T,): environment termination flags"),
    "truncated": ("bool", "(T,): environment truncation flags"),
}
FEATURE_CONTRACT = {
    "features": ["observations[t]", "continuous_action[t]", "discrete_action[t]"],
    "labels": ["delta_temperature_K[t]"],
    "diagnostics_only": ["rewards", "timestamps", "step_index", "building", "scenario", "zone_ids"],
    "forbidden_at_inference": ["observations[t+1]", "future reward", "simulator internal state", "hidden building ID"],
    "preprocessing": "fit using train buildings only; validation/generated_dev never fit scalers or models",
}


class DatasetError(ValueError):
    """Dataset cannot be accepted for training or declared evaluation."""


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def portable_gin_config(text: str) -> tuple[str,list[str]]:
    """Normalize only known path macros before Gin interprets Windows escapes."""
    fields=[]
    pattern=r'^(\s*(weather_csv_path|floor_plan_filepath|zone_map_filepath|metrics_path)\s*=\s*)([\x22\x27])(.*)\3([ \t]*(?:#.*)?)$'
    def convert(match):
        raw=match[4]
        if "\\" not in raw:return match[0]
        fields.append(match[2])
        path=re.sub(r"\\+","/",raw)
        return match[1]+match[3]+path+match[3]+match[5]
    return re.sub(pattern,convert,text,flags=re.MULTILINE),fields


def load_plan(path: Path, repo: Path, validate_sources=True) -> dict:
    try:
        plan = load_yaml_mapping(path)
        if (plan.get("version") != 1 or plan.get("episode_steps") != 8640
                or plan.get("dt_seconds") != 300 or plan.get("horizon_steps") != 1
                or plan.get("split_rule") != "building_disjoint" or plan.get("policy") != "pid_water"):
            raise DatasetError("unsupported B03 plan contract")
        episodes = plan.get("episodes")
        validate_scenarios(episodes)
        owners = {}
        for episode in episodes:
            split, suite, building = episode.get("split"), episode.get("suite"), episode["building"]
            if split not in ("train", "validation", "generated_dev") or suite == "frozen_holdout":
                raise DatasetError("invalid split or forbidden holdout collection")
            if (split == "generated_dev") != (suite == "generated_dev"):
                raise DatasetError("generated-dev must remain separate from train/validation")
            previous = owners.setdefault(building.casefold(), split)
            if previous != split:
                raise DatasetError(f"building split overlap: {building}")
            if validate_sources:
                _, pairs = load_suite(repo / plan["benchmark_manifest"], suite, repo)
                if scenario_key(episode) not in {scenario_key(p) for p in pairs}:
                    raise DatasetError(f"undeclared source scenario: {scenario_key(episode)}")
        counts={split:sum(e["split"]==split for e in episodes) for split in ("train","validation","generated_dev")}
        building_counts={split:len({e["building"].casefold() for e in episodes if e["split"]==split}) for split in counts}
        climates={e["weather"].rsplit("_",1)[0] for e in episodes}
        minima={"train":3,"validation":2,"generated_dev":1}
        if len(episodes)<6 or any(building_counts[split]<count for split,count in minima.items()):
            raise DatasetError("B03 corpus requires at least 3 train / 2 validation / 1 generated-dev buildings")
        if climates!={"fairbanks","denver","phoenix","atlanta","singapore"}:
            raise DatasetError("B03 corpus must cover all five declared climates")
        return plan
    except (BenchmarkError, KeyError, TypeError) as error:
        raise DatasetError(str(error)) from error


class TransitionBuffer:
    """Keep each state once: transition i is states[i], actions[i], states[i+1]."""
    def __init__(self, metadata, observation, timestamp, valid=None):
        self.meta = metadata
        self.obs = [np.array(observation, copy=True)]
        self.times = [timestamp]
        self.valid = [np.ones(len(observation), bool) if valid is None else np.array(valid, dtype=bool, copy=True)]
        self.cont, self.disc, self.reward, self.terminated, self.truncated = [], [], [], [], []

    def append(self, action, observation, timestamp, reward, terminated, truncated, valid=None):
        self.obs.append(np.array(observation, copy=True))
        self.times.append(timestamp)
        self.valid.append(np.ones(len(observation), bool) if valid is None else np.array(valid, dtype=bool, copy=True))
        self.cont.append(np.array(action["continuous_action"], copy=True))
        self.disc.append(np.array(action["discrete_action"], copy=True))
        self.reward.append(reward)
        self.terminated.append(terminated)
        self.truncated.append(truncated)

    def arrays(self):
        m = self.meta
        obs = np.asarray(self.obs)
        native = obs.astype(np.float64) * np.asarray(m["observation_std"]) + np.asarray(m["observation_mean"])
        cont = np.asarray(self.cont).reshape(-1, len(m["continuous_fields"]))
        disc = np.asarray(self.disc).reshape(-1, len(m["discrete_fields"]))
        low, high = np.asarray(m["continuous_native_min"]), np.asarray(m["continuous_native_max"])
        zone = native[:, m["zone_indices"]]
        valid = np.asarray(self.valid, dtype=bool)
        zone_valid = valid[:, m["zone_indices"]]
        return dict(observations=obs, observations_native=native, observation_valid=valid,
                    continuous_action=cont, continuous_action_native=low + (cont.astype(np.float64)+1.)*.5*(high-low),
                    discrete_action=disc, zone_temperature_K=zone, delta_temperature_K=np.diff(zone, axis=0).astype(np.float32),
                    target_valid=zone_valid[:-1] & zone_valid[1:], rewards=np.asarray(self.reward, np.float64),
                    timestamps=np.asarray(self.times, dtype="U40"), step_index=np.arange(len(self.cont),dtype=np.int32),
                    terminated=np.asarray(self.terminated,bool), truncated=np.asarray(self.truncated,bool))


def validate_arrays(arrays: dict, meta: dict, require_full=True) -> dict:
    if set(arrays) != set(ARRAY_SCHEMA):
        raise DatasetError(f"wrong array keys: missing={set(ARRAY_SCHEMA)-set(arrays)}, extra={set(arrays)-set(ARRAY_SCHEMA)}")
    n = len(arrays["rewards"])
    d, c, k, z = (len(meta[key]) for key in ("observation_fields", "continuous_fields", "discrete_fields", "zone_ids"))
    if n < 1 or n != meta["expected_steps"] or (require_full and n != 8640):
        raise DatasetError(f"incomplete or smoke episode: {n} steps")
    shapes = dict(observations=(n+1,d),observations_native=(n+1,d),observation_valid=(n+1,d),
                  continuous_action=(n,c),continuous_action_native=(n,c),discrete_action=(n,k),
                  zone_temperature_K=(n+1,z),delta_temperature_K=(n,z),target_valid=(n,z),
                  rewards=(n,),timestamps=(n+1,),step_index=(n,),terminated=(n,),truncated=(n,))
    for key, value in arrays.items():
        dtype = ARRAY_SCHEMA[key][0]
        if not isinstance(value,np.ndarray) or value.shape != shapes[key]:
            raise DatasetError(f"wrong shape: {key}")
        if (dtype == "unicode" and value.dtype.kind != "U") or (dtype != "unicode" and value.dtype != np.dtype(dtype)):
            raise DatasetError(f"wrong dtype: {key}")
        if value.dtype.kind in "fiu" and not np.isfinite(value).all():
            raise DatasetError(f"non-finite values: {key}")
    for key in ("observation_fields","continuous_fields","discrete_fields","zone_ids"):
        if len(set(meta[key])) != len(meta[key]):
            raise DatasetError(f"duplicate metadata field: {key}")
    if len(meta["zone_indices"]) != z or any(i < 0 or i >= d for i in meta["zone_indices"]):
        raise DatasetError("invalid zone index mapping")
    if len(set(meta["zone_indices"]))!=z or len(meta.get("observation_source_keys",[]))!=d:
        raise DatasetError("missing or duplicate zone source mapping")
    for field,source in zip(meta["observation_fields"],meta["observation_source_keys"]):
        expected=source["measurement"] if source["device"]=="environment" else source["device"]+"_"+source["measurement"]
        if field!=expected:raise DatasetError("observation field label does not match its source key")
    for index,zone_id in zip(meta["zone_indices"],meta["zone_ids"]):
        source=meta["observation_source_keys"][index]
        if source.get("device")!=zone_id or source.get("measurement")!="zone_air_temperature_sensor":
            raise DatasetError("zone label does not match its exact observation source")
    if meta["dt_seconds"]!=300:
        raise DatasetError("B03 timestep must be exactly 300 seconds")
    if set(meta["zone_ids"]) != set(meta["zone_to_ahu"]):
        raise DatasetError("missing room/VAV/AHU mapping")
    try:
        times = [datetime.fromisoformat(value) for value in arrays["timestamps"]]
        if len(set(times)) != len(times) or any((b-a).total_seconds()!=meta["dt_seconds"] for a,b in zip(times,times[1:])):
            raise DatasetError("duplicate or misaligned timestamps")
    except (TypeError, ValueError) as error:
        raise DatasetError(f"invalid timestamps: {error}") from error
    if not np.array_equal(arrays["step_index"],np.arange(n,dtype=np.int32)):
        raise DatasetError("duplicate or misordered transition indices")
    if arrays["terminated"][:-1].any() or arrays["truncated"][:-1].any():
        raise DatasetError("episode continued after termination")
    mean,std=np.asarray(meta["observation_mean"]),np.asarray(meta["observation_std"])
    if mean.shape!=(d,) or std.shape!=(d,) or not np.isfinite(mean).all() or not np.isfinite(std).all() or (std<=0).any():
        raise DatasetError("invalid/invertible normalization metadata")
    native=arrays["observations"].astype(np.float64)*std+mean
    if not np.allclose(arrays["observations_native"],native,rtol=0,atol=1e-9):
        raise DatasetError("native/normalized values disagree")
    zone=arrays["zone_temperature_K"]
    if (zone<150).any() or (zone>400).any() or not np.allclose(zone,native[:,meta["zone_indices"]],rtol=0,atol=1e-9):
        raise DatasetError("zone temperature is not reconstructed Kelvin in [150,400]")
    if not np.allclose(arrays["delta_temperature_K"],np.diff(zone,axis=0),rtol=1e-6,atol=1e-6):
        raise DatasetError("delta temperature target is shifted or uses wrong units")
    masks=arrays["observation_valid"][:,meta["zone_indices"]]
    if not np.array_equal(arrays["target_valid"],masks[:-1]&masks[1:]):
        raise DatasetError("target validity does not match both observations")
    cont,disc=arrays["continuous_action"],arrays["discrete_action"]
    if (cont < -1).any() or (cont > 1).any() or not np.isin(disc,[0,1]).all():
        raise DatasetError("action outside allowed range")
    low,high=np.asarray(meta["continuous_native_min"]),np.asarray(meta["continuous_native_max"])
    if not np.allclose(arrays["continuous_action_native"],low+(cont.astype(np.float64)+1)*.5*(high-low),rtol=0,atol=1e-9):
        raise DatasetError("native action conversion disagrees")
    return dict(steps=n,observation_dim=d,continuous_dim=c,discrete_dim=k,zones=z,
                zone_transition_samples=n*z,raw_invalid_sensor_values=int((~arrays["observation_valid"]).sum()),
                masked_zone_targets=int((~arrays["target_valid"]).sum()),rows_dropped=0,
                duplicate_timestamps=0,nonfinite_values=0,total_reward=float(arrays["rewards"].sum()),
                continuous_channels_changed=int(np.any(np.diff(cont,axis=0)!=0,axis=0).sum()),
                discrete_switches_per_channel=np.count_nonzero(np.diff(disc,axis=0),axis=0).tolist(),
                continuous_changes_per_channel=np.count_nonzero(np.diff(cont,axis=0),axis=0).tolist(),
                continuous_range_per_channel=np.ptp(cont,axis=0).tolist(),
                continuous_std_per_channel=np.std(cont.astype(np.float64),axis=0).tolist(),
                discrete_on_fraction_per_channel=np.mean(disc,axis=0).tolist(),
                action_response_claim="observational baseline data; variation alone does not identify causal action effects")


def read_snapshot(root: Path, receipt: dict) -> dict:
    """Verify immutable source/config/schema snapshots, including paused runs."""
    plan_path=root/"dataset_manifest.yaml"
    guarded=receipt.get("producer_guard")=="scoped_sha256_v1"
    required_root=ROOT_FILES|({"source_pin.json"} if guarded else set())
    if set(receipt.get("root_files",{}))!=required_root:
        raise DatasetError("missing corpus snapshot checksums")
    for name,checksum in receipt["root_files"].items():
        if digest(root/name)!=checksum:raise DatasetError(f"corpus snapshot checksum mismatch: {name}")
    if digest(plan_path)!=receipt["plan_sha256"]:
        raise DatasetError("dataset plan checksum mismatch")
    plan=load_plan(plan_path,Path(__file__).resolve().parents[1],validate_sources=False)
    schema=json.loads((root/"schema.json").read_text(encoding="utf-8"))
    if schema!=json.loads(json.dumps(dict(version=SCHEMA_VERSION,arrays=ARRAY_SCHEMA,feature_contract=FEATURE_CONTRACT))):
        raise DatasetError("unsupported or changed dataset schema/feature contract")
    return plan


def verify_manual_audit(root: Path, receipt: dict, audit: dict, item: dict, child=None):
    """Bind a recorded manual legacy producer audit; never invent worker pin proof."""
    if audit.get("source_archive_sha256")!=digest(root/"changed_files.zip"):
        raise DatasetError("legacy producer archive does not match manual audit")
    runtime=audit.get("runtime_source_sha256",{})
    if not runtime:
        raise DatasetError("legacy source has no audited runtime snapshot")
    with zipfile.ZipFile(root/"changed_files.zip") as archive:
        for name,checksum in runtime.items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=checksum:
                raise DatasetError("legacy runtime snapshot differs from manual audit")
    matched=[e for e in audit.get("completed_episodes",[]) if e["scenario"]==item["scenario"]]
    if child is None:child=json.loads((root/"episodes"/item["directory"]/"episode.json").read_text())
    if (len(matched)!=1 or matched[0].get("files")!=item.get("files")
            or matched[0].get("input_hashes")!=child.get("input_hashes")):
        raise DatasetError("legacy completed episode is not bound to manual audit")


def resolve_episode_pin(root: Path, item: dict, receipt: dict, depth=0, episode_root=None,details=False):
    """Resolve the actual producer of copied episodes through checked lineage."""
    episode_root=episode_root or root
    if depth>8:raise DatasetError("excessive or cyclic reuse lineage")
    origin=item.get("reuse_origin")
    if not origin:
        if details:return dict(root=root,item=item,receipt=receipt,audit=None)
        return digest(root/"source_pin.json") if receipt.get("producer_guard")=="scoped_sha256_v1" else None
    entry=receipt.get("lineage",{}).get(origin)
    if not isinstance(entry,dict):raise DatasetError("missing reuse provenance")
    capsule=root/entry["directory"]
    if capsule.resolve().parent!=(root/"lineage").resolve():
        raise DatasetError("unsafe reuse provenance path")
    files=entry.get("files",{})
    if "dataset.json" not in files or not ROOT_FILES.issubset(files):
        raise DatasetError("incomplete reuse source snapshots")
    for name,checksum in files.items():
        if Path(name).name!=name or not (capsule/name).is_file() or digest(capsule/name)!=checksum:
            raise DatasetError("reuse source snapshot checksum mismatch")
    prior=json.loads((capsule/"dataset.json").read_text())
    read_snapshot(capsule,prior)
    if prior.get("source_sha")!=receipt.get("source_sha") or prior.get("plan_sha256")!=receipt.get("plan_sha256"):
        raise DatasetError("reuse source SHA/plan differs from current corpus")
    matches=[e for e in prior["episodes"] if e["scenario"]==item["scenario"]]
    if len(matches)!=1 or matches[0].get("status")!="SUCCEEDED_FULL" or matches[0].get("files")!=item.get("files"):
        raise DatasetError("copied episode is not a complete original episode")
    original=matches[0]
    if original.get("reuse_origin"):
        return resolve_episode_pin(capsule,original,prior,depth+1,episode_root,details)
    if prior.get("producer_guard")=="scoped_sha256_v1":
        if "source_pin.json" not in files:raise DatasetError("missing original worker source pin")
        if details:return dict(root=capsule,item=original,receipt=prior,audit=None)
        return digest(capsule/"source_pin.json")
    if "producer_audit.json" not in files:raise DatasetError("legacy reuse requires a manual producer audit")
    # Audit binds copied episode bytes; the capsule deliberately has no duplicate arrays.
    audit=json.loads((capsule/"producer_audit.json").read_text())
    child=json.loads((episode_root/"episodes"/item["directory"]/"episode.json").read_text())
    verify_manual_audit(capsule,prior,audit,original,child)
    if details:return dict(root=capsule,item=original,receipt=prior,audit=audit)
    return None


def _canonical_pin_files(files):
    result={}
    for name,checksum in files.items():
        key=name.replace('\\','/')
        for marker in ('smart_buildings/','data/generated/'):
            if marker in key:
                key=marker+key.split(marker,1)[1];break
        if key in result and result[key]!=checksum:raise DatasetError('conflicting numerical pin aliases')
        result[key]=checksum
    return result


def verify_reuse_numeric_parity(root,item,receipt,current_pin,audit=None):
    """Compare the original leaf pin; legacy supplements must be recorded proofs.

    Do not fabricate a supplemental audit from the present checkout. Historical
    corpus reading remains possible without granting permission for new reuse.
    """
    current=_canonical_pin_files(current_pin['files'])
    core={key for key in current if key.startswith('smart_buildings/') and key.endswith('.py')}
    selected={key for key in current if '/'+item['scenario']+'/' in '/'+key}
    if not core or not any(key.endswith('/config.gin') for key in selected):
        raise DatasetError('current numerical pin lacks core/selected scenario inputs')
    config=root/'episodes'/item['directory']/'inputs/config.gin'
    text,_=portable_gin_config(config.read_text(encoding='utf-8'))
    references=set()
    for field in ('weather_csv_path','floor_plan_filepath','zone_map_filepath'):
        match=re.search(rf'(?m)^\s*{field}\s*=\s*([\x22\x27].*[\x22\x27])\s*(?:#.*)?$',text)
        if not match:raise DatasetError('missing original numerical input reference: '+field)
        value=Path(ast.literal_eval(match[1]))
        path=value if value.is_absolute() else Path(__file__).resolve().parents[1]/value
        references.add(next(iter(_canonical_pin_files({str(path.resolve()):'unused'}))))
    required=core|selected|references
    leaf=resolve_episode_pin(root,item,receipt,details=True)
    if leaf['receipt'].get('producer_guard')=='scoped_sha256_v1':
        original=json.loads((leaf['root']/'source_pin.json').read_text(encoding='utf-8'))['files']
    else:
        proof=audit if audit and 'numeric_inputs_sha256' in audit else leaf['audit']
        if proof is None or not isinstance(proof.get('numeric_inputs_sha256'),dict):
            raise DatasetError('legacy reuse needs a recorded numerical-input supplemental audit')
        child=json.loads((root/'episodes'/item['directory']/'episode.json').read_text())
        verify_manual_audit(leaf['root'],leaf['receipt'],proof,leaf['item'],child)
        original=proof['numeric_inputs_sha256']
    original=_canonical_pin_files(original)
    if any(key not in current or original.get(key)!=current[key] for key in required):
        raise DatasetError('reuse numerical source/config/weather input differs or is unproven')


def validate_episode(root, item, receipt, plan, expected_steps, require_full=True):
    key=item["scenario"]
    expected={scenario_key(e):e for e in plan["episodes"]}
    if key not in expected:raise DatasetError("undeclared episode")
    directory=root/"episodes"/item["directory"]
    if directory.resolve().parent != (root/"episodes").resolve():
        raise DatasetError("unsafe episode path")
    if set(item.get("files",{}))!=EPISODE_FILES:
        raise DatasetError("missing episode checksums")
    for filename,checksum in item["files"].items():
        if Path(filename).name!=filename or digest(directory/filename)!=checksum:
            raise DatasetError(f"artifact checksum mismatch: {key}/{filename}")
    episode=json.loads((directory/"episode.json").read_text(encoding="utf-8"))
    meta=json.loads((directory/"metadata.json").read_text(encoding="utf-8"))
    planned=expected[key]
    if (meta["scenario"]!=key or meta["split"]!=planned["split"] or meta["policy"]!=plan["policy"]
            or meta.get("building")!=planned["building"] or meta.get("weather")!=planned["weather"]
            or meta.get("suite")!=planned["suite"] or meta.get("horizon_steps")!=plan["horizon_steps"]
            or meta["expected_steps"]!=expected_steps or meta["dt_seconds"]!=plan["dt_seconds"]):
        raise DatasetError("episode identity or split mismatch")
    if (episode["status"]!=item["status"] or episode.get("scenario")!=key
            or episode.get("split")!=planned["split"] or episode.get("expected_steps")!=expected_steps
            or episode.get("steps_completed")!=expected_steps
            or episode.get("source_sha")!=receipt.get("source_sha")):
        raise DatasetError("episode receipt identity/source/steps/status mismatch")
    pin=resolve_episode_pin(root,item,receipt)
    if pin is not None and (episode.get("producer_pin_sha256")!=pin or episode.get("producer_guard")!="PASS_BEFORE_AND_AFTER"):
        raise DatasetError("worker producer/input pin was not verified before and after collection")
    inputs=episode.get("input_hashes",{})
    if not isinstance(inputs,dict) or "config.gin" not in inputs:raise DatasetError("missing input provenance")
    expected_snapshots={name for name in inputs if Path(name).suffix in (".gin",".yaml")}
    snapshot_dir=directory/"inputs"
    if not snapshot_dir.is_dir() or {p.name for p in snapshot_dir.iterdir()}!=expected_snapshots:
        raise DatasetError("missing/extra input config snapshots")
    for name in expected_snapshots:
        if Path(name).name!=name or digest(snapshot_dir/name)!=inputs[name]:raise DatasetError("input config snapshot checksum mismatch")
    runtime=episode.get("runtime_config")
    if runtime is not None or "effective_config.gin" in inputs:
        original=snapshot_dir/"config.gin";effective=snapshot_dir/"effective_config.gin"
        converted,fields=portable_gin_config(original.read_text(encoding="utf-8"))
        if (not isinstance(runtime,dict) or runtime.get("method")!="gin_path_separators_v1"
                or runtime.get("original_sha256")!=digest(original)
                or runtime.get("effective_sha256")!=digest(effective) or runtime.get("path_fields")!=fields
                or effective.read_text(encoding="utf-8")!=converted):
            raise DatasetError("effective Gin config is not the declared path-only transformation")
    with np.load(directory/"arrays.npz",allow_pickle=False) as arrays:
        quality=validate_arrays(dict(arrays),meta,require_full)
    quality.update(scenario=key,building=planned["building"],split=planned["split"])
    return quality


def verify_reuse_source(root: Path, plan_path: Path, source_sha: str, audit_path=None, environment=None,current_numeric_pin=None) -> dict:
    """Inspect snapshots; new imports additionally require current numerical parity."""
    try:
        receipt=json.loads((root/"dataset.json").read_text())
        if receipt.get("status") in (None,"RUNNING","SUCCEEDED_SMOKE") or receipt.get("steps_per_episode")!=8640:
            raise DatasetError("reuse source must be a terminal full-episode collection")
        plan=read_snapshot(root,receipt)
        if receipt.get("source_sha")!=source_sha or receipt["plan_sha256"]!=digest(plan_path):
            raise DatasetError("reuse source SHA/plan differs")
        benchmark=Path(__file__).resolve().parents[1]/plan["benchmark_manifest"]
        if digest(root/"benchmark_manifest.yaml")!=digest(benchmark):
            raise DatasetError("reuse benchmark manifest differs from current declared inputs")
        if environment is not None:
            old=receipt.get("environment",{})
            if old.get("python")!=environment["python"] or set(old.get("packages",[]))!=set(environment["packages"]):
                raise DatasetError("reuse Python/package environment differs")
        items=receipt["episodes"]
        if len({e["scenario"] for e in items})!=len(items):raise DatasetError("duplicate reuse scenarios")
        selected={e["scenario"]:e for e in items if e["status"]=="SUCCEEDED_FULL"}
        if not selected:raise DatasetError("no completed full episodes to reuse")
        audit=json.loads(audit_path.read_text()) if audit_path else None
        for item in selected.values():
            if not item.get("reuse_origin") and receipt.get("producer_guard")!="scoped_sha256_v1":
                if audit is None:raise DatasetError("legacy source requires a recorded manual producer audit")
                verify_manual_audit(root,receipt,audit,item)
            validate_episode(root,item,receipt,plan,8640)
            if current_numeric_pin is not None:
                verify_reuse_numeric_parity(root,item,receipt,current_numeric_pin,audit)
        return selected
    except (OSError,KeyError,TypeError,ValueError,zipfile.BadZipFile) as error:
        if isinstance(error,DatasetError):raise
        raise DatasetError(f"cannot verify reuse source: {error}") from error


def validate_corpus(root: Path, require_full=True) -> dict:
    receipt=json.loads((root/"dataset.json").read_text(encoding="utf-8"))
    if receipt["status"] not in ("SUCCEEDED_FULL","SUCCEEDED_SMOKE") or (require_full and receipt["status"]!="SUCCEEDED_FULL"):
        raise DatasetError("dataset is incomplete or smoke-only")
    plan=read_snapshot(root,receipt)
    expected_steps=8640 if receipt["status"]=="SUCCEEDED_FULL" else 288
    if receipt.get("steps_per_episode")!=expected_steps:
        raise DatasetError("corpus horizon does not match full/smoke status")
    expected={scenario_key(e):e for e in plan["episodes"]}
    actual={item["scenario"]:item for item in receipt["episodes"]}
    selected=receipt["selected_scenarios"]
    if (len(selected)!=len(set(selected)) or len(actual)!=len(receipt["episodes"]) or set(actual)!=set(selected)
            or (receipt["status"]=="SUCCEEDED_FULL" and set(actual)!=set(expected))):
        raise DatasetError("wrong/missing/duplicate corpus scenarios")
    discovered={p.name for p in (root/"episodes").iterdir() if p.is_dir()}
    if discovered != {item["directory"] for item in actual.values()}:
        raise DatasetError("extra or missing episode files")
    results=[]
    for key,item in actual.items():
        if key not in expected or item["status"]!=receipt["status"]:
            raise DatasetError("undeclared or failed episode")
        quality=validate_episode(root,item,receipt,plan,expected_steps,require_full)
        results.append(quality)
    return dict(status="VERIFIED_FULL_CORPUS" if require_full else "VERIFIED_SMOKE",episodes=results,
                total_transitions=sum(q["steps"] for q in results),
                total_zone_transition_samples=sum(q["zone_transition_samples"] for q in results),
                raw_invalid_sensor_values=sum(q["raw_invalid_sensor_values"] for q in results),
                masked_zone_targets=sum(q["masked_zone_targets"] for q in results),rows_dropped=0,
                splits={split:sorted({q["building"] for q in results if q["split"]==split}) for split in ("train","validation","generated_dev")})


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_dir",type=Path)
    parser.add_argument("--allow-smoke",action="store_true")
    args=parser.parse_args(argv)
    try:
        print(json.dumps(validate_corpus(args.dataset_dir,not args.allow_smoke),indent=2,allow_nan=False))
        return 0
    except (DatasetError,OSError,ValueError,KeyError) as error:
        print(f"INVALID DATASET: {error}")
        return 2


if __name__=="__main__":
    raise SystemExit(main())
