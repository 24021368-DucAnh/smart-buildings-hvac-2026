"""Copy declared generated-dev configs to a unique portable evaluation workspace.

Preserve source assets/configs. Normalize only the B03 whitelisted path macros
and redirect metrics into the new workspace. No simulator/physics changes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from team_tools.dataset import portable_gin_config
from team_tools.benchmark import load_suite, scenario_key


def prepare_pair(source,destination):
    destination=destination.resolve()
    destination.mkdir(parents=True,exist_ok=False)
    original=(source/'config.gin').read_text(encoding='utf-8')
    effective,fields=portable_gin_config(original)
    pattern=r'(?m)^(\s*metrics_path\s*=\s*)([\x22\x27])(.*)\2([ \t]*(?:#.*)?)$'
    effective,count=re.subn(pattern,lambda m:m[1]+json.dumps((destination/'metrics').as_posix())+m[4],effective)
    if count!=1:raise ValueError('expected exactly one metrics_path macro')
    for field,filename in [('floor_plan_filepath','floor_plan.npy'),('zone_map_filepath','zone_map.npy')]:
        pattern=rf'(?m)^(\s*{field}\s*=\s*)([\x22\x27])(.*)\2([ \t]*(?:#.*)?)$'
        if re.search(pattern,effective):
            if not (source/filename).is_file():raise ValueError('missing scenario asset: '+filename)
            effective=re.sub(pattern,lambda m:m[1]+json.dumps((destination/filename).as_posix())+m[4],effective)
    for p in source.iterdir():
        if p.is_file() and p.name!='config.gin':shutil.copy2(p,destination/p.name)
    (destination/'config.gin').write_text(effective,encoding='utf-8')
    sha=lambda b:hashlib.sha256(b).hexdigest()
    record=dict(source=str(source.resolve()),effective=str(destination),
        source_config_sha256=sha((source/'config.gin').read_bytes()),
        effective_config_sha256=sha((destination/'config.gin').read_bytes()),
        normalized_path_fields=fields,metrics_redirected=True)
    (destination/'portable_receipt.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--scenario',help='Optional declared generated-dev BUILDING/WEATHER')
    a=p.parse_args();root=Path(__file__).resolve().parents[1]
    manifest=root/'configs/benchmark_manifest.yaml'
    m,pairs=load_suite(manifest,'generated_dev',root)
    if a.scenario:
        pairs=[pair for pair in pairs if scenario_key(pair)==a.scenario]
        if not pairs:raise ValueError('scenario is not declared generated-dev')
    a.output.mkdir(parents=True,exist_ok=False)
    records=[prepare_pair(root/m['suites']['generated_dev']['scenarios_dir']/scenario_key(pair),
                          a.output/scenario_key(pair)) for pair in pairs]
    (a.output/'preparation.json').write_text(json.dumps(dict(suite='generated_dev',scenarios=records,
        manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest()),indent=2),encoding='utf-8')
    print(json.dumps(dict(output=str(a.output),scenarios=len(records))))

if __name__=='__main__':main()
