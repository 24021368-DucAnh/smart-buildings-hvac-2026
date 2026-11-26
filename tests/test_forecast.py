import numpy as np
import pytest
from team_tools.forecast import causal_history, fit_ridge, predict
from team_tools.forecast import zone_features, FEATURES


def test_history_never_reads_next_row():
    x=np.array([[1.,2.],[3.,4.],[1000.,2000.]])
    np.testing.assert_array_equal(causal_history(x), [[0.,0.],[1.,2.],[3.,4.]])


def test_train_only_scaler_and_serializable_model():
    x=np.array([[0.,2.],[2.,2.],[4.,2.]])
    y=np.array([0.,2.,4.])
    model=fit_ridge(x,y,alpha=1.)
    np.testing.assert_allclose(model['mean'], [2.,2.])
    assert np.isfinite(predict(model,np.array([[10000.,2.]]))).all()
    assert model['scale'][1]==1
    assert np.mean(abs(predict(model,x)-y)) < np.mean(abs(y))


def test_nonfinite_rejected():
    with pytest.raises(ValueError):
        fit_ridge(np.array([[np.nan],[1.]]),np.array([0.,1.]))


def test_matches_independent_sklearn_ridge():
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    x=np.random.default_rng(42).normal(size=(40,4))
    y=2*x[:,0]-.2*x[:,1]+.3
    scaler=StandardScaler().fit(x)
    reference=Ridge(alpha=1.).fit(scaler.transform(x),y)
    np.testing.assert_allclose(predict(fit_ridge(x,y),x),reference.predict(scaler.transform(x)),atol=1e-12)


def test_zone_features_cannot_see_future_or_reward_or_building_identity():
    names=['z_zone_air_temperature_sensor','z_zone_air_heating_temperature_setpoint_sensor',
           'z_zone_air_cooling_temperature_setpoint_sensor','hod_sin_000','hod_cos_000','dow_sin_000','dow_cos_000']
    m=dict(observation_fields=names,zone_ids=['z'],zone_to_ahu={'z':'a'},
           continuous_fields=['z_supply_air_damper_percentage_command','z_reheat_valve_percentage_command',
                              'ahs_a_supply_air_temperature_setpoint','ahs_a_supply_air_static_pressure_setpoint'],
           discrete_fields=['ahs_a_supervisor_run_command'])
    a=dict(observations_native=np.array([[294,293,297,0,1,0,1]]*4,dtype=float),
           observation_valid=np.ones((4,7),bool),continuous_action=np.zeros((3,4)),
           discrete_action=np.ones((3,1)),target_valid=np.ones((3,1),bool),
           delta_temperature_K=np.zeros((3,1)),rewards=np.zeros(3))
    x,y=zone_features(a,m,0)
    a['observations_native'][2:,0]=999
    a['delta_temperature_K'][:]=999
    a['rewards'][:]=999
    m['building']='unseen_fake_id'
    changed,_=zone_features(a,m,0)
    np.testing.assert_array_equal(x[:2],changed[:2])
    assert x.shape==(3,len(FEATURES))
    a['observation_valid'][0,0]=False
    with pytest.raises(ValueError,match='missing feature'):
        zone_features(a,m,0)
