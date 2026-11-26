import json,re
from pathlib import Path
import pytest
from team_tools.public_evidence import sanitize


def test_export_preserves_sources_numbers_and_dates():
    raw=dict(source='https://github.com/smart-buildings-2026/starter-kit',loss=.25,
             utc='2026-11-26T01:00:00+00:00',status='FAILED',path=r'C:\private\project\artifacts\run')
    result=sanitize(raw,['C:/private/project'])
    assert result['source']==raw['source'] and result['loss']==.25 and result['utc']==raw['utc'] and result['status']=='FAILED'
    assert result['path']=='./artifacts/run'
    assert raw['path'].startswith('C:')


def test_unknown_machine_path_redacted_and_logical_artifacts_kept():
    assert sanitize(r'C:\Users\Someone\Python\python.exe',[])=='[local-path-redacted]'
    assert sanitize(r'D:\other\project\data\generated\episode',[])=='./data/generated/episode'
    assert sanitize('shape (T+1,D); native = z * std + mean',[])=='shape (T+1,D); native = z * std + mean'
    assert sanitize(r'\\private-server\share\internal',[])=='[local-path-redacted]'
    assert sanitize('/home/member/private/file',[])=='[local-path-redacted]'


def test_ambiguous_export_keys_fail():
    with pytest.raises(ValueError):sanitize({'C:/one/artifacts/x':1,'C:/two/artifacts/x':2},['C:/one','C:/two'])
