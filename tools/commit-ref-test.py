"""Independent byte assertions for ref CAS, locks and failed index preparation."""
import argparse,json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser();ap.add_argument('--tier',default='native');a=ap.parse_args()
G=os.environ['DEN_GIT'];C=str(R/f'target/{a.tier}/commit-client');base=R/f'target/commit-ref-{a.tier}'
if base.exists():shutil.rmtree(base)
base.mkdir();rows=[]
def run(cmd,cwd,status=0):
 p=subprocess.run(cmd,cwd=cwd,capture_output=True,timeout=30)
 rows.append(dict(command=cmd,status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex()))
 assert p.returncode==status,(cmd,p.returncode,p.stdout,p.stderr)
 return p

def git(repo,*args):return run([G,*args],repo).stdout
for mode in ('unborn','normal','same','stale','lock','head-lock'):
 repo=base/mode;repo.mkdir();git(repo,'init','-q')
 p=subprocess.run([G,'mktree'],cwd=repo,input=b'',capture_output=True);assert p.returncode==0
 tree=p.stdout.strip().decode()
 old=git(repo,'commit-tree',tree,'-m','old').strip().decode()
 new=git(repo,'commit-tree',tree,'-p',old,'-m','new').strip().decode()
 if mode!='unborn':git(repo,'update-ref','refs/heads/main',old)
 if mode=='same':new=old
 original=repo/'.git/ORIG_HEAD';original.write_bytes(b'preserve this byte string\n')
 head=repo/'.git/HEAD';head_before=head.read_bytes()
 logs=[repo/'.git/logs/HEAD',repo/'.git/logs/refs/heads/main']
 prior=[p.read_bytes() if p.exists() else b'' for p in logs]
 message=base/(mode+'-message');message.write_bytes(b'alpha\nsecond\n')
 expected_old='-' if mode=='unborn' else '1'*40 if mode=='stale' else old
 command='verify-'+mode if mode in ('stale','lock','head-lock') else 'verify-publish'
 run([C,command,expected_old,new,'Ref Tester','ref@example.invalid','1700000000 +0000','commit',str(message)],repo)
 assert head.read_bytes()==head_before and original.read_bytes()==b'preserve this byte string\n'
 assert not (repo/'.git/HEAD.lock').exists() and not (repo/'.git/refs/heads/main.lock').exists()
 actual=[p.read_bytes() if p.exists() else b'' for p in logs]
 if mode in ('stale','lock','head-lock'):
  assert actual==prior and (repo/'.git/refs/heads/main').read_text()==old+'\n'
 else:
  before_oid='0'*40 if mode=='unborn' else old
  line=f'{before_oid} {new} Ref Tester <ref@example.invalid> 1700000000 +0000\tcommit: alpha\n'.encode()
  assert actual[0]==prior[0]+line
  assert actual[1]==prior[1]+(b'' if mode=='same' else line)
  assert (repo/'.git/refs/heads/main').read_text()==new+'\n'
for all_flag in (False,True):
 for phase in ('index-write','index-sync'):
  repo=base/f'fail-{all_flag}-{phase}';shutil.copytree(R/'target/corpus/two',repo,symlinks=True)
  (repo/'a.txt').write_bytes(b'changed\n')
  if not all_flag:git(repo,'add','a.txt')
  paths=['HEAD','refs/heads/main','logs/HEAD','logs/refs/heads/main','index']
  before={p:(repo/'.git'/p).read_bytes() for p in paths}
  run([C,'injected',phase,'commit',*(['-a'] if all_flag else []),'-m','must not publish'],repo,status=128)
  assert before=={p:(repo/'.git'/p).read_bytes() for p in paths}
  assert not list((repo/'.git').rglob('*.lock'))
(R/f'target/commit-ref-{a.tier}.json').write_text(json.dumps(rows,indent=2)+'\n')
print(f'commit refs {a.tier}: independent framing, unborn/same/stale/foreign locks and4 preparation failures PASS')
