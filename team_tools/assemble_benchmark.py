"""Assemble complete official suites from independently verified B02 runs.

Original receipts remain immutable. Legacy summary hashes are explicitly observed
at assembly time; they are not relabelled as producer-time integrity evidence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile
import subprocess
from team_tools.benchmark import BenchmarkError, _read_summary, load_suite, scenario_key, score_results, validate_scenarios
from team_tools.score_generated import validate_run_receipt

PROTECTED=('smart_buildings/','team/policy/','team/evaluate_a.py','score_leaderboard.py')


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def assemble(run_dirs, expected, policies, manifest_sha, source_sha, suite='dev_small',canonical_configs=None):
    if suite not in ('dev_small','dev_full'):raise BenchmarkError('assembly supports official development suites only')
    expected=validate_scenarios(expected);keys={scenario_key(p) for p in expected}
    if canonical_configs is None or set(canonical_configs)!=keys:raise BenchmarkError('canonical source configuration hashes required')
    if not policies or len(policies)!=len(set(policies)) or any(not re.fullmatch(r'[A-Za-z0-9_-]+',p) for p in policies):
        raise BenchmarkError('invalid/duplicate policies')
    target={(key,p) for key in keys for p in policies};found={};configs={};environment=None
    for directory in run_dirs:
        directory=Path(directory).resolve();receipt=_read_summary(directory/'run.json')
        policy=receipt.get('policy')
        if policy not in policies:raise BenchmarkError('extra policy')
        raw=receipt.get('run_config',{}).get('scenarios',[])
        if not raw or any(not isinstance(k,str) or k.count('/')!=1 for k in raw):raise BenchmarkError('malformed run scenario selection')
        pairs=validate_scenarios([dict(zip(('building','weather'),k.split('/'))) for k in raw])
        if set(raw)-keys:raise BenchmarkError('extra scenario')
        validate_run_receipt(directory/'results',suite,policy,pairs,manifest_sha)
        if receipt.get('commit_sha')!=source_sha:raise BenchmarkError('mismatched numerical source SHA')
        if receipt.get('experiment_id')!=directory.name:raise BenchmarkError('receipt identity mismatch')
        env=receipt.get('runtime_environment',{})
        selected_env={k:env.get(k) for k in ('python','packages','uv_lock_sha256','thread_limits')}
        if any(v is None for v in selected_env.values()):raise BenchmarkError('missing runtime environment')
        if environment is None:environment=selected_env
        if selected_env!=environment:raise BenchmarkError('mismatched runtime environment')
        # A dirty checkout may contain B tools/docs, but cannot silently redefine
        # the claimed official/A numerical source revision.
        try:
            with zipfile.ZipFile(directory/'changed_files.zip') as archive:
                if any(name.replace('\\','/').startswith(PROTECTED) for name in archive.namelist()):
                    raise BenchmarkError('modified protected numerical source in archive')
            patch=(directory/'tracked_changes.patch').read_text(encoding='utf-8')
        except (OSError,zipfile.BadZipFile) as e:raise BenchmarkError('missing/invalid source snapshots') from e
        if re.search(r'^diff --git [\x22]?a/(?:smart_buildings/|team/policy/|team/evaluate_a.py|score_leaderboard.py)',patch,re.M):
            raise BenchmarkError('modified protected numerical source in patch')
        entries=receipt.get('scenario_configs')
        if entries!=receipt['run_config'].get('scenario_config_hashes'):raise BenchmarkError('mismatched config snapshot lists')
        if not isinstance(entries,list) or len(entries)!=len(pairs):raise BenchmarkError('missing config entries')
        if len({x.get('scenario') for x in entries})!=len(entries) or {x.get('scenario') for x in entries}!=set(raw):
            raise BenchmarkError('duplicate/missing configuration scenario entries')
        for item in entries:
            key=item.get('scenario');hashes=item.get('hashes',{})
            if key not in raw or set(hashes)!= {'config.gin','config.yaml','floor_plan.npy','zone_map.npy'}:
                raise BenchmarkError('missing/wrong scenario configuration files')
            if any(not re.fullmatch('[0-9a-f]{64}',str(v)) for v in hashes.values()):raise BenchmarkError('invalid asset hash')
            if hashes!=canonical_configs[key]:raise BenchmarkError('configuration does not match canonical source assets')
            if configs.setdefault(key,hashes)!=hashes:raise BenchmarkError('different configurations for paired policies')
        result=score_results(directory/'results',pairs,policy)
        for row in result['scenario_scores']:
            key=row['scenario'];identity=(key,policy)
            if identity in found:raise BenchmarkError('duplicate completed scenario/policy')
            path=directory/'results'/key/policy/'summary.json';observed=digest(path)
            item=next(x for x in receipt['scenario_runs'] if x['scenario']==key)
            binding=item.get('summary_sha256')
            if binding is not None and binding!=observed:raise BenchmarkError('producer summary hash mismatch')
            found[identity]=dict(**row,policy=policy,experiment_id=directory.name,
                summary_sha256=observed,receipt_sha256=digest(directory/'run.json'),
                summary_binding='producer_bound' if binding else 'observed_at_assembly_legacy')
    if set(found)!=target:raise BenchmarkError(f'missing full cases: {sorted(target-set(found))}')
    scores={}
    for policy in policies:
        rows=[found[(key,policy)] for key in sorted(keys)]
        scores[policy]=dict(mean_loss=sum(r['loss'] for r in rows)/len(rows),
            worst_case_loss=max(r['loss'] for r in rows),scenario_count=len(rows),scenario_scores=rows)
    return dict(status='VERIFIED_FULL_SUITE_ASSEMBLY',suite=suite,source_sha=source_sha,manifest_sha256=manifest_sha,
                step_count=8640,policies=scores,rows=list(found.values()),
                provenance_note='Legacy hashes observed at assembly, not retroactive producer binding. No historical receipt was rewritten.')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index',type=Path,required=True)
    p.add_argument('--manifest',type=Path,default=Path('configs/benchmark_manifest.yaml'))
    p.add_argument('--suite',choices=('dev_small','dev_full'),default='dev_small')
    p.add_argument('--policies',nargs='+',required=True);p.add_argument('--source-sha',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args(argv)
    try:
        _,pairs=load_suite(a.manifest.resolve(),a.suite,Path(__file__).resolve().parents[1])
        repo=Path(__file__).resolve().parents[1]
        subprocess.check_call(['git','diff','--exit-code',a.source_sha,'--','smart_buildings','team/policy','team/evaluate_a.py','score_leaderboard.py'],cwd=repo)
        canonical={scenario_key(pair):{n:digest(repo/'smart_buildings/training_scenarios'/scenario_key(pair)/n)
            for n in ('config.gin','config.yaml','floor_plan.npy','zone_map.npy')} for pair in pairs}
        index=_read_summary(a.index);result=assemble(index['run_dirs'],pairs,a.policies,digest(a.manifest),a.source_sha,a.suite,canonical)
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
        print(json.dumps(result['policies'],indent=2));return 0
    except (BenchmarkError,OSError,KeyError,ValueError,subprocess.CalledProcessError) as e:
        print(f'INVALID ASSEMBLY: {e}',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
