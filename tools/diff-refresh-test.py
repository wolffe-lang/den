"""Documented diff.autoRefreshIndex, measured with stale/copied index metadata.
Only the six independently proved inode/time words are canonicalized.
"""
import argparse,json,os,pathlib,runpy,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parent.parent
O=runpy.run_path(str(ROOT/'tools/oracle.py'))


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--tier',choices=('native','release'),default='native');ap.add_argument('--oracle-only',action='store_true');a=ap.parse_args()
 git=os.environ['DEN_GIT'];den=str(ROOT/f'target/{a.tier}/den');base=ROOT/f'target/diff-refresh-{a.tier}'
 if base.exists():shutil.rmtree(base)
 base.mkdir(parents=True);source=base/'source';source.mkdir()
 def g(*args):subprocess.run([git,*args],cwd=source,check=True,capture_output=True)
 g('init','-q');(source/'a').write_bytes(b'a\n');(source/'b').write_bytes(b'b\n');g('add','-A');g('commit','-qm','base')
 cases=[]
 for dirty in (True,False):
  for flag in ([],['--exit-code'],['--quiet'],['--name-only'],['--name-status'],['--numstat'],['--stat'],['HEAD'],['--cached'],['--','a'],['--','b']):
   for setting in ('default','disabled','locked'):
    cases.append((dirty,flag,setting))
 results=[]
 for n,(dirty,flag,setting) in enumerate(cases):
  repo=base/'repo'
  def restore():
   if repo.exists():shutil.rmtree(repo)
   shutil.copytree(source,repo)
   if dirty:(repo/'a').write_bytes(b'changed\n')
   if setting=='disabled':
    with (repo/'.git/config').open('ab') as f:f.write(b'[diff]\n autoRefreshIndex = false\n')
   if setting=='locked':(repo/'.git/index.lock').write_bytes(b'foreign')
  restore();old=(repo/'.git/index').read_bytes();expected=O['capture']([git,'diff',*flag],repo,index_proof=True)
  fresh=bytes.fromhex(expected['repository']['.git/index']['hex'])
  actual=None;ok=None
  if not a.oracle_only:
   restore();actual=O['capture']([den,'diff',*flag],repo,index_proof=True);ok=O['equivalent'](expected,actual,'index-stat-proven')
  print(n,dirty,flag,setting,'refresh',old!=fresh,'status',expected['status'],'stderr',expected['stderr'],'ok',ok,flush=True)
  results.append({'name':f'refresh-{n}','dirty':dirty,'args':['diff',*flag],'setting':setting,'refresh':old!=fresh,'git':expected,'den':actual,'ok':ok})
 (ROOT/f'target/diff-refresh-{a.tier}.json').write_text(json.dumps({'rows':results},indent=2)+'\n')
 if not a.oracle_only:assert all(r['ok'] for r in results),[r['name'] for r in results if not r['ok']]

if __name__=='__main__':main()
