import hashlib
from pathlib import Path
import pytest
from team_tools.run_batch import verify_numeric_pin
from team_tools.benchmark import BenchmarkError
from team_tools.run_batch import scenario_input_pin


def test_numeric_pin_detects_changed_or_missing_file(tmp_path):
    p=tmp_path/'physics.py';p.write_bytes(b'original')
    pin={'physics.py':hashlib.sha256(p.read_bytes()).hexdigest()}
    verify_numeric_pin(pin,tmp_path)
    p.write_bytes(b'changed')
    with pytest.raises(BenchmarkError):verify_numeric_pin(pin,tmp_path)


def test_generated_actual_inputs_are_pinned(tmp_path):
    scenario=tmp_path/'scenarios/b/w';scenario.mkdir(parents=True)
    weather=tmp_path/'weather.csv';weather.write_text('data')
    for name in ('config.yaml','floor_plan.npy','zone_map.npy'):(scenario/name).write_text('asset')
    (scenario/'config.gin').write_text(f"weather_csv_path = '{weather.as_posix()}'\nfloor_plan_filepath = '{(scenario/'floor_plan.npy').as_posix()}'\nzone_map_filepath = '{(scenario/'zone_map.npy').as_posix()}'\n")
    pin=scenario_input_pin(tmp_path/'scenarios',[dict(building='b',weather='w')])
    verify_numeric_pin(pin,tmp_path)
    weather.write_text('changed weather')
    with pytest.raises(BenchmarkError):verify_numeric_pin(pin,tmp_path)
