"""Collect B03 trajectories with the official policy/environment/tracker.

From repo root: python -m team_tools.collect_transitions --steps 288
--scenario building_train_1/fairbanks_1. Full default collects the locked plan.
"""
from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4
import zipfile

from team_tools.run_batch import (THREAD_LIMITS, atomic_write_json, current_worktree_fingerprint,
                                 git_value,scenario_input_pin,changed_source_paths)
from team_tools.benchmark import load_suite, scenario_key
from team_tools.dataset import (ARRAY_SCHEMA, FEATURE_CONTRACT, SCHEMA_VERSION, DatasetError,
                               ROOT_FILES, EPISODE_FILES, TransitionBuffer, digest, load_plan, validate_arrays, validate_corpus,
                               verify_reuse_source, portable_gin_config)

REPO=Path(__file__).resolve().parents[1]
REGISTRY=REPO/"experiments/datasets.csv"
REGISTRY_FIELDS=["dataset_id","utc_time","policy","source_sha","plan_sha256","steps_per_episode",
                 "episodes_requested","episodes_completed","transitions","zone_transition_samples",
                 "runtime_wall_s","cpu_core_hours","status","artifact_uri"]


def verify_source_pin(pin,repo=None):
    """Refuse changed producer code, configuration, assets or package versions."""
    repo=repo or REPO
    for name,checksum in pin["files"].items():
        path=repo/name
        if not path.is_file() or digest(path)!=checksum:
            raise DatasetError(f"producer/input changed during collection: {name}")
    if "python" in pin and pin["python"]!=sys.version:
        raise DatasetError("Python changed during collection")
    if "packages" in pin:
        packages=sorted({f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions()})
        if packages!=pin["packages"]:raise DatasetError("packages changed during collection")


def make_source_pin(plan_path,repo=None,episodes=None):
    repo=repo or REPO
    plan=load_plan(plan_path,repo)
    benchmark,_=load_suite(repo/plan["benchmark_manifest"],"dev_small",repo)
    paths={plan_path.resolve(),(repo/plan["benchmark_manifest"]).resolve()}
    paths.update((repo/"smart_buildings").rglob("*.py"))
    paths.update(repo/"team_tools"/name for name in ("collect_transitions.py","dataset.py","audit_data.py","benchmark.py","run_batch.py"))
    actual_inputs={}
    for pair in plan["episodes"] if episodes is None else episodes:
        suite=benchmark["suites"][pair["suite"]]
        directory=repo/suite.get("scenarios_dir","smart_buildings/training_scenarios")/pair["building"]/pair["weather"]
        paths.update(p for p in directory.iterdir() if p.is_file())
        actual_inputs.update(scenario_input_pin(repo/suite.get("scenarios_dir","smart_buildings/training_scenarios"),[pair],repo))
    files={str(p.relative_to(repo) if p.is_relative_to(repo) else p).replace("\\","/"):digest(p) for p in sorted(paths)}
    files.update(actual_inputs)
    return dict(files=files,python=sys.version,packages=sorted({f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions()}))


def finalize_interrupted_worker(directory,status,reason):
    """Finish a killed worker's receipt without pretending its RAM was persisted."""
    directory.mkdir(parents=True,exist_ok=True)
    path=directory/"episode.json"
    try:child=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (ValueError,OSError):child={}
    if child.get("status") not in (None,"RUNNING"):return
    progress=directory/"progress.json"
    try:last=json.loads(progress.read_text()).get("steps",0) if progress.exists() else 0
    except (ValueError,OSError):last=0
    checkpoint=0
    if (directory/"arrays.npz").exists():
        import numpy as np
        with np.load(directory/"arrays.npz",allow_pickle=False) as a:checkpoint=len(a["rewards"])
    child.update(status=status,failure=reason,last_reported_steps=last,steps_checkpointed=checkpoint,steps_completed=checkpoint)
    atomic_write_json(path,child)


class ObservationAudit:
    """Observe responses once, before upstream imputation, without modifying them."""
    def __init__(self, request, indices, dimension):
        import numpy as np
        self.request,self.indices,self.dimension=request,indices,dimension
        self.valid=np.ones(dimension,bool)
        self.native=np.full(dimension,np.nan,np.float64)
        self.sensor_indices=list(indices.values())
        self.calls=0

    def __call__(self, request):
        self.valid[:]=True
        self.valid[self.sensor_indices]=False
        self.native[:]=float("nan")
        response=self.request(request)
        for value in response.single_observation_responses:
            key=(value.single_observation_request.device_id,value.single_observation_request.measurement_name)
            index=self.indices.get(key)
            if index is not None:
                self.valid[index]=value.observation_valid
                if value.observation_valid:self.native[index]=value.continuous_value
        self.calls+=1
        return response


