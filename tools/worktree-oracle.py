"""Strict generated worktree command matrix: stdout/stderr/status + all files.
Seed index bytes are copied unchanged to both sides. New stat words use the
per-entry six-word proof, never a blanket index exclusion.
"""
import argparse,json,os,pathlib,runpy,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser();ap.add_argument('--tier',default='native');ap.add_argument('--filter',default='');args=ap.parse_args()
G=os.environ['DEN_GIT'];C=str(R/f'target/{args.tier}/worktree-client')
O=runpy.run_path(str(R/'tools/oracle.py'))
base=R/f'target/worktree-oracle-{args.tier}'
if base.exists():shutil.rmtree(base)
base.mkdir();seeds=base/'seeds';seeds.mkdir()
def git(repo,*cmd):
 p=subprocess.run([G,*cmd],cwd=repo,capture_output=True)
 assert p.returncode==0,(cmd,p.stdout,p.stderr)
 return p.stdout

def seed(name):
 p=seeds/name;shutil.copytree(R/'target/corpus/two',p,symlinks=True);return p
p=seed('two')
p=seeds/'unborn';p.mkdir();git(p,'init','-q');(p/'new').write_bytes(b'new\n')
p=seed('staged');(p/'a.txt').write_bytes(b'changed staged\n');git(p,'add','a.txt')
p=seed('both');(p/'a.txt').write_bytes(b'staged\n');git(p,'add','a.txt');(p/'a.txt').write_bytes(b'worktree\n')
p=seed('rename');git(p,'mv','a.txt','renamed.txt')
p=seed('rename-mode');git(p,'mv','a.txt','renamed.txt');os.chmod(p/'renamed.txt',0o755);git(p,'add','renamed.txt')
p=seed('detached-tag');git(p,'tag','-a','anchor','-m','anchor');git(p,'checkout','--detach','anchor')
p=seed('removed');git(p,'rm','--cached','a.txt')
p=seed('modes');(p/'link').symlink_to('a.txt');(p/'exec').write_bytes(b'#!/bin/sh\necho hi\n');os.chmod(p/'exec',0o755);git(p,'add','.');git(p,'commit','-qm','modes')
p=seed('ignore');(p/'.gitignore').write_bytes(b'*.tmp\ncache/\n!keep.tmp\n')
(p/'cache').mkdir();(p/'cache/hidden').write_bytes(b'hidden\n');(p/'hide.tmp').write_bytes(b'hide\n');(p/'keep.tmp').write_bytes(b'keep\n')
(p/'dir').mkdir();(p/'dir/new').write_bytes(b'new\n');(p/'dir/other').write_bytes(b'other\n');(p/'space name').write_bytes(b'space\n')
p=seed('nested');(p/'dir/sub').mkdir(parents=True);(p/'dir/one').write_bytes(b'one\n');(p/'dir/sub/two').write_bytes(b'two\n');(p/'space name').write_bytes(b'space\n');(p/'tab\tname').write_bytes(b'tab\n');git(p,'add','.');git(p,'commit','-qm','nested')
p=seed('assume');git(p,'update-index','--assume-unchanged','a.txt');(p/'a.txt').write_bytes(b'local\n')
p=seed('skip');git(p,'update-index','--skip-worktree','a.txt');(p/'a.txt').write_bytes(b'local\n')
p=seed('intent');(p/'new').write_bytes(b'new\n');git(p,'add','-N','new')
p=seed('detached');(p/'.git/HEAD').write_bytes(git(p,'rev-parse','HEAD'))
cases=[]
def case(name,cmd,fixture='two',ops=(),config=''):
 cases.append(dict(name=name,args=cmd,fixture=fixture,ops=list(ops),config=config))
write=lambda path,data:dict(op='write',path=path,hex=data.hex())
remove=lambda path:dict(op='remove',path=path)
chmod=lambda path,mode:dict(op='chmod',path=path,mode=mode)

for fixture in ('two','unborn','staged','both','rename','removed','modes','ignore','intent','detached','nested','assume','skip','rename-mode','detached-tag'):
 for flag in ([],['--porcelain'],['-s','-b'],['-z'],['--porcelain','--untracked-files=all'],['--porcelain','--untracked-files=no'],['--porcelain','--ignored']):
  case('status-'+fixture+'-'+'-'.join(flag or ['human']),['status',*flag],fixture)
 case('status-'+fixture+'-no-hints',['status'],fixture,config='[advice]\nstatusHints=false\n')
