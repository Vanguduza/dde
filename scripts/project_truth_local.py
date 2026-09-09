#!/usr/bin/env python3
from __future__ import annotations
import argparse,datetime as dt,hashlib,json,os,pathlib,subprocess,sys
R=pathlib.Path(__file__).resolve().parents[1]; L=R/'docs/project-state/CHANGE_LEDGER.jsonl'; C=R/'docs/project-state/CURRENT_STATE.json'; X=[':(exclude)docs/project-state/CHANGE_LEDGER.jsonl',':(exclude)docs/project-state/CURRENT_STATE.json']
def g(*a,check=True,b=False): return subprocess.run(['git',*a],cwd=R,check=check,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=not b)
def o(*a): return g(*a).stdout.strip()
def par(s):
 c=g('rev-parse',s+'^1',check=False); return c.stdout.strip() if c.returncode==0 else None
def files_staged(): return [x for x in g('diff','--cached','--name-only','--no-renames','--','.',*X).stdout.splitlines() if x]
def dig_staged(): return hashlib.sha256(g('diff','--cached','--binary','--no-ext-diff','--no-renames','--','.',*X,b=True).stdout).hexdigest()
def cfiles(s):
 p=par(s); a=('diff','--name-only','--no-renames',p,s,'--','.',*X) if p else ('show','--pretty=','--name-only',s,'--','.',*X); return [x for x in g(*a).stdout.splitlines() if x]
def cdig(s):
 p=par(s); a=('diff','--binary','--no-ext-diff','--no-renames',p,s,'--','.',*X) if p else ('show','--binary','--format=','--no-ext-diff',s,'--','.',*X); return hashlib.sha256(g(*a,b=True).stdout).hexdigest()
def rows_at(s):
 c=g('show',f'{s}:docs/project-state/CHANGE_LEDGER.jsonl',check=False); r=[]
 if c.returncode==0:
  for q in c.stdout.splitlines():
   try:r.append(json.loads(q))
   except:pass
 return r
def record():
 f=files_staged()
 if not f:return 0
 d=dig_staged(); p=o('rev-parse','HEAD'); rows=[]
 if L.exists():
  for q in L.read_text().splitlines():
   try:rows.append(json.loads(q))
   except:pass
 if not(rows and rows[-1].get('source_parent')==p and rows[-1].get('diff_sha256')==d):
  e={'schema_version':1,'kind':'precommit-staged-diff','recorded_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'branch':o('rev-parse','--abbrev-ref','HEAD'),'source_parent':p,'changed_files':f,'diff_sha256':d,'actor':os.getenv('USER') or os.getenv('USERNAME') or 'unknown'}; L.parent.mkdir(parents=True,exist_ok=True)
  with L.open('a') as z:z.write(json.dumps(e,sort_keys=True,separators=(',',':'))+'\n')
  C.write_text(json.dumps({'schema_version':1,'state':'PENDING_COMMIT',**e},indent=2,sort_keys=True)+'\n')
 subprocess.run(['git','add','docs/project-state/CHANGE_LEDGER.jsonl','docs/project-state/CURRENT_STATE.json'],cwd=R,check=True); return 0
def install():
 c=g('log','--reverse','--format=%H','--diff-filter=A','--','scripts/project_truth_local.py',check=False); a=[x for x in c.stdout.splitlines() if x]; return a[0] if a else None
def verify():
 b=install()
 if not b: print('BLOCKED: Project Truth local guard baseline missing',file=sys.stderr); return 40
 bad=[]
 for s in [x for x in o('rev-list','--reverse',f'{b}..HEAD').splitlines() if x]:
  f=cfiles(s)
  if not f:continue
  p=par(s); d=cdig(s)
  if not any(r.get('source_parent')==p and r.get('diff_sha256')==d and sorted(r.get('changed_files',[]))==sorted(f) for r in rows_at(s)):bad.append(s)
 if bad: print('BLOCKED: unlogged post-guard commits: '+', '.join(bad),file=sys.stderr); return 41
 return 0
if __name__=='__main__':
 a=argparse.ArgumentParser(); a.add_argument('cmd',choices=['record','verify']); n=a.parse_args(); raise SystemExit(record() if n.cmd=='record' else verify())
