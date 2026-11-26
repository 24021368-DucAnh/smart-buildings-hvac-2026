from pathlib import Path
from types import SimpleNamespace
import contextlib
import csv
import io
import json
import hashlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import team_tools.collect_transitions as collector
from team_tools.dataset import DatasetError


class CollectorTests(unittest.TestCase):
    def test_package_pin_tolerates_duplicate_import_paths_but_not_changed_versions(self):
        distribution=SimpleNamespace(metadata={'Name':'example'},version='1.0')
        pin={'files':{},'packages':['example==1.0']}
        with patch.object(collector.importlib.metadata,'distributions',return_value=[distribution,distribution]):
            collector.verify_source_pin(pin,Path.cwd())
        distribution.version='2.0'
        with patch.object(collector.importlib.metadata,'distributions',return_value=[distribution]),self.assertRaises(DatasetError):
            collector.verify_source_pin(pin,Path.cwd())

    def test_producer_pin_rejects_runtime_source_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/'source.py';p.write_bytes(b'original')
            pin={'files':{'source.py':hashlib.sha256(b'original').hexdigest()}}
            collector.verify_source_pin(pin,root)
            p.write_bytes(b'changed')
            with self.assertRaises(DatasetError):collector.verify_source_pin(pin,root)

    def test_timeout_finalizes_an_existing_running_worker_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            args=collector.parser().parse_args(['--dataset-id','interrupted','--output-root',str(root),'--steps','288','--scenario','building_train_1/fairbanks_1'])
            original=subprocess.run
            def timeout(command,**kwargs):
                if '--worker' not in command:return original(command,**kwargs)
                d=Path(command[command.index('--worker')+1]);d.mkdir()
                (d/'episode.json').write_text(json.dumps(dict(status='RUNNING',steps_completed=0)))
                (d/'progress.json').write_text(json.dumps(dict(steps=120)))
                raise subprocess.TimeoutExpired(command,1,output=b'partial',stderr=b'timeout')
            with patch.object(collector,'REGISTRY',root/'registry.csv'),patch.object(collector.subprocess,'run',side_effect=timeout),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(collector.run_collection(args),1)
            child=json.loads((root/'interrupted/episodes/building_train_1__fairbanks_1/episode.json').read_text())
            self.assertEqual(child['status'],'TIMED_OUT')
            self.assertEqual(child['last_reported_steps'],120)
    def test_launch_failure_does_not_leave_a_running_episode(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            args=collector.parser().parse_args(['--dataset-id','launch-error','--output-root',str(root),'--steps','288','--scenario','building_train_1/fairbanks_1'])
            original=subprocess.run
            def fail(command,**kwargs):
                if '--worker' in command:raise OSError('synthetic launch error')
                return original(command,**kwargs)
            with patch.object(collector,'REGISTRY',root/'registry.csv'),patch.object(collector.subprocess,'run',side_effect=fail),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(collector.run_collection(args),1)
            r=json.loads((root/'launch-error/dataset.json').read_text())
            self.assertEqual(r['status'],'FAILED')
            self.assertEqual(r['episodes'][0]['status'],'FAILED')

    def test_raw_validity_is_captured_before_environment_carry_forward(self):
        request=SimpleNamespace(device_id='VAV_1',measurement_name='zone_air_temperature_sensor')
        value=SimpleNamespace(single_observation_request=request,observation_valid=False,continuous_value=0.)
        response=SimpleNamespace(single_observation_responses=[value])
        audit=collector.ObservationAudit(lambda request:response,{('VAV_1','zone_air_temperature_sensor'):0},2)
        returned=audit(None)
        self.assertIs(returned,response)
        self.assertFalse(returned.single_observation_responses[0].observation_valid)
        np.testing.assert_array_equal(audit.valid,[False,True])
        self.assertEqual(audit.calls,1)

    def test_existing_dataset_id_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'existing').mkdir()
            keep=root/'existing/keep.txt';keep.write_text('keep')
            args=collector.parser().parse_args(['--dataset-id','existing','--output-root',str(root),'--steps','288','--scenario','building_train_1/fairbanks_1'])
            with self.assertRaises(DatasetError):collector.run_collection(args)
            self.assertEqual(keep.read_text(),'keep')

    def test_timeout_leaves_terminal_status_and_no_trainable_dataset(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            args=collector.parser().parse_args(['--dataset-id','timeout','--output-root',str(root),'--steps','288','--scenario','building_train_1/fairbanks_1'])
            original=subprocess.run
            def timeout(command,**kwargs):
                if '--worker' in command:
                    raise subprocess.TimeoutExpired(command,1,output=b'partial',stderr=b'timeout')
                return original(command,**kwargs)
            with patch.object(collector,'REGISTRY',root/'registry.csv'),patch.object(collector.subprocess,'run',side_effect=timeout),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(collector.run_collection(args),1)
            r=json.loads((root/'timeout/dataset.json').read_text())
            self.assertEqual(r['status'],'TIMED_OUT')
            self.assertEqual(r['episodes'][0]['status'],'TIMED_OUT')
            self.assertFalse(r['training_ready'])
            with (root/'registry.csv').open(encoding='utf-8') as stream:
                self.assertEqual(next(csv.DictReader(stream))['status'],'TIMED_OUT')


if __name__=='__main__':unittest.main()
