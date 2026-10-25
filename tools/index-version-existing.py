"""Distinguish configured initial version from an already-existing index."""
import json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent;G=os.environ['DEN_GIT'];base=R/'target/index-version-existing'
if base.exists():shutil.rmtree(base)
base.mkdir();rows=[]
for initial,configured in ((2,4),(4,2),(4,3)):
 repo=base/f'{initial}-{configured}';repo.mkdir()
 def git(*args):
  p=subprocess.run([G,*args],cwd=repo,capture_output=True);assert p.returncode==0,p.stderr
 subprocess.run([G,'init','-q'],cwd=repo,check=True)
 (repo/'file').write_bytes(b'one\n');git('-c',f'index.version={initial}','add','file')
 before=(repo/'.git/index').read_bytes()
 (repo/'file').write_bytes(b'two\n');git('-c',f'index.version={configured}','add','file')
 after=(repo/'.git/index').read_bytes();row=dict(initial=initial,configured=configured,before=int.from_bytes(before[4:8],'big'),after=int.from_bytes(after[4:8],'big'))
 rows.append(row);print(row)
(R/'target/index-version-existing.json').write_text(json.dumps(rows,indent=2)+'\n')
