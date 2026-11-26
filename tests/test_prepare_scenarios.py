from pathlib import Path
import pytest
from team_tools.prepare_scenarios import prepare_pair


def test_portable_config_preserves_source_and_redirects_metrics(tmp_path):
    source=tmp_path/'source'; source.mkdir()
    text="weather_csv_path = 'smart_buildings\\weather\\csv\\atlanta.csv'\nmetrics_path = 'data\\metrics'\nfloor_plan_filepath = 'old/floor_plan.npy'\nzone_map_filepath = 'old/zone_map.npy'\nphysics_gain = 1.7\n"
    (source/'config.gin').write_text(text)
    (source/'floor_plan.npy').write_bytes(b'unchanged asset')
    (source/'zone_map.npy').write_bytes(b'zone asset')
    out=tmp_path/'out'
    record=prepare_pair(source,out)
    assert (source/'config.gin').read_text()==text
    effective=(out/'config.gin').read_text()
    assert 'physics_gain = 1.7' in effective
    assert 'smart_buildings/weather/csv/atlanta.csv' in effective
    assert (out/'metrics').as_posix() in effective
    assert (out/'floor_plan.npy').read_bytes()==b'unchanged asset'
    assert (out/'floor_plan.npy').as_posix() in effective
    assert (out/'zone_map.npy').as_posix() in effective
    assert record['source_config_sha256']!=record['effective_config_sha256']
    with pytest.raises(FileExistsError):prepare_pair(source,out)