def build_metadata(env, official, pair, plan, steps):
    from team_tools.audit_data import field_semantics
    from smart_buildings.smart_control.environment.hybrid_action_environment import is_discrete_action
    fields=official["observation_field_names"]
    means,stds,units,source_keys=[],[],[],[]
    sensor_indices={}
    for index,field in enumerate(fields):
        key=env._id_map.inv.get(field)
        if key is not None:
            device,measurement=key
            constants=official["observation_normalization_metadata"].get(measurement,{"sample_mean":0.,"sample_std":1.})
            mean,std=constants["sample_mean"],constants["sample_std"]
            unit,_=field_semantics(device,measurement)
            sensor_indices[(device,measurement)]=index
            source_keys.append(dict(device=device,measurement=measurement))
        else:
            mean,std,unit=(125.,126.,"count") if field=="num_occupants" else (0.,1.,"dimensionless")
            source_keys.append(dict(device="environment",measurement=field))
        means.append(mean);stds.append(std);units.append(unit)
    continuous,discrete,low,high=[],[],[],[]
    for field in env.action_names:
        _,measurement=env._id_map.inv[field]
        if is_discrete_action(field):discrete.append(field)
        else:
            continuous.append(field)
            normalizer=env.action_normalizers[measurement]
            low.append(float(normalizer.min_native_value));high.append(float(normalizer.max_native_value))
    zone_indices=list(official["zone_temp_indices"])
    zone_ids=[env._id_map.inv[fields[index]][0] for index in zone_indices]
    zone_to_ahu={room.replace("room_","VAV_"):ahu for ahu,rooms in official["ahu_zone_assignments"].items() for room in rooms}
    if set(zone_ids)!=set(zone_to_ahu):raise DatasetError("incomplete static room/VAV/AHU map")
    meta=dict(schema_version=SCHEMA_VERSION,scenario=scenario_key(pair),building=pair["building"],weather=pair["weather"],
              suite=pair["suite"],split=pair["split"],policy=plan["policy"],policy_status="provisional",expected_steps=steps,
              horizon_steps=1,dt_seconds=plan["dt_seconds"],timestamp_convention="simulator-native ISO; naive timestamps are preserved; no assumed UTC conversion",
              schedule_time_zone=str(official["time_zone"]),observation_fields=fields,observation_mean=means,observation_std=stds,
              observation_native_units=units,observation_source_keys=source_keys,zone_indices=zone_indices,zone_ids=zone_ids,
              room_to_vav={room:room.replace("room_","VAV_") for rooms in official["ahu_zone_assignments"].values() for room in rooms},
              zone_to_ahu=zone_to_ahu,continuous_fields=continuous,discrete_fields=discrete,
              continuous_native_min=low,continuous_native_max=high,feature_contract=FEATURE_CONTRACT,
              native_values_note="reconstructed from normalized policy-visible observations; raw responses used only for unit assertions and validity masks")
    return meta,sensor_indices


def save_arrays(path, arrays):
    import numpy as np
    temporary=path.with_suffix(".tmp")
    with temporary.open("wb") as stream:np.savez_compressed(stream,**arrays)
    temporary.replace(path)


def stage_runtime_config(source, snapshots):
    """Keep original inputs, load a recorded path-only portable copy if needed."""
    converted,fields=portable_gin_config(source.read_text(encoding="utf-8"))
    if not fields:return source,None
    path=snapshots/"effective_config.gin"
    with path.open("x",encoding="utf-8",newline="\n") as stream:stream.write(converted)
    return path,dict(method="gin_path_separators_v1",path_fields=fields,
                     original_sha256=digest(source),effective_sha256=digest(path))


