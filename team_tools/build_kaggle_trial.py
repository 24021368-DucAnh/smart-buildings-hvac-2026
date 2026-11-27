"""Build self-contained trial notebooks from pinned, attributed policy sources.

AI-assisted packaging only; no simulator changes, uploads or Kaggle submission.
Official notebook: https://www.kaggle.com/code/ayushrai1114/transferpolicy-notebook
"""
from pathlib import Path
import argparse, hashlib, json, re, subprocess, zipfile

ROOT=Path(__file__).resolve().parents[1]
UPSTREAM='1fb75606d12e016463fbc63de704967c5b2bf9d5'
BOOTSTRAP='''import sys
from pathlib import Path
import numpy as np

COMPETITION_DATA_FOLDER = '/kaggle/input/competitions/neurips-2026-smart-buildings/'
data_root = Path(COMPETITION_DATA_FOLDER)
if not (data_root / 'kaggle_evaluation').is_dir():
    raise FileNotFoundError('Attach the official Smart Buildings competition data in Input first.')
sys.path.insert(0, str(data_root))
sys.path.insert(0, str(data_root / 'kaggle_evaluation'))
from kaggle_evaluation import smart_buildings_inference_server
'''
SERVER='''smart_buildings_inference_server.SmartBuildingsInferenceServer(TransferPolicy).run(
    competition_data_folder=COMPETITION_DATA_FOLDER,
)
'''


def adapter_source(mode):
    if mode not in ('safe','candidate_a'):raise ValueError('unknown trial mode')
    engine='PIDWaterResetPolicy' if mode=='safe' else 'MemberAPolicy'
    return f'''class TransferPolicy(smart_buildings_inference_server.Policy):
    """Kaggle handshake adapter; control logic is the attributed {engine}."""
    def __init__(self, building_meta_data, action_spec):
        super().__init__(building_meta_data, action_spec)
        self.spec = action_spec
        self.engine = {engine}(building_meta_data, action_spec)

    def get_action(self, obs):
        action = self.engine.get_action(np.asarray(obs).copy())
        output = {{}}
        for key, dtype in [('continuous_action', np.float32), ('discrete_action', np.int32)]:
            value = np.asarray(action[key])
            spec = self.spec[key]
            if value.shape != spec.shape or not np.isfinite(value).all():
                raise ValueError('Invalid action shape/nonfinite: ' + key)
            if np.any(value < spec.low) or np.any(value > spec.high):
                raise ValueError('Action out of bounds: ' + key)
            if key == 'discrete_action' and not np.isin(value, [0, 1]).all():
                raise ValueError('Non-binary discrete action')
            output[key] = value.astype(dtype, copy=True)
        return output
'''


