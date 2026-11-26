"""The released notebook is a frozen code artifact, not a leaderboard claim."""
import hashlib,json,math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ID='20261126-a-stage1-e2c9ae5'


def test_checkpoint_notebook_source_and_release_hashes():
    folder=ROOT/'team/submission/checkpoints'
    release=json.loads((folder/(ID+'.json')).read_text(encoding='utf-8'))
    raw=(ROOT/release['notebook_path']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==release['notebook_sha256']
    notebook=json.loads(raw.decode('utf-8'))
    provenance=notebook['metadata']['project_provenance']
    assert provenance['candidate_policy_ref']==release['policy_ref']=='e2c9ae5ae73917d55e37964726393e22ceb8e040'
    assert notebook['metadata']['kaggle']['isInternetEnabled'] is False
    code=[c for c in notebook['cells'] if c['cell_type']=='code']
    records=provenance['sources']
    assert len(code[1:-2])==len(records)==4
    for record,cell in zip(records,code[1:-2]):
        embedded=''.join(cell['source'])
        assert hashlib.sha256(embedded.encode()).hexdigest()==record['embedded_sha256']
        reconstructed=embedded
        for removed in record['removed_imports']:
            reconstructed=reconstructed.replace('# Notebook: dependency class is defined in the preceding cell.',removed,1)
        assert hashlib.sha256(reconstructed.encode()).hexdigest()==record['original_sha256']
    compile('\n'.join(''.join(c['source']) for c in code),'checkpoint-notebook','exec')


def test_checkpoint_scores_are_explicit_diagnostics_not_kaggle():
    release=json.loads((ROOT/'team/submission/checkpoints'/(ID+'.json')).read_text(encoding='utf-8'))
    assert release['kaggle_public_score'] is None
    assert release['G1']=='NOT APPROVED'
    rows=release['independently_verified_full_cases']
    assert len(rows)==release['full_case_count']
    assert len({r['scenario'] for r in rows})==len(rows)
    for row in rows:
        assert row['total_steps']==8640 and math.isfinite(row['total_reward'])
        assert math.isclose(row['loss'],abs(row['total_reward']/8640),rel_tol=1e-12)
    if release['recommendation']=='PROVISIONAL_NEXT_SUBMISSION_CANDIDATE':
        assert len(rows)==2 and all(r['loss']<=r['old_a_loss'] for r in rows)
        assert any(r['loss']<r['old_a_loss'] for r in rows)
