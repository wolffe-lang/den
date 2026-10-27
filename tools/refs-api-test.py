"""Independent importing ref client; no porcelain implementation dependency."""
import argparse,json,os,pathlib,runpy,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser();ap.add_argument('--tier',default='native');a=ap.parse_args()
G=os.environ['DEN_GIT']; C=str(R/f'target/{a.tier}/refs-client')
O=runpy.run_path(str(R/'tools/oracle.py'))
base=R/f'target/refs-api-{a.tier}'
if base.exists():shutil.rmtree(base)
base.mkdir(parents=True); seed=base/'seed';seed.mkdir()
def git(*args):
 p=subprocess.run([G,*args],cwd=seed,capture_output=True);assert p.returncode==0,(args,p.stderr);return p.stdout.decode().strip()
git('init','-q');(seed/'a').write_bytes(b'a\n');git('add','a');git('commit','-qm','one');one=git('rev-parse','HEAD')
(seed/'a').write_bytes(b'b\n');git('commit','-qam','two');two=git('rev-parse','HEAD')
git('branch','topic',one);git('tag','-am','tag','annotated',one);tag=git('rev-parse','annotated');git('pack-refs','--all')
rows=[]
for name,want in [('HEAD',two),('refs/heads/main',two),('refs/heads/topic',one),('refs/tags/annotated',tag)]:
 p=subprocess.run([C,'read',str(seed/'.git'),name],capture_output=True)
 assert (p.returncode,p.stdout,p.stderr)==(0,(want+'\n').encode(),b''),(name,p.stdout,p.stderr)
 rows.append({'read':name,'oid':want})
# One large packed namespace must be enumerated without reparsing the packed file per ref.
packed=seed/'.git/packed-refs'
original=packed.read_bytes()
packed.write_bytes(original+b''.join(f'{one} refs/heads/bulk-{i:04}\n'.encode() for i in range(1000)))
p=subprocess.run([C,'list',str(seed/'.git'),'refs/heads/'],capture_output=True,timeout=30)
expected=b''.join(f'{one} refs/heads/bulk-{i:04}\n'.encode() for i in range(1000))+f'{two} refs/heads/main\n{one} refs/heads/topic\n'.encode()
assert (p.returncode,p.stdout,p.stderr)==(0,expected,b''),(p.returncode,p.stderr)
rows.append({'listing':1002})
packed.write_bytes(original+b''.join(f'{one} refs/heads/bulk-{i:04}\n'.encode() for i in range(4095)))
p=subprocess.run([C,'list',str(seed/'.git'),'refs/heads/'],capture_output=True,timeout=30)
assert (p.returncode,p.stdout,p.stderr)==(1,b'',b'limit\n'),(p.returncode,p.stderr)
rows.append({'listing-limit':4097,'explicit':True})
packed.write_bytes(original)
for i,(name,old,new,message) in enumerate([
 ('refs/heads/new','-',one,'branch: Created from main'),
 ('refs/heads/topic',one,two,'branch: Reset to main'),
 ('refs/heads/topic',one,one,'same oid'),
 ('refs/heads/topic',one,'-','delete'),
 ('refs/tags/new','-',one,'tag'),
]):
 root=base/f'write-{i}';root.mkdir();repo=root/'repo'
 def restore():
  if repo.exists():shutil.rmtree(repo)
  shutil.copytree(seed,repo)
 restore()
 args=[G,'update-ref','--no-deref','-m',message,name,'0'*40 if new=='-' else new,'0'*40 if old=='-' else old]
 expected=O['capture'](args,repo)
 restore();actual=O['capture']([C,'write',str(repo/'.git'),name,old,new,message],repo)
 assert O['equivalent'](expected,actual),(i,expected,actual)
 rows.append({'write':name,'before':old,'after':new,'exact':True})
for i,condition in enumerate(['stale','ref-lock','packed-lock']):
 repo=base/f'failure-{i}';shutil.copytree(seed,repo)
 expected_old=two if condition=='stale' else one
 new='-' if condition=='packed-lock' else two
 if condition!='stale':
  lock=repo/'.git'/('refs/heads/topic.lock' if condition=='ref-lock' else 'packed-refs.lock')
  lock.parent.mkdir(parents=True,exist_ok=True);lock.write_bytes(b'foreign lock\n')
 before={str(p.relative_to(repo)):p.read_bytes() for p in repo.rglob('*') if p.is_file()}
 result=subprocess.run([C,'write',str(repo/'.git'),'refs/heads/topic',expected_old,new,'test'],capture_output=True)
 after={str(p.relative_to(repo)):p.read_bytes() for p in repo.rglob('*') if p.is_file()}
 assert result.returncode==1 and before==after,(condition,result.returncode,result.stderr)
 rows.append({'failure':condition,'immutable':True,'stderr':result.stderr.hex()})
(R/f'target/refs-api-{a.tier}.json').write_text(json.dumps(rows,indent=2)+'\n')
print('refs independent client:',len(rows),'checks; 1002-ref bounded enumeration; zero skips',flush=True)
