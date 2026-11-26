"""B04 frozen-model diagnostics; AI-assisted Member B code.

Reuses forecast.py and validated B03 artifacts. No fitting, simulator or policy
change. Sources/semantics and predeclared decisions: team/B04_PLAN.md and
team/PROJECT_KNOWLEDGE.md. Correlations are descriptive, never causal effects.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import time
from datetime import datetime, timezone

for _key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[_key]='1'
import numpy as np
from team_tools.forecast import FEATURES, episodes, zone_features, predict
from team_tools.dataset import validate_corpus


def vectors(*values):
    arrays=[np.asarray(v,dtype=float) for v in values]
    if any(v.ndim!=1 or not len(v) or not np.isfinite(v).all() for v in arrays):
        raise ValueError('expected nonempty finite vectors')
    if len({len(v) for v in arrays})!=1:raise ValueError('vector length mismatch')
    return arrays


def error_stats(y,p):
    y,p=vectors(y,p);e=p-y;ae=abs(e);sq=e*e
    result=dict(n=len(y),mae_K=float(ae.mean()),rmse_K=float(np.sqrt(sq.mean())),
        bias_K=float(e.mean()),p50_abs_K=float(np.quantile(ae,.5)),
        p90_abs_K=float(np.quantile(ae,.9)),p99_abs_K=float(np.quantile(ae,.99)),max_abs_K=float(ae.max()))
    for threshold in (1,5):
        mask=abs(y)>threshold
        result[f'tail_gt_{threshold}K']=dict(n=int(mask.sum()),fraction=float(mask.mean()),
            absolute_error_share=float(ae[mask].sum()/ae.sum()) if ae.sum() else None,
            squared_error_share=float(sq[mask].sum()/sq.sum()) if sq.sum() else None)
    return result


def action_coverage(values,discrete=False):
    values,=vectors(values)
    low=0 if discrete else -1
    if np.any(values<low-1e-6) or np.any(values>1+1e-6):raise ValueError('action outside normalized range')
    if discrete and not np.isin(values,[0,1]).all():raise ValueError('nonbinary action')
    edges=[-.5,.5,1.5] if discrete else [-1,-.5,0,.5,1]
    changes=np.flatnonzero(abs(np.diff(values))>1e-6)+1
    lengths=np.diff(np.r_[0,changes,len(values)])
    counts=np.histogram(np.clip(values,low,1),edges)[0]
    return dict(n=len(values),minimum=float(values.min()),maximum=float(values.max()),std=float(values.std()),
        unique_rounded_4dp=int(len(np.unique(np.round(values,4)))),
        fraction_at_low=float(np.isclose(values,low,atol=1e-6,rtol=0).mean()),
        fraction_at_high=float(np.isclose(values,1,atol=1e-6,rtol=0).mean()),
        switch_fraction=float(len(changes)/(len(values)-1)) if len(values)>1 else None,
        longest_constant_steps=int(lengths.max()),bin_counts=counts.tolist())


def lag_association(command,target,lag):
    command,target=vectors(command,target)
    if not isinstance(lag,int) or lag<0:raise ValueError('lag must be a nonnegative integer')
    x,y=(command[:-lag],target[lag:]) if lag else (command,target)
    value=None
    if len(x)>1 and np.std(x)>1e-12 and np.std(y)>1e-12:value=float(np.corrcoef(x,y)[0,1])
    return dict(lag_steps=lag,n=len(x),pearson=value)


def readback_alignment(command,observations,lag,floor=None):
    command,=vectors(command);observations,=vectors(observations)
    if len(observations)!=len(command)+1:raise ValueError('readback needs T+1 observations')
    if not isinstance(lag,int) or lag<0 or lag>=len(command):raise ValueError('invalid lag')
    if floor is not None:
        if not np.isfinite(floor) or not 0<=floor<=1:raise ValueError('invalid readback floor')
        command=np.maximum(command,floor)
    x,y=(command[:-lag],observations[1+lag:]) if lag else (command,observations[1:])
    error=abs(y-x)
    return dict(lag_steps=lag,n=len(x),mae_native=float(error.mean()),match_fraction=float((error<=1e-5).mean()))


def digest(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):result.update(chunk)
    return result.hexdigest()


def load_bound_model(path,reference):
    if digest(path)!=reference['model_sha256']:raise ValueError('model hash differs from fixed B04 reference')
    if reference['features']!=FEATURES:raise ValueError('feature contract changed')
    with np.load(path,allow_pickle=False) as data:model={k:data[k] for k in data.files}
    if set(model)!={'mean','scale','coef','intercept'}:raise ValueError('invalid model keys')
    for key in ('mean','scale','coef'):
        if model[key].shape!=(len(FEATURES),) or not np.isfinite(model[key]).all():raise ValueError('invalid model '+key)
    if model['intercept'].shape!=() or not np.isfinite(model['intercept']):raise ValueError('invalid intercept')
    if np.any(model['scale']<=0):raise ValueError('nonpositive model scale')
    return model


def verify_reference_metrics(actual,expected):
    def keyed(rows):
        result={}
        for row in rows:
            key=tuple(row[k] for k in ('building','weather','split','model'))
            if key in result:raise ValueError('duplicate reference metric')
            result[key]=row
        return result
    a,b=keyed(actual),keyed(expected)
    if set(a)!=set(b):raise ValueError('missing/extra baseline metrics')
    for key in a:
        if a[key]['n']!=b[key]['n']:raise ValueError('sample count differs')
        for metric in ('mae_K','rmse_K'):
            if not np.isfinite(a[key][metric]) or abs(a[key][metric]-b[key][metric])>1e-10:
                raise ValueError('baseline metric did not reproduce: '+str(key)+metric)


def flat_stats(y,p):
    return {k:v for k,v in error_stats(y,p).items() if not isinstance(v,dict)}


def write_csv(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def zone_slices(x,y):
    yield 'all',np.ones(len(y),bool)
    for name,mask in [('below_band',x[:,2]>0),('above_band',x[:,3]>0),('inside_band',(x[:,2]<=0)&(x[:,3]<=0)),
        ('delta_le_0.1K',abs(y)<=.1),('delta_0.1_to_1K',(abs(y)>.1)&(abs(y)<=1)),('delta_gt_1K',abs(y)>1),
        ('first_12_steps',np.arange(len(y))<12),('after_12_steps',np.arange(len(y))>=12)]:
        if mask.any():yield name,mask


def analyze_episode(path,m,a,model,bounds):
    identity={k:m[k] for k in ('building','weather','split')}
    zone_rows=[];slices=[];lags=[];readbacks=[];events=[];support=[];ys=[];ps=[]
    field_index={name:i for i,name in enumerate(m['observation_fields'])}
    continuous_index={name:i for i,name in enumerate(m['continuous_fields'])}
    for z,zone in enumerate(m['zone_ids']):
        x,y=zone_features(a,m,z);p=predict(model,x)
        if not np.isfinite(p).all():raise ValueError('nonfinite prediction')
        ys.append(y);ps.append(p)
        for name,values in [('persistence',np.zeros_like(y)),('ridge',p)]:
            zone_rows.append(dict(**identity,zone=zone,model=name,**flat_stats(y,values)))
            for label,mask in zone_slices(x,y):
                slices.append(dict(**identity,zone=zone,model=name,slice=label,**flat_stats(y[mask],values[mask])))
        for feature in ('damper_t','reheat_t','ahu_on_t'):
            command=x[:,FEATURES.index(feature)]
            for lag in range(4):lags.append(dict(**identity,zone=zone,command=feature,**lag_association(command,y,lag)))
        for suffix in ('supply_air_damper_percentage_command','reheat_valve_percentage_command'):
            field=zone+'_'+suffix
            readback=a['observations_native'][:,field_index[field]]
            if not a['observation_valid'][:,field_index[field]].all():raise ValueError('invalid readback sensor')
            native_command=a['continuous_action_native'][:,continuous_index[field]]
            for lag in range(3):
                row=dict(**identity,zone=zone,command=suffix,**readback_alignment(native_command,readback,lag))
                floor_check=readback_alignment(native_command,readback,lag,floor=.1) if suffix.startswith('supply_air_damper') else None
                row.update(default_floor_0p1_mae_native=floor_check['mae_native'] if floor_check else None,
                    default_floor_0p1_match_fraction=floor_check['match_fraction'] if floor_check else None)
                readbacks.append(row)
        for i,feature in enumerate(FEATURES):
            support.append(dict(**identity,zone=zone,feature=feature,n=len(y),
                out_of_train_range=int(((x[:,i]<bounds[0][i]-1e-6)|(x[:,i]>bounds[1][i]+1e-6)).sum()),
                abs_train_z_gt_3=int((abs((x[:,i]-model['mean'][i])/model['scale'][i])>3).sum())))
        step=int(np.argmax(abs(p-y)))
        events.append(dict(**identity,zone=zone,step=step,timestamp=str(a['timestamps'][step]),
            next_timestamp=str(a['timestamps'][step+1]),temperature_K=float(x[step,0]),
            next_temperature_K=float(a['zone_temperature_K'][step+1,z]),
            target_delta_K=float(y[step]),ridge_delta_K=float(p[step]),ridge_abs_error_K=float(abs(p[step]-y[step])),
            previous_sensor_delta_K=float(x[step,1]),heating_margin_K=float(x[step,2]),cooling_margin_K=float(x[step,3]),
            damper_command_normalized=float(x[step,4]),reheat_command_normalized=float(x[step,5])))
    y=np.concatenate(ys);p=np.concatenate(ps)
    building=[dict(**identity,model=name,**error_stats(y,values)) for name,values in [('persistence',np.zeros_like(y)),('ridge',p)]]
    coverage=[]
    for key,names,discrete in [('continuous_action',m['continuous_fields'],False),('discrete_action',m['discrete_fields'],True)]:
        for i,field in enumerate(names):
            coverage.append(dict(**identity,field=field,action_type=key,**action_coverage(a[key][:,i],discrete)))
    return dict(building=building,zones=zone_rows,slices=slices,lags=lags,readbacks=readbacks,
        events=events,support=support,coverage=coverage)


def compact_findings(tables):
    buildings=tables['building'];zone_summary=[];readback_summary=[];support_summary=[];action_summary=[];lag_summary=[]
    for row in buildings:
        if row['model']!='ridge':continue
        building=row['building'];zones=[r for r in tables['zones'] if r['building']==building]
        base={r['zone']:r for r in zones if r['model']=='persistence'}
        deltas=[r['mae_K']-base[r['zone']]['mae_K'] for r in zones if r['model']=='ridge']
        zone_summary.append(dict(building=building,split=row['split'],zones=len(deltas),
            ridge_mae_better_zones=sum(d<0 for d in deltas),ridge_mae_worse_zones=sum(d>0 for d in deltas),
            zone_macro_mean_mae_delta_K=float(np.mean(deltas))))
        for command in ('supply_air_damper_percentage_command','reheat_valve_percentage_command'):
            for lag in range(3):
                selected=[r for r in tables['readbacks'] if r['building']==building and r['command']==command and r['lag_steps']==lag]
                n=sum(r['n'] for r in selected)
                readback_summary.append(dict(building=building,command=command,lag_steps=lag,n=n,
                    mae_native=sum(r['mae_native']*r['n'] for r in selected)/n,
                    match_fraction=sum(r['match_fraction']*r['n'] for r in selected)/n,
                    default_floor_0p1_mae_native=sum(r['default_floor_0p1_mae_native']*r['n'] for r in selected)/n if command.startswith('supply_air_damper') else None,
                    default_floor_0p1_match_fraction=sum(r['default_floor_0p1_match_fraction']*r['n'] for r in selected)/n if command.startswith('supply_air_damper') else None))
        for command in ('damper_t','reheat_t','ahu_on_t'):
            for lag in range(4):
                selected=[r for r in tables['lags'] if r['building']==building and r['command']==command and r['lag_steps']==lag]
                values=[r['pearson'] for r in selected if r['pearson'] is not None]
                lag_summary.append(dict(building=building,command=command,lag_steps=lag,zone_pairs=len(selected),
                    constant_or_short_pairs=len(selected)-len(values),median_pearson=float(np.median(values)) if values else None))
        for feature in FEATURES:
            selected=[r for r in tables['support'] if r['building']==building and r['feature']==feature];n=sum(r['n'] for r in selected)
            support_summary.append(dict(building=building,split=row['split'],feature=feature,n=n,
                out_of_train_range_fraction=sum(r['out_of_train_range'] for r in selected)/n,
                abs_train_z_gt_3_fraction=sum(r['abs_train_z_gt_3'] for r in selected)/n))
        selected=[r for r in tables['coverage'] if r['building']==building]
        action_summary.append(dict(building=building,split=row['split'],fields=len(selected),
            constant_fields=sum(r['std']<=1e-12 for r in selected),
            reheat_fields=sum(r['field'].endswith('reheat_valve_percentage_command') for r in selected),
            constant_reheat_fields=sum(r['std']<=1e-12 and r['field'].endswith('reheat_valve_percentage_command') for r in selected),
            very_low_switch_fields=sum(r['switch_fraction'] is not None and r['switch_fraction']<.01 for r in selected),
            definition='Constant std<=1e-12; low-switch fraction<1%; descriptive only, not causal identifiability.'))
    slice_summary=[]
    for building,label,model in sorted({(r['building'],r['slice'],r['model']) for r in tables['slices']}):
        selected=[r for r in tables['slices'] if r['building']==building and r['slice']==label and r['model']==model]
        n=sum(r['n'] for r in selected)
        slice_summary.append(dict(building=building,slice=label,model=model,n=n,
            mae_K=sum(r['mae_K']*r['n'] for r in selected)/n,
            rmse_K=float(np.sqrt(sum(r['rmse_K']**2*r['n'] for r in selected)/n)),
            bias_K=sum(r['bias_K']*r['n'] for r in selected)/n))
    return dict(zone_summary=zone_summary,readback_summary=readback_summary,lag_summary=lag_summary,slice_summary=slice_summary,
        feature_support=support_summary,action_summary=action_summary,
        worst_event_per_zone_top12=sorted(tables['events'],key=lambda r:r['ridge_abs_error_K'],reverse=True)[:12])


def make_plots(out,tables,findings):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    buildings=[r['building'] for r in tables['building'] if r['model']=='ridge']
    labels={b:b.replace('building_train_','').replace('building_','')+'\n'+next(r['split'] for r in tables['building'] if r['building']==b) for b in buildings}
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for ax,metric in zip(axes,('mae_K','rmse_K')):
        for offset,name in [(-.18,'persistence'),(.18,'ridge')]:
            values=[next(r[metric] for r in tables['building'] if r['building']==b and r['model']==name) for b in buildings]
            ax.bar(np.arange(len(buildings))+offset,values,.36,label=name)
        ax.set_xticks(range(len(buildings)),[labels[b] for b in buildings],rotation=15)
        ax.set(xlabel='Building (one fixed episode each)',ylabel=metric+' [K]',title='Frozen B04 sensor-delta prediction');ax.legend()
    fig.suptitle('B03 corpus / original fixed Ridge; descriptive replay, no refit')
    fig.tight_layout();fig.savefig(out/'building_errors.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4))
    for i,b in enumerate(buildings):
        selected=[r for r in tables['zones'] if r['building']==b];base={r['zone']:r['mae_K'] for r in selected if r['model']=='persistence'}
        deltas=[r['mae_K']-base[r['zone']] for r in selected if r['model']=='ridge']
        ax.scatter(np.full(len(deltas),i),deltas,s=12,alpha=.5)
    ax.axhline(0,color='gray',linewidth=1);ax.set_xticks(range(len(buildings)),[labels[b] for b in buildings],rotation=15)
    ax.set(xlabel='Building; each dot one zone',ylabel='Ridge MAE - persistence MAE [K]',title='Zone errors: negative means Ridge better; all zones retained')
    fig.tight_layout();fig.savefig(out/'zone_mae_deltas.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for ax,command in zip(axes,('supply_air_damper_percentage_command','reheat_valve_percentage_command')):
        for b in buildings:
            selected=[r for r in findings['readback_summary'] if r['building']==b and r['command']==command]
            ax.plot([r['lag_steps'] for r in selected],[r['mae_native'] for r in selected],marker='o',label=b.replace('building_train_','train_'))
        title='VAV damper position' if command.startswith('supply') else 'VAV reheat valve'
        ax.set(xlabel='Past command lag [steps of 5 min]',ylabel='MAE vs post-action readback [fraction 0..1]',title=title);ax.set_xticks([0,1,2]);ax.legend(fontsize=7)
    fig.suptitle('Observed actuator readback, not latent temperature or causal response')
    fig.tight_layout();fig.savefig(out/'readback_alignment.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for ax,suffix in zip(axes,('supply_air_damper_percentage_command','reheat_valve_percentage_command')):
        for i,split in enumerate(('train','validation','generated_dev')):
            selected=[r for r in tables['coverage'] if r['split']==split and r['field'].endswith(suffix)]
            counts=np.sum([r['bin_counts'] for r in selected],axis=0)
            ax.bar(np.arange(4)+(i-1)*.25,counts/counts.sum(),.25,label=split)
        ax.set_xticks(range(4),['[-1,-.5)','[-.5,0)','[0,.5)','[.5,1]'])
        ax.set(xlabel='Chosen normalized command bin',ylabel='Fraction of zone-action steps',title='Damper' if suffix.startswith('supply') else 'Reheat');ax.legend()
    fig.suptitle('B03 official pid_water observations; sample-weighted coverage, not interventions')
    fig.tight_layout();fig.savefig(out/'action_coverage.png',dpi=160);plt.close(fig)


def run(root,model_path,out,reference_path,budget_s=600):
    started=time.perf_counter();cpu=time.process_time();repo=Path(__file__).resolve().parents[1]
    reference_pin=digest(reference_path);reference=json.loads(reference_path.read_text(encoding='utf-8'))
    if 'frozen_holdout' in [p.casefold() for p in root.resolve().parts]:raise ValueError('holdout is closed')
    if digest(root/'dataset.json')!=reference['dataset_receipt_sha256']:raise ValueError('dataset receipt hash differs')
    if digest(root/'dataset_manifest.yaml')!=reference['dataset_manifest_sha256']:raise ValueError('dataset plan hash differs')
    if digest(repo/'team_tools/forecast.py')!=reference['source_sha256']:raise ValueError('forecast source differs')
    model=load_bound_model(model_path,reference)
    validation=validate_corpus(root)
    receipt=json.loads((root/'dataset.json').read_text(encoding='utf-8'))
    paths={'model':model_path,'reference':reference_path,'dataset/dataset.json':root/'dataset.json'}
    for item in receipt['episodes']:
        for name in item['files']:paths['dataset/episodes/'+item['directory']+'/'+name]=root/'episodes'/item['directory']/name
    for name in ('team_tools/forecast.py','team_tools/forecast_diagnostics.py','team_tools/dataset.py',
        'smart_buildings/smart_control/simulator/vav.py','smart_buildings/smart_control/simulator/simulator.py',
        'smart_buildings/smart_control/environment/environment.py'):paths['source/'+name]=repo/name
    pins={key:digest(path) for key,path in paths.items()}
    if pins['model']!=reference['model_sha256'] or pins['reference']!=reference_pin:
        raise ValueError('bound model/reference changed during preflight')
    if pins['source/team_tools/forecast.py']!=reference['source_sha256']:
        raise ValueError('forecast source changed during preflight')
    for item in receipt['episodes']:
        for name,checksum in item['files'].items():
            if pins['dataset/episodes/'+item['directory']+'/'+name]!=checksum:raise ValueError('episode changed after validation')
    def check_budget():
        if time.perf_counter()-started>budget_s:raise TimeoutError('offline diagnostic budget exceeded')
    check_budget();out.mkdir(parents=True,exist_ok=False)
    try:
        lower=np.full(len(FEATURES),np.inf);upper=-lower
        for _,m,a in episodes(root):
            if m['split']!='train':continue
            for z in range(len(m['zone_ids'])):
                x,_=zone_features(a,m,z);lower=np.minimum(lower,x.min(axis=0));upper=np.maximum(upper,x.max(axis=0))
            check_budget()
        if not np.isfinite(lower).all():raise ValueError('no training support')
        tables={k:[] for k in ('building','zones','slices','lags','readbacks','events','support','coverage')}
        for path,m,a in episodes(root):
            result=analyze_episode(path,m,a,model,(lower,upper))
            for key in tables:tables[key].extend(result[key])
            check_budget()
        verify_reference_metrics(tables['building'],reference['metrics'])
        findings=compact_findings(tables);make_plots(out,tables,findings);check_budget()
        if any(digest(path)!=pins[key] for key,path in paths.items()):raise ValueError('input/source changed during analysis')
        for key,rows in tables.items():
            flat=[{k:json.dumps(v) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows]
            write_csv(out/(key+'.csv'),flat)
        sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
        report=dict(status='VERIFIED_FROZEN_MODEL_DIAGNOSTIC',updated_utc=datetime.now(timezone.utc).isoformat(),
            source_sha=sha,working_tree_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=repo).strip()),
            source_sha_scope='HEAD base plus exact diagnostic/source hashes; no historical receipt relabeling',
            dataset_id=root.name,model_sha256=pins['model'],input_fingerprints=pins,
            source_urls=['https://github.com/smart-buildings-2026/starter-kit','https://github.com/24021368-DucAnh/smart-buildings-hvac-2026'],
            ai_assistance='Codex/ChatGPT implemented B diagnostic/tests/notes; inherited official env and B04 model retained.',
            human_person_hours=None,rows_dropped=0,model_refit=False,simulator_steps=0,
            corpus_transitions=validation['total_transitions'],zone_samples=validation['total_zone_transition_samples'],
            reproduction_tolerance=1e-10,building_metrics=tables['building'],**findings,
            train_support_bounds=dict(zip(FEATURES,[dict(minimum=float(lo),maximum=float(hi)) for lo,hi in zip(lower,upper)])),
            decision='KEEP_RIDGE_OFFLINE_B05_OFF; no new model/control gain tested',
            limitations=['One weather per building; building/climate confounded','Single observational pid_water behavior policy; action correlations not causal',
                'Generated0500 was already seen in development, not a final holdout','Readback equality does not prove thermal response or physical plausibility',
                'Feature range/z flags are descriptive, not a calibrated OOD detector','Past-lag analysis never selects features or tunes the model',
                'Target-delta slices are retrospective; their true future label cannot select an inference fallback'],
            not_run=['Model refit/tuning','New simulator rollouts','Frozen holdout','B05 control','Kaggle status verification'],
            python=sys.version,numpy=np.__version__,numerical_threads=1,wall_budget_s=budget_s,
            runtime_wall_s=time.perf_counter()-started,process_cpu_s=time.process_time()-cpu)
        (out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        print(json.dumps(dict(status=report['status'],output=str(out),runtime_wall_s=report['runtime_wall_s'])));return report
    except Exception as error:
        (out/'failure.json').write_text(json.dumps(dict(status='FAILED',error=str(error),runtime_wall_s=time.perf_counter()-started)),encoding='utf-8')
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset',type=Path);parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--reference',type=Path,default=Path('team/B04_checks.json'))
    args=parser.parse_args()
    run(args.dataset,args.model,args.output,args.reference)


if __name__=='__main__':main()