def collect_episode(plan_path, index, steps, output, pin_path=None):
    import numpy as np
    pin=json.loads(pin_path.read_text()) if pin_path else None
    if pin is not None:verify_source_pin(pin)
    from smart_buildings.evaluate import (POLICY_MAP, SimulationTracker, create_building_meta_data,
                                         get_policy_action, initialize_policy, load_hybrid_environment, validate_action)
    from team_tools.audit_data import verify_chronology
    plan=load_plan(plan_path,REPO);pair=plan["episodes"][index]
    benchmark,pairs=load_suite(REPO/plan["benchmark_manifest"],pair["suite"],REPO)
    source=REPO/benchmark["suites"][pair["suite"]].get("scenarios_dir","smart_buildings/training_scenarios")/pair["building"]/pair["weather"]
    output.mkdir(parents=True,exist_ok=False)
    (output/"inputs").mkdir()
    inputs={}
    for file in source.iterdir():
        if file.is_file():
            inputs[file.name]=digest(file)
            if file.suffix in (".gin",".yaml"): (output/"inputs"/file.name).write_bytes(file.read_bytes())
    runtime_path,runtime_config=stage_runtime_config(source/"config.gin",output/"inputs")
    if runtime_config:inputs["effective_config.gin"]=runtime_config["effective_sha256"]
    receipt=dict(status="RUNNING",scenario=scenario_key(pair),split=pair["split"],expected_steps=steps,
                 source_sha=git_value("rev-parse","HEAD"),input_hashes=inputs,steps_completed=0)
    if pin_path:receipt.update(producer_pin_sha256=digest(pin_path),producer_guard="PASS_BEFORE")
    if runtime_config:receipt["runtime_config"]=runtime_config
    atomic_write_json(output/"episode.json",receipt)
    wall,cpu=time.perf_counter(),time.process_time()
    env=None;buffer=None
    try:
        env=load_hybrid_environment(runtime_path)
        tracker=SimulationTracker(env,capture_snapshots=False)
        env.metrics_path=None;env._occupancy_normalization_constant=125.
        official=create_building_meta_data(env,source)
        policy=initialize_policy(POLICY_MAP[plan["policy"]],official,env.action_spec())
        meta,indices=build_metadata(env,official,pair,plan,steps)
        if env.time_step_sec!=plan["dt_seconds"]:raise DatasetError("source timestep differs from locked plan")
        atomic_write_json(output/"metadata.json",meta)
        audit=ObservationAudit(env.building.request_observations,indices,len(meta["observation_fields"]))
        env.building.request_observations=audit
        tracker.reset();obs=tracker.last_obs
        buffer=TransitionBuffer(meta,obs,env.current_simulation_timestamp.isoformat(),audit.valid)
        sensor=np.array(audit.sensor_indices,dtype=int)
        mean,std=np.asarray(meta["observation_mean"]),np.asarray(meta["observation_std"])

        def check_observation(value):
            if value.dtype!=np.float32 or value.shape!=(len(mean),) or not np.isfinite(value).all():
                raise DatasetError("invalid observation shape/dtype/finiteness")
            valid=sensor[audit.valid[sensor]]
            if not np.allclose(value[valid].astype(np.float64)*std[valid]+mean[valid],audit.native[valid],rtol=1e-5,atol=2e-4):
                raise DatasetError("raw-response/native normalization assertion failed")

        check_observation(obs)
        for step in range(steps):
            before=env.current_simulation_timestamp.isoformat()
            action=validate_action(get_policy_action(policy,obs.copy()),env.action_spec())
            next_obs,reward,terminated,truncated,_=tracker.step(action)
            timestamp=env.current_simulation_timestamp.isoformat()
            verify_chronology(before,timestamp,plan["dt_seconds"])
            check_observation(next_obs)
            if not np.isfinite(reward):raise DatasetError("non-finite reward")
            buffer.append(action,next_obs,timestamp,float(reward),terminated,truncated,audit.valid)
            obs=next_obs;receipt["steps_completed"]=step+1
            if (step+1)%288==0:
                atomic_write_json(output/"progress.json",dict(steps=step+1,expected=steps,wall_s=time.perf_counter()-wall,cpu_s=time.process_time()-cpu))
            if (step+1)%1440==0:save_arrays(output/"arrays.npz",buffer.arrays())
            if terminated or truncated:break
        arrays=buffer.arrays();save_arrays(output/"arrays.npz",arrays)
        if audit.calls!=len(buffer.obs):raise DatasetError("extra/missing observation query; chronology cannot be trusted")
        quality=validate_arrays(arrays,meta,require_full=steps==8640)
        if pin is not None:
            verify_source_pin(pin)
            receipt["producer_guard"]="PASS_BEFORE_AND_AFTER"
        quality["raw_observation_queries"]=audit.calls
        atomic_write_json(output/"quality.json",quality)
        receipt["status"]="SUCCEEDED_FULL" if steps==8640 else "SUCCEEDED_SMOKE"
    except Exception as error:
        receipt["status"]="FAILED_VALIDATION";receipt["failure"]=f"{type(error).__name__}: {error}"
        if buffer is not None and buffer.cont:save_arrays(output/"arrays.npz",buffer.arrays())
    finally:
        if env is not None:env.close()
        receipt["runtime_wall_s"]=time.perf_counter()-wall;receipt["process_cpu_s"]=time.process_time()-cpu
        atomic_write_json(output/"episode.json",receipt)
    print(json.dumps(receipt,indent=2))
    return 0 if receipt["status"].startswith("SUCCEEDED") else 1


