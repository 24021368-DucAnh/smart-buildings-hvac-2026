import hashlib
import json
import zipfile
import pytest
from team_tools.benchmark import BenchmarkError, config_fingerprint
from team_tools.assemble_benchmark import assemble

CANONICAL={'b/w':{n:'b'*64 for n in ('config.gin','config.yaml','floor_plan.npy','zone_map.npy')}}


def fixture_run(tmp_path, name, policy, pair, reward=-8640.):
    root=tmp_path/name; results=root/'results';s=results/pair/policy/'summary.json';s.parent.mkdir(parents=True)
    s.write_text(json.dumps(dict(policy=policy,total_steps=8640,total_reward=reward)))
    files={n:'b'*64 for n in ('config.gin','config.yaml','floor_plan.npy','zone_map.npy')}
    snap=dict(suite='dev_small',policy=policy,steps=8640,manifest_sha256='c'*64,
              scenarios=[pair],scenario_config_hashes=[dict(scenario=pair,hashes=files)])
    receipt=dict(experiment_id=name,status='SUCCEEDED_FULL',suite='dev_small',policy=policy,step_count=8640,
        scenario_count_expected=1,commit_sha='a'*40,manifest_sha256='c'*64,run_config=snap,config_hash=config_fingerprint(snap),
        scenario_configs=snap['scenario_config_hashes'],scenario_runs=[dict(scenario=pair,status='SUCCEEDED')],
        runtime_environment=dict(python='3.12',packages=['numpy==2'],uv_lock_sha256='d'*64,thread_limits={'OMP_NUM_THREADS':'1'}))
    (root/'run.json').write_text(json.dumps(receipt));(root/'tracked_changes.patch').write_text('')
    with zipfile.ZipFile(root/'changed_files.zip','w'):pass
    return root


def test_exact_assembly_and_report_time_hashes(tmp_path):
    dirs=[fixture_run(tmp_path,'one','pid','b/w'),fixture_run(tmp_path,'two','member_a','b/w',-4320.)]
    r=assemble(dirs,[dict(building='b',weather='w')],['pid','member_a'],'c'*64,'a'*40,canonical_configs=CANONICAL)
    assert r['policies']['pid']['mean_loss']==1
    assert r['policies']['member_a']['mean_loss']==.5
    assert r['rows'][0]['summary_binding']=='observed_at_assembly_legacy'


@pytest.mark.parametrize('problem',['missing','duplicate','extra','source','config','nan','partial','protected','summary_hash'])
def test_rejects_invalid_assembly(tmp_path,problem):
    a=fixture_run(tmp_path,'one','pid','b/w');dirs=[a]
    if problem=='missing':dirs=[]
    elif problem=='duplicate':dirs=[a,a]
    elif problem=='extra':dirs.append(fixture_run(tmp_path,'extra','pid','other/w'))
    elif problem=='protected':
        with zipfile.ZipFile(a/'changed_files.zip','a') as z:z.writestr('smart_buildings/baselines/pid.py','changed')
    elif problem in ('source','config','partial','summary_hash'):
        r=json.loads((a/'run.json').read_text())
        if problem=='source':r['commit_sha']='f'*40
        if problem=='config':r['config_hash']='0'*64
        if problem=='partial':r['status']='TIMED_OUT'
        if problem=='summary_hash':r['scenario_runs'][0]['summary_sha256']='0'*64
        (a/'run.json').write_text(json.dumps(r))
    else:
        s=a/'results/b/w/pid/summary.json';r=json.loads(s.read_text());r['total_reward']=float('nan');s.write_text(json.dumps(r))
    with pytest.raises(BenchmarkError):assemble(dirs,[dict(building='b',weather='w')],['pid'],'c'*64,'a'*40,canonical_configs=CANONICAL)


def test_rejects_consistently_noncanonical_asset_hashes(tmp_path):
    a=fixture_run(tmp_path,'one','pid','b/w')
    canonical={'b/w':{n:'f'*64 for n in CANONICAL['b/w']}}
    with pytest.raises(BenchmarkError,match='canonical'):
        assemble([a],[dict(building='b',weather='w')],['pid'],'c'*64,'a'*40,canonical_configs=canonical)


def test_new_receipt_cannot_downgrade_to_legacy_missing_binding(tmp_path):
    a=fixture_run(tmp_path,'one','pid','b/w');p=a/'run.json';r=json.loads(p.read_text())
    r['source_guard']='before_after_sha256_v1';p.write_text(json.dumps(r))
    with pytest.raises(BenchmarkError,match='checksum'):
        assemble([a],[dict(building='b',weather='w')],['pid'],'c'*64,'a'*40,canonical_configs=CANONICAL)
    s=a/'results/b/w/pid/summary.json';r['scenario_runs'][0]['summary_sha256']=hashlib.sha256(s.read_bytes()).hexdigest();p.write_text(json.dumps(r))
    with pytest.raises(BenchmarkError,match='numerical source'):
        assemble([a],[dict(building='b',weather='w')],['pid'],'c'*64,'a'*40,canonical_configs=CANONICAL)
    r['numeric_sources_sha256']={'smart_buildings/physics.py':'b'*64};r['evaluator_bootstrap']='recorded bootstrap';p.write_text(json.dumps(r))
    result=assemble([a],[dict(building='b',weather='w')],['pid'],'c'*64,'a'*40,canonical_configs=CANONICAL)
    assert result['rows'][0]['summary_binding']=='producer_bound'
