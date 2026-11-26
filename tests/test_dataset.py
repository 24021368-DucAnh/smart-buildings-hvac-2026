"""Hand-checked synthetic fixtures: these are never measured datasets."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import json
import hashlib
from datetime import datetime,timedelta

import numpy as np
import yaml

from team_tools.dataset import DatasetError, TransitionBuffer, validate_arrays, load_plan, validate_corpus


def metadata(d=3, c=2, k=1):
    return dict(observation_fields=["VAV_1_zone_air_temperature_sensor"]+[f"field_{i}" for i in range(1,d)],
                observation_source_keys=[dict(device="VAV_1",measurement="zone_air_temperature_sensor")]+[dict(device="environment",measurement=f"field_{i}") for i in range(1,d)],
                observation_mean=[295.] + [0.] * (d-1), observation_std=[5.] + [1.] * (d-1),
                zone_indices=[0], zone_ids=["VAV_1"], zone_to_ahu={"VAV_1":"ahu_1"},
                continuous_fields=[f"c_{i}" for i in range(c)], discrete_fields=[f"k_{i}" for i in range(k)],
                continuous_native_min=[0.]*c, continuous_native_max=[20.]*c,
                dt_seconds=300, expected_steps=2)


def fixture(d=3,c=2,k=1):
    m=metadata(d,c,k)
    buffer=TransitionBuffer(m, np.array([-.2]+[0.]*(d-1),np.float32), '2023-01-01T00:00:00')
    action=dict(continuous_action=np.zeros(c,np.float32),discrete_action=np.ones(k,np.int32))
    for i,z in enumerate([0.,.2],1):
        buffer.append(action,np.array([z]+[0.]*(d-1),np.float32),f'2023-01-01T00:{i*5:02d}:00',-1.,False,False)
    return m,buffer.arrays()


class DatasetTests(unittest.TestCase):
    def test_observation_labels_cannot_be_permuted_apart_from_source_keys(self):
        m,a=fixture();m['observation_fields'][0],m['observation_fields'][1]=m['observation_fields'][1],m['observation_fields'][0]
        with self.assertRaises(DatasetError):validate_arrays(a,m,require_full=False)

    def test_zone_id_cannot_be_changed_without_changing_its_source_measurement(self):
        m,a=fixture();m['zone_ids']=['VAV_2'];m['zone_to_ahu']={'VAV_2':'ahu_1'}
        with self.assertRaises(DatasetError):validate_arrays(a,m,require_full=False)

    def test_plan_requires_the_locked_corpus_size_and_split_counts(self):
        repo=Path(__file__).resolve().parents[1]
        plan=yaml.safe_load((repo/'configs/dataset_manifest.yaml').read_text())
        plan['episodes']=plan['episodes'][:1]
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'plan.yaml';p.write_text(yaml.safe_dump(plan))
            with self.assertRaises(DatasetError):load_plan(p,repo)

    def test_explicit_expanded_plan_can_add_weather_without_weakening_group_splits(self):
        repo=Path(__file__).resolve().parents[1]
        plan=yaml.safe_load((repo/'configs/dataset_manifest.yaml').read_text())
        plan['episodes'].append(dict(suite='dev_full',building='building_train_1',weather='atlanta_2',split='train'))
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'plan.yaml';p.write_text(yaml.safe_dump(plan))
            self.assertEqual(len(load_plan(p,repo)['episodes']),7)

    def test_action_variation_reports_amplitude_and_switch_counts(self):
        m,a=fixture()
        a['continuous_action'][:,0]=[-1.,1.]
        a['continuous_action_native'][:,0]=[0.,20.]
        a['discrete_action'][:,0]=[0,1]
        q=validate_arrays(a,m,require_full=False)
        self.assertEqual(q['continuous_range_per_channel'][0],2.)
        self.assertEqual(q['continuous_std_per_channel'][0],1.)
        self.assertEqual(q['discrete_switches_per_channel'][0],1)

    def test_kelvin_targets_and_native_actions_are_hand_checked(self):
        m,a=fixture()
        quality=validate_arrays(a,m,require_full=False)
        np.testing.assert_allclose(a['zone_temperature_K'][:,0],[294.,295.,296.],atol=1e-5)
        np.testing.assert_allclose(a['delta_temperature_K'][:,0],[1.,1.],atol=1e-5)
        np.testing.assert_allclose(a['continuous_action_native'],10.)
        self.assertEqual(quality['steps'],2)

    def test_buffer_copies_observations_instead_of_keeping_mutable_views(self):
        m=metadata();obs=np.array([-.2,0.,0.],np.float32)
        b=TransitionBuffer(m,obs,'2023-01-01T00:00:00');obs[0]=0.
        action=dict(continuous_action=np.zeros(2,np.float32),discrete_action=np.ones(1,np.int32))
        b.append(action,obs,'2023-01-01T00:05:00',-1.,False,False)
        obs[0]=99.;action['continuous_action'][:]=1.
        self.assertAlmostEqual(float(b.arrays()['observations'][0,0]),-.2)
        self.assertEqual(float(b.arrays()['observations'][1,0]),0.)
        self.assertEqual(float(b.arrays()['continuous_action'][0,0]),0.)

    def test_variable_building_dimensions_are_supported(self):
        for dims in [(3,2,1),(7,4,2)]:
            with self.subTest(dims=dims):
                m,a=fixture(*dims)
                self.assertEqual(validate_arrays(a,m,require_full=False)['observation_dim'],dims[0])

    def test_missing_observations_are_retained_and_targets_are_masked(self):
        m=metadata(); b=TransitionBuffer(m,np.array([-.2,0,0],np.float32),'2023-01-01T00:00:00')
        action=dict(continuous_action=np.zeros(2,np.float32),discrete_action=np.ones(1,np.int32))
        b.append(action,np.zeros(3,np.float32),'2023-01-01T00:05:00',-1.,False,False,np.array([False,True,True]))
        a=b.arrays();m['expected_steps']=1
        q=validate_arrays(a,m,require_full=False)
        self.assertEqual(q['raw_invalid_sensor_values'],1)
        self.assertEqual(q['masked_zone_targets'],1)
        self.assertEqual(len(a['continuous_action']),1)

    def test_corrupt_arrays_are_rejected(self):
        for mutation in ['nan','duplicate_time','wrong_target','missing','extra','dtype','shape','partial']:
            with self.subTest(mutation=mutation):
                m,a=fixture();a={k:v.copy() for k,v in a.items()}
                if mutation=='nan':a['observations'][0,0]=np.nan
                elif mutation=='duplicate_time':a['timestamps'][1]=a['timestamps'][0]
                elif mutation=='wrong_target':a['delta_temperature_K'][0,0]=100.
                elif mutation=='missing':a.pop('discrete_action')
                elif mutation=='extra':a['future_reward_feature']=np.zeros(2)
                elif mutation=='dtype':a['discrete_action']=a['discrete_action'].astype(np.float32)
                elif mutation=='shape':a['continuous_action']=np.zeros((2,9),np.float32)
                else:m['expected_steps']=3
                with self.assertRaises(DatasetError):validate_arrays(a,m,require_full=False)

    def test_smoke_cannot_be_accepted_as_a_full_training_episode(self):
        m,a=fixture()
        with self.assertRaises(DatasetError):validate_arrays(a,m,require_full=True)

    def test_plan_rejects_building_overlap_and_holdout(self):
        repo=Path(__file__).resolve().parents[1]
        plan=yaml.safe_load((repo/'configs/dataset_manifest.yaml').read_text())
        for mutation in ['overlap','holdout','duplicate']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp:
                value=deepcopy(plan)
                if mutation=='overlap':value['episodes'][1]['building']=value['episodes'][0]['building'];value['episodes'][1]['split']='validation'
                elif mutation=='holdout':value['episodes'][0]['suite']='frozen_holdout'
                else:value['episodes'].append(deepcopy(value['episodes'][0]))
                p=Path(temp)/'plan.yaml';p.write_text(yaml.safe_dump(value))
                with self.assertRaises(DatasetError):load_plan(p,repo)


class CorpusIntegrityTests(unittest.TestCase):
    def make_corpus(self,root):
        repo=Path(__file__).resolve().parents[1]
        (root/'dataset_manifest.yaml').write_bytes((repo/'configs/dataset_manifest.yaml').read_bytes())
        (root/'benchmark_manifest.yaml').write_bytes((repo/'configs/benchmark_manifest.yaml').read_bytes())
        from team_tools.dataset import ARRAY_SCHEMA,FEATURE_CONTRACT
        (root/'schema.json').write_text(json.dumps(dict(version=1,arrays=ARRAY_SCHEMA,feature_contract=FEATURE_CONTRACT)))
        (root/'tracked_changes.patch').write_text('synthetic source fixture')
        (root/'changed_files.zip').write_bytes(b'synthetic zip fixture')
        d=root/'episodes/building_train_1__fairbanks_1';d.mkdir(parents=True)
        m=metadata();m['expected_steps']=288
        t=datetime(2023,1,1)
        b=TransitionBuffer(m,np.array([-.2,0,0],np.float32),t.isoformat())
        action=dict(continuous_action=np.zeros(2,np.float32),discrete_action=np.ones(1,np.int32))
        for i in range(1,289):b.append(action,np.array([0,0,0],np.float32),(t+timedelta(seconds=300*i)).isoformat(),-1.,False,False)
        a=b.arrays();m.update(scenario='building_train_1/fairbanks_1',suite='dev_small',building='building_train_1',weather='fairbanks_1',split='train',policy='pid_water',horizon_steps=1)
        np.savez_compressed(d/'arrays.npz',**a)
        (d/'metadata.json').write_text(json.dumps(m))
        (d/'quality.json').write_text('{}')
        (d/'inputs').mkdir()
        (d/'inputs/config.gin').write_text('synthetic gin snapshot')
        (d/'episode.json').write_text(json.dumps(dict(status='SUCCEEDED_SMOKE',scenario='building_train_1/fairbanks_1',split='train',source_sha='a'*40,
                                                     expected_steps=288,steps_completed=288,input_hashes={'config.gin':hashlib.sha256((d/'inputs/config.gin').read_bytes()).hexdigest()})))
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        r=dict(status='SUCCEEDED_SMOKE',source_sha='a'*40,steps_per_episode=288,plan_sha256=sha(root/'dataset_manifest.yaml'),
               selected_scenarios=['building_train_1/fairbanks_1'],root_files={name:sha(root/name) for name in ['dataset_manifest.yaml','benchmark_manifest.yaml','schema.json','tracked_changes.patch','changed_files.zip']},
               episodes=[dict(scenario='building_train_1/fairbanks_1',directory=d.name,status='SUCCEEDED_SMOKE',files={name:sha(d/name) for name in ['arrays.npz','metadata.json','quality.json','episode.json']})])
        (root/'dataset.json').write_text(json.dumps(r))
        return r

    def test_missing_checksums_are_not_accepted_as_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r=self.make_corpus(root)
            self.assertEqual(validate_corpus(root,False)['total_transitions'],288)
            r['episodes'][0]['files']={}
            (root/'dataset.json').write_text(json.dumps(r))
            with self.assertRaises(DatasetError):validate_corpus(root,False)

    def test_modified_schema_snapshot_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);self.make_corpus(root)
            (root/'schema.json').write_text('{}')
            with self.assertRaises(DatasetError):validate_corpus(root,False)

    def test_snapshot_partial_directory_and_duplicate_selection_are_rejected(self):
        for mutation in ['input_missing','extra_partial','duplicate_selected','wrong_receipt_scenario','wrong_receipt_steps','wrong_receipt_source','wrong_dt']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);r=self.make_corpus(root);d=root/'episodes/building_train_1__fairbanks_1'
                if mutation=='input_missing':(d/'inputs/config.gin').unlink()
                elif mutation=='extra_partial':(root/'episodes/extra_partial').mkdir()
                elif mutation=='duplicate_selected':r['selected_scenarios']*=2
                elif mutation=='wrong_dt':
                    p=d/'metadata.json';m=json.loads(p.read_text());m['dt_seconds']=600;p.write_text(json.dumps(m))
                    r['episodes'][0]['files']['metadata.json']=hashlib.sha256(p.read_bytes()).hexdigest()
                    with np.load(d/'arrays.npz',allow_pickle=False) as data:arrays=dict(data)
                    t=datetime.fromisoformat(str(arrays['timestamps'][0]))
                    arrays['timestamps']=np.array([(t+timedelta(seconds=600*i)).isoformat() for i in range(289)],dtype='U40')
                    np.savez_compressed(d/'arrays.npz',**arrays)
                    r['episodes'][0]['files']['arrays.npz']=hashlib.sha256((d/'arrays.npz').read_bytes()).hexdigest()
                else:
                    p=d/'episode.json';e=json.loads(p.read_text())
                    if mutation=='wrong_receipt_scenario':e['scenario']='wrong/scenario'
                    elif mutation=='wrong_receipt_steps':e['steps_completed']=0
                    else:e['source_sha']='b'*40
                    p.write_text(json.dumps(e));r['episodes'][0]['files']['episode.json']=hashlib.sha256(p.read_bytes()).hexdigest()
                (root/'dataset.json').write_text(json.dumps(r))
                with self.assertRaises(DatasetError):validate_corpus(root,False)
