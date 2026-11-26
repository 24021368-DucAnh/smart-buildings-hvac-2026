"""Bounded paired diagnostics; reuse B02 runner and official evaluator unchanged."""
import json
from pathlib import Path
import time
from team_tools import run_batch as rb


def completion_status(runs,expected):
    if any(r['exit_code'] for r in runs):return 'FAILED'
    actual={(r['scenario'],r['policy'],r['steps']) for r in runs}
    return 'SUCCEEDED' if actual==expected and len(runs)==len(expected) else 'INCOMPLETE_BUDGET'


def main():
    started=time.perf_counter();budget=2400
    # A's official wrapper registers its policy using the same official main().
    rb.EVALUATOR_BOOTSTRAP=rb.EVALUATOR_BOOTSTRAP.replace(
        "runpy.run_module('smart_buildings.evaluate', run_name='__main__')",
        "runpy.run_module('team.evaluate_a', run_name='__main__')")
    stamp=time.strftime('%Y%m%d-%H%M%S');runs=[]
    expected={(pair,policy,steps) for steps in (288,8640)
              for pair in ('building_train_1/fairbanks_1','building_train_4/phoenix_8')
              for policy in ('pid','pid_water','member_a') if steps==8640 or 'fairbanks' in pair}
    def save():
        status=completion_status(runs,expected)
        Path('artifacts/base_comparison.json').write_text(json.dumps(dict(runs=runs,wall_budget_s=budget,
            runtime_s=time.perf_counter()-started,status=status,expected_jobs=len(expected),completed_jobs=len(runs),
            missing=sorted(expected-{(r['scenario'],r['policy'],r['steps']) for r in runs}),
            scope='Two-scenario diagnostics; not a suite score'),indent=2))
        return status
    for steps in (288,8640):
        for pair in ('building_train_1/fairbanks_1','building_train_4/phoenix_8'):
            if steps==288 and 'phoenix' in pair: continue
            for policy in ('pid','pid_water','member_a'):
                remaining=int(budget-(time.perf_counter()-started))
                if remaining<30:
                    save();return 2
                args=rb.build_parser().parse_args(['--policy',policy,'--steps',str(steps),
                    '--scenario',pair,'--experiment-id',f'base-{stamp}-{steps}-{pair.split("/")[0]}-{policy}',
                    '--timeout-seconds',str(min(600,remaining))])
                result=rb.run_batch(args)
                runs.append(dict(id=args.experiment_id,exit_code=result,steps=steps,scenario=pair,policy=policy))
                save()
                if result: return 1
    return 0 if save()=='SUCCEEDED' else 2

if __name__=='__main__': raise SystemExit(main())