def append_registry(row):
    REGISTRY.parent.mkdir(parents=True,exist_ok=True)
    exists=REGISTRY.exists() and REGISTRY.stat().st_size>0
    with REGISTRY.open("a",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=REGISTRY_FIELDS)
        if not exists:writer.writeheader()
        writer.writerow({key:row.get(key,"") for key in REGISTRY_FIELDS})


def import_reusable_episodes(source,dest,plan_path,source_sha,audit_path=None,environment=None,current_numeric_pin=None):
    """Copy complete verified episodes and retain their original producer evidence."""
    from copy import deepcopy
    if current_numeric_pin is None:raise DatasetError('new reuse requires a current numerical source pin')
    selected=verify_reuse_source(source,plan_path,source_sha,audit_path,environment,current_numeric_pin)
    prior=json.loads((source/"dataset.json").read_text())
    origin="origin-"+digest(source/"dataset.json")[:16]
    capsule=dest/"lineage"/origin
    capsule.mkdir(parents=True,exist_ok=False)
    names=set(prior["root_files"])|{"dataset.json"}
    for name in names:shutil.copy2(source/name,capsule/name)
    if (source/"lineage").exists():shutil.copytree(source/"lineage",capsule/"lineage")
    if audit_path:
        shutil.copy2(audit_path,capsule/"producer_audit.json");names.add("producer_audit.json")
    items={}
    for key,original in selected.items():
        shutil.copytree(source/"episodes"/original["directory"],dest/"episodes"/original["directory"])
        item=deepcopy(original);item["reuse_origin"]=origin
        item["process_cpu_s"]=json.loads((dest/"episodes"/item["directory"]/"episode.json").read_text()).get("process_cpu_s")
        items[key]=item
    entry=dict(directory=f"lineage/{origin}",source_dataset_id=prior.get("dataset_id"),
               source_status=prior["status"],files={name:digest(capsule/name) for name in sorted(names)})
    return items,{origin:entry}


