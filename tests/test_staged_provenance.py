import subprocess
from unittest.mock import patch
from team_tools import run_batch as r


def test_staged_source_bytes_change_dirty_fingerprint(tmp_path):
    def git(*args):subprocess.run(['git',*args],cwd=tmp_path,check=True,capture_output=True)
    git('init','-q');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--allow-empty','-qm','synthetic fixture')
    source=tmp_path/'module.py';source.write_text('version one');git('add','module.py')
    with patch.object(r,'REPO_ROOT',tmp_path):first=r.current_worktree_fingerprint()
    source.write_text('version two');git('add','module.py')
    with patch.object(r,'REPO_ROOT',tmp_path):second=r.current_worktree_fingerprint()
    assert first[0] and second[0]
    assert first[1]!=second[1]
