"""Resume tests use synthetic temporary episodes, never simulator scores."""
from copy import deepcopy
from datetime import datetime,timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import numpy as np

import test_dataset as fixtures
from team_tools.dataset import DatasetError,TransitionBuffer,ROOT_FILES,verify_reuse_source,resolve_episode_pin,digest,validate_corpus
import team_tools.collect_transitions as collector

GIN="weather_csv_path = 'smart_buildings/weather/csv/fairbanks.csv'\nfloor_plan_filepath = 'smart_buildings/training_scenarios/building_train_1/fairbanks_1/floor_plan.npy'\nzone_map_filepath = 'smart_buildings/training_scenarios/building_train_1/fairbanks_1/zone_map.npy'\n"
NUMERIC={'smart_buildings/physics.py':'1'*64,'smart_buildings/weather/csv/fairbanks.csv':'2'*64,
 'smart_buildings/training_scenarios/building_train_1/fairbanks_1/config.gin':hashlib.sha256(GIN.encode()).hexdigest()}
NUMERIC.update({f'smart_buildings/training_scenarios/building_train_1/fairbanks_1/{name}':'3'*64 for name in ('floor_plan.npy','zone_map.npy')})
def numeric_pin():return {'files':dict(NUMERIC)}


def make_full_source(root):
    r=fixtures.CorpusIntegrityTests().make_corpus(root)
    d=root/'episodes/building_train_1__fairbanks_1'
    m=fixtures.metadata();m.update(expected_steps=8640,scenario='building_train_1/fairbanks_1',suite='dev_small',building='building_train_1',weather='fairbanks_1',split='train',policy='pid_water',horizon_steps=1)
    t=datetime(2023,1,1);b=TransitionBuffer(m,np.array([-.2,0,0],np.float32),t.isoformat())
    action=dict(continuous_action=np.zeros(2,np.float32),discrete_action=np.ones(1,np.int32))
    for i in range(1,8641):b.append(action,np.array([0,0,0],np.float32),(t+timedelta(seconds=300*i)).isoformat(),-1.,False,False)
    np.savez_compressed(d/'arrays.npz',**b.arrays());(d/'metadata.json').write_text(json.dumps(m))
    (d/'inputs/config.gin').write_text(GIN)
    e=json.loads((d/'episode.json').read_text());e.update(status='SUCCEEDED_FULL',expected_steps=8640,steps_completed=8640,process_cpu_s=1.)
    e['input_hashes']['config.gin']=digest(d/'inputs/config.gin')
    (d/'episode.json').write_text(json.dumps(e))
    r.update(status='PAUSED_BY_USER',dataset_id='synthetic-paused',steps_per_episode=8640)
    r['episodes'][0]['status']='SUCCEEDED_FULL'
    r['episodes'][0]['files']={name:digest(d/name) for name in r['episodes'][0]['files']}
    with zipfile.ZipFile(root/'changed_files.zip','w') as z:z.writestr('team_tools/collect_transitions.py','synthetic producer')
    r['root_files']={name:digest(root/name) for name in ROOT_FILES}
    (root/'dataset.json').write_text(json.dumps(r))
    audit=dict(source_archive_sha256=digest(root/'changed_files.zip'),runtime_source_sha256={'team_tools/collect_transitions.py':hashlib.sha256(b'synthetic producer').hexdigest()},
               completed_episodes=[dict(scenario=r['episodes'][0]['scenario'],files=r['episodes'][0]['files'],input_hashes=e['input_hashes'])])
    audit['numeric_inputs_sha256']=dict(NUMERIC)
    path=root/'manual_audit.json';path.write_text(json.dumps(audit))
    return r,path


