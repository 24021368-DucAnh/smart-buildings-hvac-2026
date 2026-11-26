"""Create portable B evidence exports, preserving raw originals outside Git.

AI-assisted Member B tooling; source/AI/time policy: team/PROJECT_KNOWLEDGE.md.
This edits public copies only and never upgrades evidence/status or changes scores.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,hashlib,io,json,re

DRIVE=re.compile(r'(?i)(?<![a-z0-9_])[a-z]:[\\/]')
FILES=['team/B03_checks.json','team/B04_checks.json','team/benchmark_checks.json','team/data_audit_checks.json',
       'experiments/registry.csv','experiments/datasets.csv','experiments/forecasts.csv']


def sanitize(value,roots):
    if isinstance(value,str):
        normalized=value.replace('\\','/')
        result=normalized
        changed=False
        for root in sorted(roots,key=len,reverse=True):
            result,count=re.subn(re.escape(str(root).replace('\\','/').rstrip('/')),'.',result,flags=re.I)
            changed=changed or bool(count)
        if DRIVE.search(result) or result.startswith(('//','/Users/','/home/')):
            for marker in ('/artifacts/','/data/generated/','/configs/','/team/','/.venv/'):
                if marker in result:return '.'+result[result.index(marker):]
            return '[local-path-redacted]'
        return result if changed else value
    if isinstance(value,list):return [sanitize(v,roots) for v in value]
    if isinstance(value,dict):
        out={}
        for key,item in value.items():
            canonical=sanitize(key,roots)
            if canonical in out:raise ValueError('ambiguous public path key')
            out[canonical]=sanitize(item,roots)
        return out
    return value


def export(root,output,aliases,apply=False):
    output.mkdir(parents=True,exist_ok=False);records=[]
    for name in FILES:
        source=root/name
        if not source.exists():continue
        raw=source.read_bytes();backup=output/'originals'/name;backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(raw)
        if source.suffix=='.json':
            value=sanitize(json.loads(raw.decode('utf-8')),aliases)
            value['public_export_note']='Path fields normalized/redacted; numbers, status, timestamps and original hash values preserved. Raw originals stay local.'
            public=(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')
        else:
            reader=csv.DictReader(io.StringIO(raw.decode('utf-8')));fields=reader.fieldnames
            rows=[{k:sanitize(v,aliases) for k,v in r.items()} for r in reader]
            stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows);public=stream.getvalue().encode('utf-8')
        if DRIVE.search(public.decode('utf-8')):raise ValueError('unremoved machine path in public export: '+name)
        dest=output/'public'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(public)
        if apply:source.write_bytes(public)
        records.append(dict(path=name,original_sha256=hashlib.sha256(raw).hexdigest(),public_sha256=hashlib.sha256(public).hexdigest()))
    receipt=dict(utc=datetime.now(timezone.utc).isoformat(),applied=apply,files=records)
    (output/'export_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--root-alias',action='append',default=[]);p.add_argument('--apply',action='store_true');a=p.parse_args()
    root=Path(__file__).resolve().parents[1]
    result=export(root,a.output,[root.as_posix(),*a.root_alias],a.apply)
    print(json.dumps(dict(files=len(result['files']),applied=a.apply,receipt=str(a.output/'export_receipt.json'))))

if __name__=='__main__':main()
