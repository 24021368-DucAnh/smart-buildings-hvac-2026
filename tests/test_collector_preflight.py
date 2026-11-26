from pathlib import Path
from unittest.mock import patch
import pytest
from team_tools import collect_transitions as c


def test_source_preflight_failure_creates_no_orphan(tmp_path):
    args=c.parser().parse_args(['--steps','288','--scenario','building_train_1/fairbanks_1',
        '--dataset-id','preflight','--output-root',str(tmp_path)])
    with patch.object(c,'make_source_pin',side_effect=FileNotFoundError('missing selected input')):
        with pytest.raises(FileNotFoundError):c.run_collection(args)
    assert not (tmp_path/'preflight').exists()


def test_smoke_pin_only_requires_selected_scenario(tmp_path):
    first=dict(building='b',weather='w',suite='dev_small')
    plan=dict(benchmark_manifest='bench.yaml',episodes=[first,dict(building='g',weather='w',suite='generated_dev')])
    for name in ['plan.yaml','bench.yaml','weather.csv',*[f'team_tools/{n}' for n in ('collect_transitions.py','dataset.py','audit_data.py','benchmark.py','run_batch.py')]]:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('x')
    scenario=tmp_path/'smart_buildings/training_scenarios/b/w';scenario.mkdir(parents=True)
    for name in ('config.yaml','floor_plan.npy','zone_map.npy'):(scenario/name).write_text('asset')
    (tmp_path/'external_floor.npy').write_text('actual external floor')
    (scenario/'config.gin').write_text("weather_csv_path = 'weather.csv'\nfloor_plan_filepath = 'external_floor.npy'\nzone_map_filepath = 'smart_buildings/training_scenarios/b/w/zone_map.npy'\n")
    manifest={'suites':{'dev_small':{},'generated_dev':{'scenarios_dir':'absent-generated'}}}
    with patch.object(c,'load_plan',return_value=plan),patch.object(c,'load_suite',return_value=(manifest,[])):
        pin=c.make_source_pin(tmp_path/'plan.yaml',tmp_path,episodes=[first])
    assert 'smart_buildings/training_scenarios/b/w/config.gin' in pin['files']
    assert not any('absent-generated' in key for key in pin['files'])
    assert any(key.endswith('/external_floor.npy') for key in pin['files'])