def run_collection(args):
    plan_path=args.manifest.resolve();plan=load_plan(plan_path,REPO)
    if args.steps not in (288,8640) or args.timeout_seconds<=0 or args.max_wall_seconds<=0:
        raise DatasetError("invalid steps or compute budget")
    if args.reuse_from and args.steps!=8640:raise DatasetError("only complete 8640-step episodes can be reused in a full corpus")
    if args.reuse_audit and not args.reuse_from:raise DatasetError("reuse audit requires a source dataset")
    selected=[(i,e) for i,e in enumerate(plan["episodes"]) if not args.scenario or scenario_key(e)==args.scenario]
    if not selected:raise DatasetError("scenario is not declared in the locked dataset plan")
    if args.steps==8640 and args.scenario:raise DatasetError("full corpus requires all locked episodes; use smoke for a single-scenario check")
    dataset_id=args.dataset_id or f"b03-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:6]}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}",dataset_id):raise DatasetError("unsafe dataset ID")
    root=args.output_root.resolve()/dataset_id
    if root.exists():raise DatasetError("dataset ID already exists; refusing to overwrite")
    source_sha=git_value("rev-parse","HEAD")
    environment=dict(python=sys.version,platform=platform.platform(),packages=sorted({f"{d.metadata['Name']}=={d.version}" for d in importlib.metadata.distributions()}),
                     thread_limits=THREAD_LIMITS,PYTHONHASHSEED="0",uv_lock_sha256=digest(REPO/"uv.lock"))
    # Validate selected inputs before creating any output; a one-scenario smoke
    # must not depend on unselected generated data absent from a fresh clone.
    pin=make_source_pin(plan_path,episodes=[e for _,e in selected])
    if args.reuse_from:verify_reuse_source(args.reuse_from,plan_path,source_sha,args.reuse_audit,environment,pin)
    root.mkdir(parents=True)
    (root/"episodes").mkdir();(root/"dataset_manifest.yaml").write_bytes(plan_path.read_bytes())
    (root/"benchmark_manifest.yaml").write_bytes((REPO/plan["benchmark_manifest"]).read_bytes())
    atomic_write_json(root/"schema.json",dict(version=SCHEMA_VERSION,arrays=ARRAY_SCHEMA,feature_contract=FEATURE_CONTRACT))
    (root/"tracked_changes.patch").write_bytes(subprocess.check_output(["git","diff","--binary","HEAD"],cwd=REPO))
    with zipfile.ZipFile(root/"changed_files.zip","w",zipfile.ZIP_DEFLATED) as archive:
        for relative in changed_source_paths():
            path=REPO/relative
            if path.is_file():archive.write(path,relative)
    dirty,fingerprint=current_worktree_fingerprint()
    atomic_write_json(root/"source_pin.json",pin)
    started=datetime.now(timezone.utc).isoformat();wall=time.perf_counter()
    receipt=dict(dataset_id=dataset_id,started_at_utc=started,policy=plan["policy"],policy_status="provisional",status="RUNNING",
                 source_sha=git_value("rev-parse","HEAD"),branch=git_value("branch","--show-current"),working_tree_dirty=dirty,
                 working_tree_sha256=fingerprint,plan_sha256=digest(plan_path),benchmark_manifest_sha256=digest(REPO/plan["benchmark_manifest"]),
                 steps_per_episode=args.steps,workers=1,training_ready=False,selected_scenarios=[scenario_key(e) for _,e in selected],episodes=[],
                 timeout_seconds=args.timeout_seconds,max_wall_seconds=args.max_wall_seconds,
                 producer_guard="scoped_sha256_v1",
                 cpu_measurement_scope="worker collection phase via time.process_time; excludes worker imports/startup and parent validation; killed worker CPU unavailable",
                 root_files={name:digest(root/name) for name in sorted(ROOT_FILES|{"source_pin.json"})},
                 environment=environment)
    atomic_write_json(root/"dataset.json",receipt)
    try:
        reused={}
        if args.reuse_from:
            reused,receipt["lineage"]=import_reusable_episodes(args.reuse_from,root,plan_path,source_sha,args.reuse_audit,environment,pin)
        for index,pair in selected:
            verify_source_pin(pin)
            if scenario_key(pair) in reused:
                receipt["episodes"].append(reused[scenario_key(pair)])
                atomic_write_json(root/"dataset.json",receipt)
                continue
            remaining=args.max_wall_seconds-(time.perf_counter()-wall)
            if remaining<=0:receipt["status"]="BUDGET_EXCEEDED";break
            name=f"{pair['building']}__{pair['weather']}"
            item=dict(scenario=scenario_key(pair),directory=name,status="RUNNING",files={})
            receipt["episodes"].append(item);atomic_write_json(root/"dataset.json",receipt)
            command=[sys.executable,"-m","team_tools.collect_transitions","--worker",str(root/"episodes"/name),
                     "--manifest",str(root/"dataset_manifest.yaml"),"--episode-index",str(index),"--steps",str(args.steps),"--source-pin",str(root/"source_pin.json")]
            env=os.environ.copy();env.update(THREAD_LIMITS);env.update(PYTHONUTF8="1",PYTHONIOENCODING="utf-8",PYTHONHASHSEED="0")
            try:
                result=subprocess.run(command,cwd=REPO,env=env,capture_output=True,text=True,encoding="utf-8",errors="replace",
                                      timeout=min(args.timeout_seconds,remaining),check=False)
                (root/f"{name}.stdout.log").write_text(result.stdout,encoding="utf-8")
                (root/f"{name}.stderr.log").write_text(result.stderr,encoding="utf-8")
                if (root/"episodes"/name/"episode.json").is_file():
                    child=json.loads((root/"episodes"/name/"episode.json").read_text())
                    item.update(status=child["status"],process_cpu_s=child["process_cpu_s"])
                if result.returncode!=0 or not item["status"].startswith("SUCCEEDED"):
                    finalize_interrupted_worker(root/"episodes"/name,"FAILED","worker exited without successful receipt")
                    item["status"]="FAILED";receipt["status"]="FAILED";break
                verify_source_pin(pin)
                item["files"]={filename:digest(root/"episodes"/name/filename) for filename in sorted(EPISODE_FILES)}
            except subprocess.TimeoutExpired as error:
                for kind,value in (("stdout",error.stdout),("stderr",error.stderr)):
                    text=value.decode("utf-8",errors="replace") if isinstance(value,bytes) else value or ""
                    (root/f"{name}.{kind}.log").write_text(text,encoding="utf-8")
                item["status"]="TIMED_OUT";receipt["status"]="TIMED_OUT";break
            atomic_write_json(root/"dataset.json",receipt)
        else:receipt["status"]="SUCCEEDED_FULL" if args.steps==8640 else "SUCCEEDED_SMOKE"
        atomic_write_json(root/"dataset.json",receipt)
        if receipt["status"].startswith("SUCCEEDED"):
            quality=validate_corpus(root,require_full=args.steps==8640)
            atomic_write_json(root/"validation.json",quality)
            receipt["training_ready"]=args.steps==8640
            receipt["transitions"]=quality["total_transitions"];receipt["zone_transition_samples"]=quality["total_zone_transition_samples"]
    except Exception as error:
        receipt["status"]="FAILED";receipt["failure"]=f"{type(error).__name__}: {error}"
    finally:
        if receipt["status"]=="RUNNING":receipt["status"]="FAILED_INTERNAL"
        for item in receipt["episodes"]:
            if item["status"]=="RUNNING":item["status"]="FAILED"
            if item["status"] in ("FAILED","TIMED_OUT"):
                finalize_interrupted_worker(root/"episodes"/item["directory"],item["status"],receipt.get("failure",item["status"]))
        receipt["finished_at_utc"]=datetime.now(timezone.utc).isoformat();receipt["runtime_wall_s"]=time.perf_counter()-wall
        values=[e.get("process_cpu_s") for e in receipt["episodes"] if not e.get("reuse_origin")]
        reused_values=[e.get("process_cpu_s") for e in receipt["episodes"] if e.get("reuse_origin")]
        receipt["cpu_core_hours"]=sum(values)/3600 if all(isinstance(v,(int,float)) for v in values) else None
        receipt["reused_production_cpu_core_hours"]=sum(reused_values)/3600 if all(isinstance(v,(int,float)) for v in reused_values) else None
        receipt["cpu_measurement_scope"]+="; cpu_core_hours counts only newly collected episodes, reused production CPU is separate"
        atomic_write_json(root/"dataset.json",receipt)
        append_registry(dict(dataset_id=dataset_id,utc_time=started,policy=plan["policy"],source_sha=receipt["source_sha"],plan_sha256=receipt["plan_sha256"],
                             steps_per_episode=args.steps,episodes_requested=len(selected),episodes_completed=sum(e["status"].startswith("SUCCEEDED") for e in receipt["episodes"]),
                             transitions=receipt.get("transitions",""),zone_transition_samples=receipt.get("zone_transition_samples",""),runtime_wall_s=receipt["runtime_wall_s"],
                             cpu_core_hours=receipt["cpu_core_hours"] if receipt["cpu_core_hours"] is not None else "",status=receipt["status"],artifact_uri=str(root)))
    print(json.dumps(dict(dataset_id=dataset_id,status=receipt["status"],training_ready=receipt["training_ready"],artifact_uri=str(root)),indent=2))
    return 0 if receipt["status"].startswith("SUCCEEDED") else 1


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,default=REPO/"configs/dataset_manifest.yaml")
    p.add_argument("--output-root",type=Path,default=REPO/"data/generated/trajectories")
    p.add_argument("--dataset-id")
    p.add_argument("--steps",type=int,choices=(288,8640),default=8640)
    p.add_argument("--scenario")
    p.add_argument("--reuse-from",type=Path,help="reuse verified complete episodes from a terminal dataset; never resume partial simulator state")
    p.add_argument("--reuse-audit",type=Path,help="recorded manual producer audit required for legacy datasets without a worker source pin")
    p.add_argument("--timeout-seconds",type=int,default=1800)
    p.add_argument("--max-wall-seconds",type=int,default=7200)
    p.add_argument("--worker",type=Path,help=argparse.SUPPRESS)
    p.add_argument("--episode-index",type=int,default=0,help=argparse.SUPPRESS)
    p.add_argument("--source-pin",type=Path,help=argparse.SUPPRESS)
    return p


def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.worker:return collect_episode(args.manifest,args.episode_index,args.steps,args.worker,args.source_pin)
        return run_collection(args)
    except (DatasetError,ValueError,OSError) as error:
        print(f"COLLECTION FAILED: {error}",file=sys.stderr);return 2


if __name__=="__main__":raise SystemExit(main())
