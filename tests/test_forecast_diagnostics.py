import numpy as np
import pytest
import hashlib
from team_tools.forecast import FEATURES
from team_tools.forecast_diagnostics import error_stats, action_coverage, lag_association, readback_alignment
from team_tools.forecast_diagnostics import load_bound_model, verify_reference_metrics
from team_tools.forecast_diagnostics import analyze_episode, compact_findings
from team_tools.forecast_diagnostics import run


def test_error_decomposition_hand_calculated():
    r=error_stats(np.array([0.,2.,-6.]),np.array([1.,1.,-4.]))
    assert r['n']==3 and r['mae_K']==pytest.approx(4/3)
    assert r['rmse_K']==pytest.approx(np.sqrt(2))
    assert r['bias_K']==pytest.approx(2/3)
    assert r['tail_gt_1K']['n']==2
    assert r['tail_gt_1K']['absolute_error_share']==pytest.approx(3/4)
    assert r['tail_gt_5K']['squared_error_share']==pytest.approx(4/6)


@pytest.mark.parametrize('y,p',[(np.array([]),np.array([])),(np.array([np.nan]),np.array([0.])),(np.array([1.]),np.array([0.,0.]))])
def test_error_stats_reject_invalid(y,p):
    with pytest.raises(ValueError):error_stats(y,p)


def test_coverage_exact_edges_switches_and_no_transition_case():
    r=action_coverage(np.array([-1.,-1.,0.,1.]))
    assert r['bin_counts']==[2,0,1,1]
    assert r['switch_fraction']==pytest.approx(2/3)
    assert r['longest_constant_steps']==2
    assert r['fraction_at_low']==.5 and r['fraction_at_high']==.25
    assert action_coverage(np.array([0.]))['switch_fraction'] is None
    with pytest.raises(ValueError):action_coverage(np.array([1.1]))


def test_lag_direction_no_wraparound_and_constant_handling():
    x=np.array([0.,1.,0.,2.,-1.,3.])
    y=np.r_[100.,x[:-1]]
    r=lag_association(x,y,1)
    assert r['n']==5 and r['pearson']==pytest.approx(1.)
    assert lag_association(np.ones(6),y,1)['pearson'] is None
    assert lag_association(x,y,7)['n']==0
    with pytest.raises(ValueError):lag_association(x,y,-1)


def test_readback_uses_post_action_observation_and_native_units():
    command=np.array([0.,.5,1.])
    readback=np.array([.123,0.,.5,1.])
    assert readback_alignment(command,readback,0)['mae_native']==0
    assert readback_alignment(command,readback,1)['mae_native']==.5
    with pytest.raises(ValueError):readback_alignment(command,readback[:-1],0)


def test_source_default_damper_floor_is_explicit_not_fitted():
    command=np.array([0.,.05,.5,1.])
    readback=np.r_[.1,np.maximum(command,.1)]
    assert readback_alignment(command,readback,0)['mae_native']>0
    assert readback_alignment(command,readback,0,floor=.1)['mae_native']==0
    with pytest.raises(ValueError):readback_alignment(command,readback,0,floor=1.1)


