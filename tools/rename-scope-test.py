"""Edited -a previews and summaries, quiet commits, and no identity fallback."""
import argparse,json,os,pathlib,runpy,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser();ap.add_argument('--tier',default='native');a=ap.parse_args()
G=os.environ['DEN_GIT'];C=str(R/f'target/{a.tier}/commit-client');O=runpy.run_path(str(R/'tools/oracle.py'))
base=R/f'target/rename-scope-{a.tier}'
if base.exists():shutil.rmtree(base)
base.mkdir();seed=base/'seed';seed.mkdir()
def git(repo,*args):
 p=subprocess.run([G,*args],cwd=repo,capture_output=True);assert p.returncode==0,(args,p.stderr)
 return p.stdout
git(seed,'init','-q');(seed/'old').write_bytes(b'a'*64);git(seed,'add','old');git(seed,'commit','-qm','root')
(seed/'old').unlink();(seed/'new').write_bytes(b'b'*64);git(seed,'add','-N','new')
repo=base/'repo'
def restore():
 if repo.exists():shutil.rmtree(repo)
 shutil.copytree(seed,repo,symlinks=True)
restore();human_expected=O['capture']([G,'commit','-a','-m','scope'],repo,index_proof=True)
restore();p=O['capture']([C,'commit','-a','-m','scope'],repo,index_proof=True)
assert human_expected['status']==p['status']==0 and O['equivalent'](human_expected,p,'index-stat-proven'),(human_expected,p)
assert b'rename old => new (100%)' in bytes.fromhex(p['stdout'])
assert b'1 insertion(+), 1 deletion(-)' in bytes.fromhex(p['stdout'])
restore();expected=O['capture']([G,'commit','-a','-q','-m','scope'],repo,index_proof=True)
restore();actual=O['capture']([C,'commit','-a','-q','-m','scope'],repo,index_proof=True)
assert expected['status']==actual['status']==0 and O['equivalent'](expected,actual,'index-stat-proven')
# Explicit invalid bytes in an identity/date environment never select fallback
# config or the wall clock. This is a named language-boundary refusal, not Git
# output parity for non-UTF-8 strings.
invalid=[]
for key in ('GIT_AUTHOR_NAME','GIT_AUTHOR_EMAIL','GIT_AUTHOR_DATE','GIT_COMMITTER_NAME','GIT_COMMITTER_EMAIL','GIT_COMMITTER_DATE'):
 restore();state=O['snapshot'](repo);env=dict(os.environb);env[key.encode()]=b'\xff'
 q=subprocess.run([C,'commit','-a','-q','-m','must refuse'],cwd=repo,env=env,capture_output=True)
 assert q.returncode==2 and b'not yet implemented' in q.stderr and key.encode() in q.stderr,(key,q.returncode,q.stderr)
 assert O['snapshot'](repo)==state
 invalid.append(dict(key=key,status=q.returncode,stderr=q.stderr.hex()))
(R/f'target/rename-scope-{a.tier}.json').write_text(json.dumps(dict(human_git=human_expected,human_den=p,quiet_git=expected,quiet_den=actual,invalid_environment=invalid),indent=2)+'\n')
print(f'rename scope {a.tier}: unpublished -a preview and unequal-R100 human summary, quiet full-state parity, six explicit identity refusals PASS')
