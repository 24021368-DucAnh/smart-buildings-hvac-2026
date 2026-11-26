"""B04: offline, building-disjoint persistence versus fixed Ridge baseline.

All feature extraction is causal. Metadata maps variable building dimensions to
the same per-zone columns. The model predicts the next policy-visible sensor
delta, not the simulator's latent thermal state.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
import numpy as np
from team_tools.dataset import validate_corpus

FEATURES=['temperature_K','previous_sensor_delta_K','heating_margin_K','cooling_margin_K',
          'damper_t','reheat_t','damper_previous','reheat_previous',
          'ahu_supply_command_t','ahu_pressure_command_t','ahu_on_t','ahu_on_previous',
          'hod_sin','hod_cos','dow_sin','dow_cos']


def causal_history(x):
    return np.concatenate([np.zeros_like(x[:1]),x[:-1]],axis=0)


def fit_ridge(x,y,alpha=1.):
    if not np.isfinite(x).all() or not np.isfinite(y).all() or alpha<=0:
        raise ValueError('nonfinite training data or invalid alpha')
    mean=x.mean(axis=0); scale=x.std(axis=0); scale[scale==0]=1
    z=(x-mean)/scale; intercept=float(y.mean())
    coef=np.linalg.solve(z.T@z + alpha*np.eye(z.shape[1]), z.T@(y-intercept))
    return dict(mean=mean,scale=scale,coef=coef,intercept=np.array(intercept))


def predict(model,x):
    return ((x-model['mean'])/model['scale'])@model['coef']+model['intercept']


def zone_features(a,m,z):
    """No t+1/reward/ID enters x; IDs are used solely to resolve metadata indices."""
    fields={f:i for i,f in enumerate(m['observation_fields'])}
    ci={f:i for i,f in enumerate(m['continuous_fields'])}
    di={f:i for i,f in enumerate(m['discrete_fields'])}
    vav=m['zone_ids'][z]; ahu=m['zone_to_ahu'][vav]
    obs=a['observations_native'][:-1]
    def sensor(name):
        i=fields[name]
        if not a['observation_valid'][:-1,i].all():
            raise ValueError('missing feature sensor: '+name)
        return obs[:,i]
    def command(name): return a['continuous_action'][:,ci[name]].astype(float)
    temp=sensor(vav+'_zone_air_temperature_sensor')
    # At the first step no previous transition exists: fixed zero history.
    previous_delta=np.r_[0.,np.diff(temp)]
    damper=command(vav+'_supply_air_damper_percentage_command')
    reheat=command(vav+'_reheat_valve_percentage_command')
    on=a['discrete_action'][:,di['ahs_'+ahu+'_supervisor_run_command']].astype(float)
    x=np.column_stack([temp,previous_delta,
        sensor(vav+'_zone_air_heating_temperature_setpoint_sensor')-temp,
        temp-sensor(vav+'_zone_air_cooling_temperature_setpoint_sensor'),
        damper,reheat,causal_history(damper),causal_history(reheat),
        command('ahs_'+ahu+'_supply_air_temperature_setpoint'),
        command('ahs_'+ahu+'_supply_air_static_pressure_setpoint'),on,causal_history(on),
        *[sensor(n+'_000') for n in ('hod_sin','hod_cos','dow_sin','dow_cos')]])
    if not np.isfinite(x).all() or not a['target_valid'][:,z].all():
        raise ValueError('invalid features/target: no silent row dropping')
    return x,a['delta_temperature_K'][:,z].astype(float)


def episodes(root):
    for p in sorted((root/'episodes').iterdir()):
        m=json.loads((p/'metadata.json').read_text(encoding='utf-8'))
        with np.load(p/'arrays.npz',allow_pickle=False) as f:
            a={k:f[k] for k in f.files}
        yield p,m,a


def metrics(y,p):
    e=p-y
    return dict(n=len(y),mae_K=float(np.mean(abs(e))),rmse_K=float(np.sqrt(np.mean(e*e))))


def run(root,out):
    started=time.perf_counter()
    validation=validate_corpus(root)
    out.mkdir(parents=True,exist_ok=False)
    xs=[];ys=[]
    for _,m,a in episodes(root):
        if m['split']!='train': continue
        for z in range(len(m['zone_ids'])):
            x,y=zone_features(a,m,z);xs.append(x);ys.append(y)
    model=fit_ridge(np.concatenate(xs),np.concatenate(ys))
    train_samples=sum(len(y) for y in ys)
    del xs,ys
    np.savez(out/'ridge.npz',**model)
    # Verify offline roundtrip before measuring unseen buildings.
    with np.load(out/'ridge.npz',allow_pickle=False) as f:
        restored={k:f[k] for k in f.files}
    rows=[];zone_rows=[]
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for p,m,a in episodes(root):
        target=[];preds=[]
        for z,vav in enumerate(m['zone_ids']):
            x,y=zone_features(a,m,z);pred=predict(restored,x)
            if z==0:
                np.testing.assert_allclose(pred,predict(model,x),rtol=0,atol=0)
                fig,ax=plt.subplots(figsize=(10,3))
                ax.plot(y[:288],label='Observed sensor delta');ax.plot(pred[:288],label='Ridge')
                ax.axhline(0,color='gray',label='Persistence');ax.set(xlabel='5-minute step',ylabel='Delta K',title=m['scenario']+' / '+vav)
                ax.legend();fig.tight_layout();fig.savefig(out/(p.name+'.png'));plt.close(fig)
            for name,values in [('persistence',np.zeros_like(y)),('ridge',pred)]:
                zone_rows.append(dict(building=m['building'],weather=m['weather'],split=m['split'],zone=vav,model=name,**metrics(y,values)))
            target.append(y);preds.append(pred)
        y=np.concatenate(target);pred=np.concatenate(preds)
        np.savez_compressed(out/(p.name+'_predictions.npz'),target=y,ridge=pred)
        for name,values in [('persistence',np.zeros_like(y)),('ridge',pred)]:
            rows.append(dict(building=m['building'],weather=m['weather'],split=m['split'],model=name,**metrics(y,values)))
    for name,data in [('metrics.csv',rows),('zone_metrics.csv',zone_rows)]:
        with (out/name).open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    report=dict(status='VERIFIED_OFFLINE_BASELINE',dataset=str(root.resolve()),
        git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        source_sha256=sha(Path(__file__)),dataset_manifest_sha256=sha(root/'dataset_manifest.yaml'),
        model_sha256=sha(out/'ridge.npz'),features=FEATURES,alpha=1.,train_samples=train_samples,
        split_buildings=validation['splits'],metrics=rows,rows_dropped=0,
        runtime_s=time.perf_counter()-started,control_score='NOT RUN',
        limitations=['Fixed observational pid_water trajectories; not causal action identification',
            'One climate per building confounds building and climate transfer',
            'One-step policy-visible sensor forecast; not latent physical state',
            'No model selection on generated-dev; no frozen holdout access',
            'No B05 control integration or guaranteed Kaggle gain'])
    (out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps(report,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dataset',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();run(a.dataset,a.output)

if __name__=='__main__': main()
