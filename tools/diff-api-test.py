"""Independent package client for the pure collect/render consumer boundary."""
import argparse,json,os,pathlib,runpy,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
O=runpy.run_path(str(R/'tools/oracle.py'))
a=argparse.ArgumentParser();a.add_argument('--tier',required=True);a=a.parse_args()
git=os.environ['DEN_GIT'];driver=R/f'target/{a.tier}/diff-client';repo=R/f'target/diff-api-{a.tier}'
if repo.exists():shutil.rmtree(repo)
repo.mkdir(parents=True)
def g(*args):return subprocess.run([git,*args],cwd=repo,check=True,capture_output=True).stdout.strip().decode()
g('init','-q');(repo/'a').write_bytes(b'old\n');g('add','a');g('commit','-qm','base');first=g('rev-parse','HEAD')
(repo/'a').write_bytes(b'new\n');g('add','a');g('commit','-qm','next');second=g('rev-parse','HEAD')
(repo/'a').rename(repo/'moved');(repo/'moved').write_bytes(b'new\nedit\n');g('add','-A');(repo/'moved').write_bytes(b'worktree\n')
rows=[]
for endpoint in ([],['--cached'],[first,second]):
 for mode in ([],['--stat'],['--name-status'],['-U0']):
  before={'repository':O['snapshot'](repo),'worktree':O['worktree_snapshot'](repo)}
  expected=O['capture']([git,'diff',*endpoint,*mode],repo)
  actual=O['capture']([str(driver),*endpoint,*mode],repo)
  assert actual['repository']==before['repository'] and actual['worktree']==before['worktree']
  assert actual==expected,(endpoint,mode,expected['stdout'],actual['stdout'])
  rows.append({'args':[*endpoint,*mode],'result':actual})
(R/f'target/diff-api-{a.tier}.json').write_text(json.dumps({'rows':rows},indent=2)+'\n')
bad=subprocess.run([str(driver),'invalid'],cwd=repo,capture_output=True)
assert bad.returncode==1 and bad.stderr==b'invalid\n' and not bad.stdout,bad
print('diff external collect/render client: 12 exact command/state comparisons; zero skips')