def test_model_binding_and_schema_reject_drift(tmp_path):
    path=tmp_path/'ridge.npz'
    np.savez(path,mean=np.zeros(16),scale=np.ones(16),coef=np.ones(16),intercept=np.array(0.))
    reference=dict(features=FEATURES,model_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    assert load_bound_model(path,reference)['coef'].shape==(16,)
    reference['model_sha256']='0'*64
    with pytest.raises(ValueError,match='hash'):load_bound_model(path,reference)
    np.savez(path,mean=np.zeros(16),scale=np.zeros(16),coef=np.ones(16),intercept=np.array(0.))
    reference['model_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match='scale'):load_bound_model(path,reference)


def test_reference_reproduction_cannot_ignore_missing_or_changed_metrics():
    row=dict(building='b',weather='w',split='validation',model='ridge',n=2,mae_K=.2,rmse_K=.3)
    verify_reference_metrics([row],[row.copy()])
    with pytest.raises(ValueError):verify_reference_metrics([row],[])
    with pytest.raises(ValueError):verify_reference_metrics([dict(row,mae_K=.201)],[row])


def test_episode_keeps_all_rows_and_readback_units(tmp_path):
    fields=['z_zone_air_temperature_sensor','z_zone_air_heating_temperature_setpoint_sensor',
        'z_zone_air_cooling_temperature_setpoint_sensor','hod_sin_000','hod_cos_000','dow_sin_000','dow_cos_000',
        'z_supply_air_damper_percentage_command','z_reheat_valve_percentage_command']
    m=dict(building='b',weather='w',split='validation',zone_ids=['z'],zone_to_ahu={'z':'a'},observation_fields=fields,
        continuous_fields=['z_supply_air_damper_percentage_command','z_reheat_valve_percentage_command',
            'ahs_a_supply_air_temperature_setpoint','ahs_a_supply_air_static_pressure_setpoint'],
        discrete_fields=['ahs_a_supervisor_run_command'])
    obs=np.array([[293+i,293,297,0,1,0,1,1,0] for i in range(5)],float)
    a=dict(observations_native=obs,observation_valid=np.ones_like(obs,bool),continuous_action=np.tile([1,-1,0,0],(4,1)),
        continuous_action_native=np.tile([1,0,.5,.5],(4,1)),discrete_action=np.ones((4,1)),
        delta_temperature_K=np.ones((4,1)),target_valid=np.ones((4,1),bool),timestamps=np.array(['t0','t1','t2','t3','t4']),
        zone_temperature_K=obs[:,:1])
    model=dict(mean=np.zeros(16),scale=np.ones(16),coef=np.zeros(16),intercept=np.array(0.))
    result=analyze_episode(tmp_path,m,a,model,(np.full(16,-1000),np.full(16,1000)))
    assert [r['n'] for r in result['building']]==[4,4]
    assert all(r['mae_K']==1 for r in result['zones'])
    assert all(r['mae_native']==0 for r in result['readbacks'])
    summary=compact_findings(result)
    assert summary['zone_summary'][0]['ridge_mae_worse_zones']==0
    assert summary['action_summary'][0]['constant_fields']==5


def test_wrong_dataset_receipt_fails_before_model_or_output(tmp_path):
    import json
    root=tmp_path/'corpus';root.mkdir();(root/'dataset.json').write_text('{}')
    reference=tmp_path/'reference.json';reference.write_text(json.dumps({'dataset_receipt_sha256':'0'*64}))
    output=tmp_path/'output'
    with pytest.raises(ValueError,match='dataset receipt hash'):
        run(root,tmp_path/'missing-model.npz',output,reference)
    assert not output.exists()


def test_tail_statistics_zero_error_are_explicitly_undefined():
    result=error_stats(np.array([0.,2.]),np.array([0.,2.]))
    assert result['tail_gt_1K']['n']==1
    assert result['tail_gt_1K']['absolute_error_share'] is None


def test_model_changed_during_validation_cannot_be_relabelled(tmp_path,monkeypatch):
    import json
    import team_tools.forecast_diagnostics as diagnostic
    root=tmp_path/'corpus';root.mkdir();(root/'dataset.json').write_text(json.dumps({'episodes':[]}));(root/'dataset_manifest.yaml').write_text('plan')
    model_path=tmp_path/'ridge.npz'
    model=dict(mean=np.zeros(16),scale=np.ones(16),coef=np.ones(16),intercept=np.array(0.))
    np.savez(model_path,**model)
    reference=dict(features=FEATURES,model_sha256=diagnostic.digest(model_path),
        dataset_receipt_sha256=diagnostic.digest(root/'dataset.json'),dataset_manifest_sha256=diagnostic.digest(root/'dataset_manifest.yaml'),
        source_sha256=diagnostic.digest(diagnostic.Path(diagnostic.__file__).with_name('forecast.py')))
    reference_path=tmp_path/'reference.json';reference_path.write_text(json.dumps(reference))
    def mutate(_):
        np.savez(model_path,**dict(model,coef=np.zeros(16)))
        return {}
    monkeypatch.setattr(diagnostic,'validate_corpus',mutate)
    with pytest.raises(ValueError,match='changed during preflight'):
        run(root,model_path,tmp_path/'output',reference_path)
    assert not (tmp_path/'output').exists()
