import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from team_tools.build_kaggle_trial import build, adapter_source


def test_bundle_self_contained_and_no_network_or_local_data(tmp_path):
    result=build(tmp_path/'bundle')
    assert len(result['notebooks'])==2
    for name in result['notebooks']:
        n=json.loads((tmp_path/'bundle'/name).read_text(encoding='utf-8'))
        assert n['metadata']['kaggle']['isInternetEnabled'] is False
        code='\n'.join(''.join(c['source']) for c in n['cells'] if c['cell_type']=='code')
        compile(code,name,'exec')
        assert 'SmartBuildingsInferenceServer(TransferPolicy).run(' in code
        assert 'from team.' not in code and 'from smart_buildings.baselines' not in code
        assert 'pip install' not in code and 'read_csv' not in code
        assert all(c.get('outputs',[])==[] for c in n['cells'])
    with pytest.raises(FileExistsError):build(tmp_path/'bundle')


def test_adapter_preserves_action_and_rejects_invalid_output():
    class Base:
        def __init__(self,*a):pass
    class Engine:
        def __init__(self,*a):self.action={'continuous_action':np.array([.2],np.float32),'discrete_action':np.array([1],np.int32)}
        def get_action(self,obs):return self.action
    namespace=dict(np=np,smart_buildings_inference_server=SimpleNamespace(Policy=Base),PIDWaterResetPolicy=Engine)
    exec(adapter_source('safe'),namespace)
    spec={k:SimpleNamespace(shape=(1,),low=np.array([-1 if k=='continuous_action' else 0]),high=np.array([1])) for k in ('continuous_action','discrete_action')}
    policy=namespace['TransferPolicy']({},spec)
    result=policy.get_action(np.zeros(1))
    np.testing.assert_array_equal(result['continuous_action'],policy.engine.action['continuous_action'])
    result['continuous_action'][0]=0
    assert policy.engine.action['continuous_action'][0]==np.float32(.2)
    policy.engine.action['continuous_action'][0]=np.nan
    with pytest.raises(ValueError):policy.get_action(np.zeros(1))


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):adapter_source('unapproved')


@pytest.mark.parametrize('key,value',[('continuous_action',np.array([2.])),('continuous_action',np.zeros(2)),('discrete_action',np.array([.5]))])
def test_adapter_rejects_shape_bounds_and_nonbinary(key,value):
    class Base:
        def __init__(self,*a):pass
    class Engine:
        def __init__(self,*a):pass
        def get_action(self,obs):return {'continuous_action':np.array([0.]),'discrete_action':np.array([1.]),key:value}
    scope=dict(np=np,smart_buildings_inference_server=SimpleNamespace(Policy=Base),PIDWaterResetPolicy=Engine)
    exec(adapter_source('safe'),scope)
    spec={k:SimpleNamespace(shape=(1,),low=0 if k=='discrete_action' else -1,high=1) for k in ('continuous_action','discrete_action')}
    with pytest.raises(ValueError):scope['TransferPolicy']({},spec).get_action(np.zeros(1))


def test_checkpoint_ref_requires_full_commit_before_creating_output(tmp_path):
    with pytest.raises(ValueError,match='full commit'):
        build(tmp_path/'bundle',policy_ref='feature/a-zone')
    assert not (tmp_path/'bundle').exists()


def test_explicit_ref_embeds_committed_source_not_dirty_worktree(tmp_path,monkeypatch):
    import subprocess
    import team_tools.build_kaggle_trial as builder
    def git(*args):return subprocess.check_output(['git',*args],cwd=tmp_path)
    git('init','-q')
    names=['smart_buildings/baselines/pid.py','smart_buildings/baselines/pid_plus.py',
        'team/policy/zone_controller.py','team/policy/member_a_policy.py']
    for name in names:
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True)
        imports= 'from smart_buildings.baselines.pid import PIDPolicy\n' if 'pid_plus' in name else ''
        if 'member_a_policy' in name:imports='from smart_buildings.baselines.pid_plus  import PIDWaterResetPolicy\nfrom team.policy.zone_controller import ZoneController\n'
        path.write_text(imports+'VERSION = "committed"\n')
    git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','synthetic source')
    sha=git('rev-parse','HEAD').decode().strip()
    (tmp_path/names[-1]).write_text('VERSION = "dirty"\n')
    monkeypatch.setattr(builder,'ROOT',tmp_path)
    sources,records=builder.policy_sources('candidate_a',policy_ref=sha)
    assert 'committed' in sources[-1] and 'dirty' not in sources[-1]
    assert records[-1]['source_commit']==sha
    assert records[0]['source_commit']==sha
