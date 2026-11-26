"""Read-only compatibility checks for the selected main and imported B sources."""
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
from team.policy.zone_controller import ZoneController


def main():
    def git(*a):return subprocess.check_output(['git',*a],text=True).strip()
    names=['z_zone_air_temperature_sensor','z_zone_air_heating_temperature_setpoint_sensor',
           'z_zone_air_cooling_temperature_setpoint_sensor','hod_sin_000','hod_cos_000','dow_sin_000','dow_cos_000']
    meta=dict(comfort_temp_window=[295.,297.],eco_temp_window=[290.,300.],
        morning_start_hour=8,evening_start_hour=18,
        observation_normalization_metadata={'zone_air_temperature_sensor':{'sample_mean':295.,'sample_std':5.}},
        observation_field_names=names,zone_action_indices={'z':{'supply_air_damper_percentage_command':2,'reheat_valve_percentage_command':3}})
    module=ZoneController(meta)
    obs=np.array([-.2,295.,297.,0.,1.,0.,1.])
    action={'continuous_action':np.zeros(6,dtype=np.float32),'discrete_action':np.ones(2,dtype=np.int32)}
    old={k:v.copy() for k,v in action.items()}; result=module.adjust(obs,action,{})
    slots=np.flatnonzero(result['continuous_action']!=old['continuous_action']).tolist()
    assert set(slots)<= {2,3}
    np.testing.assert_array_equal(result['discrete_action'],old['discrete_action'])
    assert module._denormalize_temp(-.2)==294.
    report=dict(main_sha=git('rev-parse','HEAD'),
        diff_since_original=git('diff','--name-only','78d8b62f6d13454dc83370b1adf7be88190b5720','HEAD').splitlines(),
        official_source_diff=git('diff','--name-only','78d8b62f6d13454dc83370b1adf7be88190b5720','HEAD','--','smart_buildings','score_leaderboard.py'),
        setpoint_units='VERIFIED raw Kelvin in pid_plus and B01 runtime normalization audit',
        zone_temperature_example_K=module._denormalize_temp(-.2),
        A_writes_only_zone_slots_fixture=True,
        A_mutates_incoming_action=any(not np.array_equal(action[k],old[k]) for k in action),
        open_contract_items=['A adjust mutates incoming action; composer copy boundary or A fix needed before shared integration',
            'No enable_a / flag-off identity composer present in current main',
            'A _command_zones delegates all zones on each AHU call; redundant repeated writes, review scaling',
            'G1 public candidate license/source/reproduction matrix and base lock not present in main diff',
            'B01 phase audit describes command application and delayed sensor readback separately; preserve distinction'],
        imported_B_sources={str(p).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
            for directory in ('team_tools','configs','tests') for p in Path(directory).rglob('*') if p.is_file() and '__pycache__' not in str(p)},
        source_layout='Existing B layout retained as explicitly documented in team/README.md')
    Path('artifacts/main_compatibility.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