for name,cmd,ops in [
 ('unchanged',['add','a.txt'],[]),
 ('changed',['add','a.txt'],[write('a.txt',b'changed\n')]),
 ('new',['add','new'],[write('new',b'new\n')]),
 ('directory',['add','dir'],[write('dir/one',b'one\n'),write('dir/sub/two',b'two\n')]),
 ('all',['add','-A'],[write('a.txt',b'changed\n'),write('new',b'new\n'),remove('b.txt')]),
 ('update',['add','-u'],[write('a.txt',b'changed\n'),write('new',b'new\n'),remove('b.txt')]),
 ('dot',['add','.'],[write('new',b'new\n'),remove('b.txt')]),
 ('ignore-removal',['add','--ignore-removal','.'],[write('new',b'new\n'),remove('b.txt')]),
 ('intent',['add','-N','new'],[write('new',b'new\n')]),
 ('chmod-plus',['add','--chmod=+x','a.txt'],[]),
 ('chmod-minus',['add','--chmod=-x','a.txt'],[chmod('a.txt',0o755)]),
 ('missing',['add','missing'],[]),('no-path',['add'],[]),
]:case('add-'+name,cmd,ops=ops)
case('add-ignored',['add','hide.tmp'],'ignore')
case('add-force',['add','-f','hide.tmp'],'ignore')
case('add-mode-disabled',['add','a.txt'],ops=[chmod('a.txt',0o755)],config='[core]\nfileMode=false\n')
for name,cmd,fixture,ops in [
 ('plain',['rm','a.txt'],'two',[]),('cached',['rm','--cached','a.txt'],'two',[]),('quiet',['rm','-q','a.txt'],'two',[]),
 ('modified',['rm','a.txt'],'two',[write('a.txt',b'local\n')]),('force',['rm','-f','a.txt'],'two',[write('a.txt',b'local\n')]),
 ('staged',['rm','a.txt'],'staged',[]),('both',['rm','a.txt'],'both',[]),('cached-both',['rm','--cached','a.txt'],'both',[]),
 ('cached-staged',['rm','--cached','a.txt'],'staged',[]),('missing',['rm','missing'],'two',[]),
]:case('rm-'+name,cmd,fixture,ops)
for name,cmd,ops in [
 ('file',['mv','a.txt','moved'],[]),('modified',['mv','a.txt','moved'],[write('a.txt',b'local\n')]),
 ('overwrite',['mv','a.txt','b.txt'],[]),('force',['mv','-f','a.txt','b.txt'],[]),
 ('missing',['mv','missing','moved'],[]),('skip',['mv','-k','missing','moved'],[]),
]:case('mv-'+name,cmd,ops=ops)
for fixture in ('two','staged','both','removed','intent','modes'):
 for flags in ([],['--staged'],['--staged','--worktree'],['--source=HEAD']):
  case('restore-'+fixture+'-'+'-'.join(flags or ['worktree']),['restore',*flags,'a.txt'],fixture,[write('a.txt',b'local\n')])
case('restore-missing',['restore','missing'])
case('checkout-path',['checkout','--','a.txt'],ops=[write('a.txt',b'local\n')])
case('restore-exec',['restore','exec'],'modes',[chmod('exec',0o644),write('exec',b'changed\n')])
case('restore-link',['restore','link'],'modes',[remove('link'),write('link',b'changed\n')])

for cmd in [['rm','dir'],['rm','-r','dir'],['rm','--cached','-r','dir'],['mv','dir','moved'],['mv','dir','dir/sub'],['restore','dir']]:
 case('nested-'+'-'.join(cmd),cmd,'nested')
case('mv-into-directory',['mv','a.txt','dir'],'nested')
case('mv-multiple',['mv','a.txt','b.txt','dir'],'nested')
case('status-nested-quotes',['status','--porcelain'],'nested',[write('space name',b'changed\n'),write('tab\tname',b'changed\n')])
case('add-symlink',['add','link'],'modes')
case('restore-symlink-false',['restore','link'],'modes',[remove('link'),write('link',b'wrong')],config='[core]\nsymlinks=false\n')
case('add-symlink-false',['add','link'],'modes',[remove('link'),write('link',b'b.txt')],config='[core]\nsymlinks=false\n')
case('status-filemode-false',['status','--porcelain'],'two',[chmod('a.txt',0o755)],config='[core]\nfileMode=false\n')
case('status-ignored-all',['status','--porcelain','--ignored','--untracked-files=all'],'ignore')
case('add-assume',['add','a.txt'],'assume')
case('add-skip',['add','a.txt'],'skip')
case('add-skip-no-hints',['add','a.txt'],'skip',config='[advice]\nupdateSparsePath=false\n')
for path in ['a.txt','hide.tmp','keep.tmp','cache/hidden','dir/new']:
 case('check-ignore-'+path,['check-ignore','-v',path],'ignore')

case('status-filemode-empty',['status','--porcelain'],'two',[chmod('a.txt',0o755)],config='[core]\nfileMode=\n')
for cmd in [['add','a.txt'],['rm','a.txt'],['mv','a.txt','moved'],['restore','a.txt']]:
 case('index-lock-'+cmd[0],cmd,'two',[write('.git/index.lock',b'foreign lock\n')])
selected=[c for c in cases if args.filter in c['name']]
assert selected,'empty selection'
rows=[]
for case in selected:
 root=base/case['name'].replace('/','_');root.mkdir()
 repo=root/'repo'
 def restore():
  if repo.exists():shutil.rmtree(repo)
  shutil.copytree(seeds/case['fixture'],repo,symlinks=True)
  if case['config']:
   with (repo/'.git/config').open('ab') as f:f.write(('\n'+case['config']).encode())
  for op in case['ops']:
   path=repo/op['path']
   if op['op']=='write':path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(bytes.fromhex(op['hex']))
   elif op['op']=='remove':path.unlink()
   elif op['op']=='chmod':os.chmod(path,op['mode'])
   else:raise AssertionError(op)
 restore();expected=O['capture']([G,*case['args']],repo,index_proof=True)
 restore();actual=O['capture']([C,*case['args']],repo,index_proof=True)
 good=O['equivalent'](expected,actual,'index-stat-proven')
 rows.append(dict(case=case,git=expected,den=actual,equal=good))
 print(('parity' if good else 'FAIL')+': '+case['name'],flush=True)
 if not good:
  print(' git',expected['status'],bytes.fromhex(expected['stdout']),bytes.fromhex(expected['stderr']))
  print(' den',actual['status'],bytes.fromhex(actual['stdout']),bytes.fromhex(actual['stderr']))
(R/f'target/worktree-oracle-{args.tier}.json').write_text(json.dumps(rows,indent=2)+'\n')
fails=sum(not r['equal'] for r in rows)
print(f'worktree oracle {args.tier}: {len(rows)-fails}/{len(rows)} parity, {fails} mismatches')
raise SystemExit(bool(fails))