def resolve_commit(value):
    if not re.fullmatch('[0-9a-f]{40}',value):raise ValueError('policy ref must be a full commit SHA')
    try:
        kind=subprocess.check_output(['git','cat-file','-t',value],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError as error:raise ValueError('policy commit is unavailable locally; fetch it first') from error
    if kind!='commit':raise ValueError('policy ref must identify a commit')
    return value


def policy_sources(mode,policy_ref=None):
    if mode not in ('safe','candidate_a'):raise ValueError('unknown policy mode')
    if policy_ref is not None:resolve_commit(policy_ref)
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    names=['smart_buildings/baselines/pid.py','smart_buildings/baselines/pid_plus.py']
    removals={'smart_buildings/baselines/pid_plus.py':['from smart_buildings.baselines.pid import PIDPolicy']}
    if mode=='candidate_a':
        names+=['team/policy/zone_controller.py','team/policy/member_a_policy.py']
        removals[names[-1]]=['from smart_buildings.baselines.pid_plus  import PIDWaterResetPolicy','from team.policy.zone_controller import ZoneController']
    sources=[];records=[]
    for name in names:
        source_commit=(policy_ref if name.startswith('team/policy/') else head) if policy_ref else None
        raw=subprocess.check_output(['git','show',source_commit+':'+name],cwd=ROOT) if source_commit else (ROOT/name).read_bytes()
        source=raw.decode('utf-8')
        for line in removals.get(name,[]):
            if source.count(line)!=1:raise ValueError('source import changed: '+name)
            source=source.replace(line,'# Notebook: dependency class is defined in the preceding cell.')
        sources.append(source)
        records.append(dict(path=name,source_commit=source_commit,original_sha256=hashlib.sha256(raw).hexdigest(),
            embedded_sha256=hashlib.sha256(source.encode()).hexdigest(),removed_imports=removals.get(name,[])))
    return sources,records


def checkpoint_engine(policy_ref):
    """Load the same pinned policy definitions embedded in the checkpoint notebook."""
    sources,_=policy_sources('candidate_a',policy_ref)
    namespace={'__name__':'checkpoint_policy'}
    for index,source in enumerate(sources):exec(compile(source,'checkpoint-source-'+str(index),'exec'),namespace)
    return namespace['MemberAPolicy']


def cell(kind,source,index):
    result=dict(cell_type=kind,id=f'trial-{index}',metadata={},source=source.splitlines(True))
    if kind=='code':result.update(execution_count=None,outputs=[])
    return result


def build(output,policy_ref=None):
    if policy_ref is not None:resolve_commit(policy_ref)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    manifest=dict(status='PREPARED_NOT_KAGGLE_VERIFIED',source_sha=sha,official_upstream_sha=UPSTREAM,
        candidate_policy_ref=policy_ref,source_selection='Pinned Git blobs for checkpoint; working files otherwise',
        source_sha_scope='Git HEAD base; individual original/embedded hashes bind policy bytes, builder hash binds packaging code.',
        working_tree_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT).strip()),
        official_template='https://www.kaggle.com/code/ayushrai1114/transferpolicy-notebook',
        template_version_observed=1,ai_assistance='Codex/ChatGPT packaging, tests and guide; policies attributed separately.',
        template_download_sha256='786545a08be78ce7e9f60110297fc345a91fe1a39c8eedd4058b5444913629c5',
        builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        source_repository='https://github.com/24021368-DucAnh/smart-buildings-hvac-2026',
        human_hours=None,kaggle_score=None,notebooks=[],policies={})
    for mode in ('safe','candidate_a'):
        sources,records=policy_sources(mode,policy_ref)
        explanation=f'''# Smart Buildings trial — {mode}

Prepared 26/11/2026. Status: NOT RUN ON KAGGLE; no score claimed.
Safe = official PIDWaterResetPolicy, provisional workflow baseline.
Candidate A = team MemberAPolicy at source {policy_ref or sha}, G1 NOT APPROVED.
No Ridge/B05/B06, fitting, downloads, hidden data or local filesystem dependency.

Sources: official starter kit https://github.com/smart-buildings-2026/starter-kit
at {UPSTREAM} (Apache-2.0); group repository at {sha}.
Kaggle handshake/run adapted from Ayush Rai, TransferPolicy Notebook, version1,
https://www.kaggle.com/code/ayushrai1114/transferpolicy-notebook (Apache-2.0).
Policy source below is copied with only the listed import removals, because
the same dependency classes precede it. Numerical control logic is unchanged.
Substantial Codex/ChatGPT assistance: packaging/adapter/tests/guide. A code is
attributed to A; A's AI usage and human person-hours are not inferred.

Attach competition data, CPU, Internet OFF. Run All / Save Version (Save & Run All),
then submit the successful saved version from Kaggle. The final cell invokes the
official server; do not replace it with local evaluate.py or a fabricated CSV.
'''
        cells=[cell('markdown',explanation,0),cell('code',BOOTSTRAP,1)]
        for record,source in zip(records,sources):
            cells.append(cell('markdown','Source: `'+record['path']+'`; original SHA256 `'+record['original_sha256']+'`. Import adaptations: '+str(record['removed_imports']),len(cells)))
            cells.append(cell('code',source,len(cells)))
        cells += [cell('code',adapter_source(mode),len(cells)),cell('code',SERVER,len(cells)+1)]
        notebook=dict(nbformat=4,nbformat_minor=5,cells=cells,metadata=dict(
            kernelspec=dict(display_name='Python 3',language='python',name='python3'),
            language_info=dict(name='python'),
            kaggle=dict(accelerator='none',dataSources=[dict(sourceType='competition',sourceId=157303)],isInternetEnabled=False,language='python',sourceType='notebook',isGpuEnabled=False),
            project_provenance=dict(mode=mode,source_sha=sha,candidate_policy_ref=policy_ref,upstream_sha=UPSTREAM,sources=records,license='Apache-2.0',
                license_text=(ROOT/'LICENSE').read_text(),notice_text=(ROOT/'NOTICE').read_text())))
        name='smart-buildings-'+mode.replace('_','-')+'.ipynb'
        (output/name).write_text(json.dumps(notebook,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        manifest['notebooks'].append(name)
        manifest['policies'][mode]=dict(sources=records,notebook_sha256=hashlib.sha256((output/name).read_bytes()).hexdigest())
    for name in ('LICENSE','NOTICE'):(output/name).write_bytes((ROOT/name).read_bytes())
    guide=ROOT/'team/KAGGLE_TRIAL_GUIDE.md'
    if guide.exists():(output/guide.name).write_bytes(guide.read_bytes())
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    with zipfile.ZipFile(output/'kaggle-trial-bundle.zip','x',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            if path.suffix!='.zip':archive.write(path,path.name)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--policy-ref',help='Full immutable commit SHA for A sources, including unmerged checkpoint candidates')
    args=parser.parse_args()
    result=build(args.output,args.policy_ref)
    print(json.dumps(dict(output=str(args.output),status=result['status'],notebooks=result['notebooks']),indent=2))


if __name__=='__main__':main()