class ReuseTests(unittest.TestCase):
    def test_same_head_reuse_rejects_numerical_input_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r,audit=make_full_source(root)
            for key in NUMERIC:
                pin=numeric_pin();pin['files'][key]='f'*64
                with self.subTest(key=key),self.assertRaises(DatasetError):
                    verify_reuse_source(root,root/'dataset_manifest.yaml','a'*40,audit,current_numeric_pin=pin)
            selected=verify_reuse_source(root,root/'dataset_manifest.yaml','a'*40,audit,current_numeric_pin=numeric_pin())
            self.assertEqual(len(selected),1)
    def test_generated_windows_paths_are_staged_without_changing_original_or_physics(self):
        import gin
        from team_tools.dataset import portable_gin_config
        original='weather_csv_path = "smart_buildings\\weather\\csv\\atlanta.csv"\nfloor_plan_filepath = "data\\generated\\building_0500\\floor_plan.npy"\ninitial_temp = 294.0\nlabel = "building_0500/atlanta_4"\n'
        converted,fields=portable_gin_config(original)
        self.assertEqual(set(fields),{'weather_csv_path','floor_plan_filepath'})
        self.assertIn('initial_temp = 294.0',converted)
        self.assertIn('label = "building_0500/atlanta_4"',converted)
        gin.clear_config()
        try:
            gin.parse_config(converted)
            self.assertEqual(gin.query_parameter('%floor_plan_filepath'),'data/generated/building_0500/floor_plan.npy')
            self.assertEqual(gin.query_parameter('%weather_csv_path'),'smart_buildings/weather/csv/atlanta.csv')
        finally:gin.clear_config()
        with tempfile.TemporaryDirectory() as temp:
            d=Path(temp);source=d/'config.gin';source.write_text(original)
            snap=d/'inputs';snap.mkdir()
            path,record=collector.stage_runtime_config(source,snap)
            self.assertEqual(source.read_text(),original)
            self.assertEqual(path.read_text(),converted)
            self.assertEqual(record['effective_sha256'],digest(path))
        self.assertEqual(portable_gin_config(converted),(converted,[]))

    def test_runtime_config_cannot_change_physics_even_with_updated_checksums(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r=fixtures.CorpusIntegrityTests().make_corpus(root)
            item=r['episodes'][0];d=root/'episodes'/item['directory'];snap=d/'inputs'
            original=snap/'config.gin';original.write_text('floor_plan_filepath = "data\\building\\floor_plan.npy"\ninitial_temp = 294.0\n')
            effective,record=collector.stage_runtime_config(original,snap)
            e=json.loads((d/'episode.json').read_text());e.update(runtime_config=record,input_hashes={'config.gin':digest(original),'effective_config.gin':digest(effective)})
            def save():
                (d/'episode.json').write_text(json.dumps(e));item['files']['episode.json']=digest(d/'episode.json')
                (root/'dataset.json').write_text(json.dumps(r))
            save();validate_corpus(root,False)
            effective.write_text(effective.read_text().replace('294.0','295.0'))
            e['runtime_config']['effective_sha256']=digest(effective);e['input_hashes']['effective_config.gin']=digest(effective)
            save()
            with self.assertRaises(DatasetError):validate_corpus(root,False)

    def test_reuse_rejects_a_different_benchmark_manifest_even_if_root_hashes_are_updated(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r,audit=make_full_source(root)
            bench=root/'benchmark_manifest.yaml';bench.write_bytes(bench.read_bytes()+b'\n# changed suite inputs\n')
            r['root_files']['benchmark_manifest.yaml']=digest(bench)
            (root/'dataset.json').write_text(json.dumps(r))
            with self.assertRaises(DatasetError):verify_reuse_source(root,root/'dataset_manifest.yaml','a'*40,audit)

    def test_only_verified_full_episodes_are_selected_from_a_paused_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r,audit=make_full_source(root)
            r['episodes'].append(dict(scenario='building_train_5/atlanta_6',directory='partial',status='PAUSED_BY_USER',files={}))
            (root/'dataset.json').write_text(json.dumps(r))
            selected=verify_reuse_source(root,root/'dataset_manifest.yaml','a'*40,audit)
            self.assertEqual(set(selected),{'building_train_1/fairbanks_1'})

    def test_source_schema_plan_hashes_and_manual_audit_are_required(self):
        for fault in ['wrong_sha','wrong_plan','corrupt_data','missing_input','missing_audit','wrong_audit']:
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);r,audit=make_full_source(root);d=root/'episodes/building_train_1__fairbanks_1'
                expected='b'*40 if fault=='wrong_sha' else 'a'*40
                plan=root/'dataset_manifest.yaml'
                if fault=='wrong_plan':plan=root/'other.yaml';plan.write_bytes((root/'dataset_manifest.yaml').read_bytes()+b'\n')
                elif fault=='corrupt_data':(d/'arrays.npz').write_bytes(b'bad')
                elif fault=='missing_input':(d/'inputs/config.gin').unlink()
                elif fault=='missing_audit':audit=None
                elif fault=='wrong_audit':audit.write_text('{}')
                with self.assertRaises(DatasetError):verify_reuse_source(root,plan,expected,audit)

    def test_import_preserves_original_bytes_and_retains_producer_lineage(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);source=base/'old';source.mkdir();r,audit=make_full_source(source)
            dest=base/'new';dest.mkdir();(dest/'episodes').mkdir()
            before=(source/'dataset.json').read_bytes()
            items,lineage=collector.import_reusable_episodes(source,dest,source/'dataset_manifest.yaml','a'*40,audit,current_numeric_pin=numeric_pin())
            key='building_train_1/fairbanks_1';item=items[key]
            copied=dest/'episodes'/item['directory']
            self.assertEqual((source/'episodes'/item['directory']/'arrays.npz').read_bytes(),(copied/'arrays.npz').read_bytes())
            self.assertEqual((source/'dataset.json').read_bytes(),before)
            self.assertEqual(json.loads((copied/'episode.json').read_text())['status'],'SUCCEEDED_FULL')
            header=dict(source_sha='a'*40,plan_sha256=r['plan_sha256'],lineage=lineage)
            self.assertIsNone(resolve_episode_pin(dest,item,header))
            capsule=dest/lineage[item['reuse_origin']]['directory']
            (capsule/'dataset.json').write_text('{}')
            with self.assertRaises(DatasetError):resolve_episode_pin(dest,item,header)

    def test_reusing_smoke_as_full_collection_is_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            args=collector.parser().parse_args(['--steps','288','--reuse-from',str(root),'--output-root',str(root/'new')])
            with self.assertRaises(DatasetError):collector.run_collection(args)
            self.assertFalse((root/'new').exists())

    def test_guarded_reuse_uses_original_worker_pin_and_checks_both_boundaries(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);source=base/'old';source.mkdir();r,_=make_full_source(source)
            pin=source/'source_pin.json';pin.write_text(json.dumps(numeric_pin()))
            r['producer_guard']='scoped_sha256_v1';r['root_files']['source_pin.json']=digest(pin)
            item=r['episodes'][0];e_path=source/'episodes'/item['directory']/'episode.json'
            e=json.loads(e_path.read_text());e.update(producer_pin_sha256=digest(pin),producer_guard='PASS_BEFORE_AND_AFTER')
            e_path.write_text(json.dumps(e));item['files']['episode.json']=digest(e_path)
            (source/'dataset.json').write_text(json.dumps(r))
            dest=base/'new';dest.mkdir();(dest/'episodes').mkdir()
            items,lineage=collector.import_reusable_episodes(source,dest,source/'dataset_manifest.yaml','a'*40,current_numeric_pin=numeric_pin())
            copied=items[item['scenario']]
            h=dict(source_sha='a'*40,plan_sha256=r['plan_sha256'],lineage=lineage)
            self.assertEqual(resolve_episode_pin(dest,copied,h),digest(pin))
            # Even matching checksums cannot turn a before-only worker into a verified one.
            e['producer_guard']='PASS_BEFORE';e_path.write_text(json.dumps(e));item['files']['episode.json']=digest(e_path)
            (source/'dataset.json').write_text(json.dumps(r))
            with self.assertRaises(DatasetError):verify_reuse_source(source,source/'dataset_manifest.yaml','a'*40)

    def test_repeated_pause_and_reuse_retains_legacy_audit_chain(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);source=base/'old';source.mkdir();r,audit=make_full_source(source)
            dest=base/'new';dest.mkdir();(dest/'episodes').mkdir()
            items,lineage=collector.import_reusable_episodes(source,dest,source/'dataset_manifest.yaml','a'*40,audit,current_numeric_pin=numeric_pin())
            import shutil
            for name in ROOT_FILES:shutil.copy2(source/name,dest/name)
            r.update(episodes=list(items.values()),lineage=lineage)
            (dest/'dataset.json').write_text(json.dumps(r))
            newer=base/'newer';newer.mkdir();(newer/'episodes').mkdir()
            items2,lineage2=collector.import_reusable_episodes(dest,newer,dest/'dataset_manifest.yaml','a'*40,current_numeric_pin=numeric_pin())
            h=dict(source_sha='a'*40,plan_sha256=r['plan_sha256'],lineage=lineage2)
            self.assertIsNone(resolve_episode_pin(newer,next(iter(items2.values())),h))
