"""Blame documentation and pinned black-box contract; complete immutable state."""
import argparse, hashlib, json, os, pathlib, runpy, shutil, subprocess
p=argparse.ArgumentParser();p.add_argument('--tier',default='native');p.add_argument('--measure',action='store_true');a=p.parse_args()
R=pathlib.Path(__file__).resolve().parent.parent
G=os.environ['DEN_GIT'];D=R/f'target/{a.tier}/den';client=R/f'target/{a.tier}/blame-client'
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest()=='c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
pack=runpy.run_path(str(R/'tools/packed-fixture.py'))['pack_fixture']
root=R/f'target/blame-{a.tier}';shutil.rmtree(root,ignore_errors=True);root.mkdir(parents=True)
rows=[];clients=[];scopes=[];fail=[];snapshots={}
def run(exe,args,cwd,data=None):
 q=subprocess.run([str(exe),*args],cwd=cwd,input=data,capture_output=True)
 return dict(status=q.returncode,stdout=q.stdout.hex(),stderr=q.stderr.hex())
def g(cwd,*args,data=None):
 q=run(G,args,cwd,data);assert q['status']==0,(args,q);return bytes.fromhex(q['stdout']).strip().decode()
def state(cwd):
 out={}
 for f in sorted(cwd.rglob('*')):
  if f.is_symlink():data=['symlink',os.fsencode(os.readlink(f)).hex()]
  elif f.is_file():data=['file',hashlib.sha256(f.read_bytes()).hexdigest()]
  elif f.is_dir():data=['directory']
  else:data=['other']
  out[str(f.relative_to(cwd))]=[f.lstat().st_mode,*data]
 return out
base=root/'seed';base.mkdir();g(base,'init','-q')
def commit(files,parents=(),author='A',n=0,zone='+0000'):
 entries=[]
 for path,data in sorted(files.items()):
  blob=g(base,'hash-object','-w','--stdin',data=data);entries.append(f'100644 blob {blob}\t'.encode()+path+b'\0')
 tree=g(base,'mktree','-z',data=b''.join(entries))
 data=f'tree {tree}\n'.encode()+b''.join(f'parent {x}\n'.encode() for x in parents)+f'author {author} <a@b> {1700000000+n} {zone}\ncommitter C <c@d> {1700000100+n} +0000\n\nsubject {n}\n\nbody\n'.encode()
 return g(base,'hash-object','-w','-t','commit','--stdin',data=data)
f0={b'file':b'alpha\nbeta\ngamma\ndelta\nepsilon\n',b'raw\xff':b'raw\xff\nlast',b'empty':b''}
c0=commit(f0);f1={**f0,b'file':b'alpha\nBETA\ngamma\ndelta\nepsilon\n'};c1=commit(f1,[c0],'Long Author',10,'+0530')
f2={**f1,b'file':b'insert\nalpha\nBETA\ngamma\nepsilon\ntrailer'};c2=commit(f2,[c1],'Z',20,'-0230')
side=commit({**f0,b'file':b'alpha\nbeta\ngamma\nDELTA\nepsilon\n'},[c0],'Side',30)
merged={**f1,b'file':b'alpha\nBETA\ngamma\nDELTA\nepsilon\n'};cm=commit(merged,[c1,side],'Merger',40)
reverse=commit(merged,[side,c1],'Merger',40)
renamed={k:v for k,v in merged.items() if k!=b'file'};renamed[b'new name']=merged[b'file'];cr=commit(renamed,[cm],'Rename',50)
fr={**renamed,b'new name':b'alpha\nBETA\ngamma\nDELTA\nnew-end\n'};cre=commit(fr,[cr],'Edit',60)
cw=commit({**f1,b'file':b' alpha \n B E T A\n\tgamma\r\ndelta\nepsilon'},[c1],'White',70)
cb=commit({b'file':b'a\x00b\nraw\xff\nno-lf'},[],'Binary',80)
left=commit({b'file':b'new-alpha\nbeta\ngamma\ndelta\nepsilon\n'},[c0],'Left',81)
right=commit({b'file':b'new-alpha\nnew-beta\ngamma\ndelta\nepsilon\n'},[c0],'Right',82)
same_second=commit({b'file':b'new-alpha\nnew-beta\ngamma\ndelta\nepsilon\n'},[left,right],'Same second',83)
novel_merge=commit({b'file':b'new-alpha\nnew-beta\ngamma\nnovel\nepsilon\n'},[left,right],'Novel merge',84)
edited_rename=commit({b'edited':b'alpha\nBETA\ngamma\nDELTA\nchanged\n'},[cm],'Edited rename',85)
repeated=commit({b'file':b'repeat\nrepeat\n'},[],'Repeated',86)
repeat_edit=commit({b'file':b'repeat\nchange\n'},[repeated],'Repeat edit',87)
reordered=commit({b'file':b'beta\nalpha\ngamma\ndelta\nepsilon\n'},[c0],'Reorder',88)
for name,id in [('same-second',same_second),('novel-merge',novel_merge),('edited-rename',edited_rename),('repeated',repeated),('repeat-edit',repeat_edit),('reordered',reordered)]:g(base,'update-ref','refs/heads/'+name,id)
for name,id in [('main',cre),('root',c0),('one',c1),('two',c2),('merge',cm),('reversed',reverse),('rename',cr),('white',cw),('binary',cb)]:g(base,'update-ref','refs/heads/'+name,id)
g(base,'tag','-a','-m','tag','v1',cm)
# Independent monotone edit histories, unique byte lines and alternating final LF.
import random
rng=random.Random(1100)
random_revs=[]
for seed in range(8):
 content=[f'{seed}-line-{i}'.encode() for i in range(8)];parent=[]
 for step in range(4):
  if step:
   at=rng.randrange(len(content));content[at]=f'{seed}-replacement-{step}'.encode()
   content.insert(rng.randrange(len(content)+1),f'{seed}-insert-{step}'.encode())
   if step%2:content.pop(rng.randrange(len(content)))
  rev=commit({b'file':b'\n'.join(content)+(b'\n' if step%2==0 else b'')},parent,f'Random {seed}',100+seed*4+step)
  parent=[rev];random_revs.append(rev)
  g(base,'update-ref',f'refs/heads/random-{seed}-{step}',rev)
(base/'dirty').write_bytes(b'leave unchanged\n');(base/'.git/index.lock').write_bytes(b'foreign\n')
commands=[]
for rev,path in [('root','file'),('one','file'),('two','file'),('merge','file'),('reversed','file'),('rename','new name'),('HEAD','new name'),('white','file'),('binary','file'),('root','empty'),('same-second','file'),('novel-merge','file'),('edited-rename','edited'),('repeated','file')]:
 for flags in [[],['--porcelain'],['--line-porcelain'],['--root'],['-l'],['-s'],['-e'],['-n'],['-f'],['--first-parent'],['-w']]:commands.append(['blame',*flags,rev,'--',path])
for flags in [['-L','2,4'],['-L2,+2'],['-L','4,-2'],['-L',',3'],['-L','3,'],['-L','3'],['-L','4,2'],['-L','1,2','-L','2,4'],['-L','5,99'],['-L','0,2'],['-L','99,100'],['-L','2,+0'],['-L','2,-0'],['-L','2,2','--line-porcelain']]:commands.append(['blame',*flags,'merge','--','file'])
for rev in ['HEAD^','v1^0','merge^2','merge~1',cm,cm[:9]]:commands.append(['blame',rev,'--','file' if rev!='HEAD^' else 'new name'])
for rev,path in [('root','missing'),('none','file'),('root^','file')]:commands.append(['blame',rev,'--',path])
for rev in random_revs:
 for flags in [[],['--line-porcelain']]:commands.append(['blame',*flags,rev,'--','file'])
# Ranges are selected once against the final contents; raw bytes remain untouched.
for mode in ['loose','packed']:
 repo=root/mode;shutil.copytree(base,repo)
 if mode=='packed':pack(G,repo)
 snapshots[str(repo.relative_to(root))]=state(repo)
 for args in commands:
  before=state(repo);expected=run(G,args,repo);actual=expected if a.measure else run(D,args,repo)
  row=dict(fixture_set='new',mode=mode,args=args,expected=expected,actual=actual,unchanged=before==state(repo));rows.append(row)
  if expected!=actual or not row['unchanged']:fail.append([mode,args]);print('FAIL',mode,args,expected,actual,flush=True)
 if not a.measure:
  for args,feature in [(['-M'],'blame moved-line detection (-M)'),(['-C'],'blame copied-line detection (-C)'),(['-C','-C','-C'],'blame copied-line detection (-C)'),(['--ignore-rev',c1],'blame ignored revisions'),(['--contents','dirty'],'blame alternate contents'),(['--reverse','root..merge'],'blame reverse history'),(['-L',':function'],'blame function ranges'),(['-L','/alpha/,3'],'blame regex ranges')]:
   before=state(repo);actual=run(D,['blame',*args,'merge','--','file'],repo);expected=dict(status=2,stdout='',stderr=f'den: not yet implemented: {feature}\n'.encode().hex())
   scopes.append(dict(mode=mode,args=args,expected=expected,actual=actual,unchanged=before==state(repo)))
   if expected!=actual or before!=state(repo):fail.append(['scope',mode,args]);print('FAIL scope',args,actual,flush=True)
  for rev,path in [('merge','file'),('reversed','file'),('HEAD','new name'),('root',b'raw\xff'),('white','file')]:
   before=state(repo);raw=isinstance(path,bytes);args=[rev,'--raw' if raw else path]
   actual=run(client,args,repo);expected=run(G,['blame','--line-porcelain',rev,'--',path],repo)
   clients.append(dict(mode=mode,args=[rev,repr(path)],expected=expected,actual=actual,unchanged=before==state(repo)))
   if expected!=actual or before!=state(repo):fail.append(['client',mode,repr(path)]);print('FAIL client',rev,repr(path),expected,actual,flush=True)
  before=state(repo);actual=run(client,['--limits'],repo);expected=dict(status=0,stdout=b'limits: exact cap, over cap, invalid cap, malformed result\n'.hex(),stderr='')
  clients.append(dict(mode=mode,args=['--limits'],expected=expected,actual=actual,unchanged=before==state(repo)))
  if expected!=actual or before!=state(repo):fail.append(['client',mode,'limits']);print('FAIL client limits',actual,flush=True)
 # Conservative alignment refusals are measured non-parity rows, not altered oracle expectations.
 if not a.measure:
  for rev,feature in [('repeat-edit','blame repeated or hash-colliding changed lines'),('reordered','blame reordered common lines')]:
   before=state(repo);actual=run(D,['blame',rev,'--','file'],repo);oracle=run(G,['blame',rev,'--','file'],repo)
   expected=dict(status=2,stdout='',stderr=f'den: not yet implemented: {feature}\n'.encode().hex())
   scopes.append(dict(mode=mode,args=[rev],expected=expected,actual=actual,oracle=oracle,unchanged=before==state(repo)))
   if expected!=actual or before!=state(repo):fail.append(['scope',mode,rev])
# Original corpus fixtures used by vc09, copied immutably in both storage modes.
inherited=root/'inherited';runpy.run_path(str(R/'tools/corpus.py'))['build'](inherited)
for name,path in [('two','a.txt'),('linear','a.txt'),('merge','a.txt'),('rename','renamed.txt'),('binary','raw.bin'),('symlink','a.txt'),('thousand','file-0001'),('m2-amend','a.txt'),('m2-index-v4','a.txt'),('m2-edited-rename','a.txt')]:
 for mode in ['loose','packed']:
  repo=root/f'inherited-{name}-{mode}';shutil.copytree(inherited/name,repo)
  if mode=='packed':pack(G,repo)
  (repo/'dirty-witness').write_bytes(b'unchanged\n');(repo/'.git/index.lock').write_bytes(b'foreign\n')
  snapshots[str(repo.relative_to(root))]=state(repo)
  for flags in [[],['--porcelain'],['--line-porcelain'],['-w'],['--first-parent']]:
   args=['blame',*flags,'HEAD','--',path];before=state(repo);expected=run(G,args,repo);actual=expected if a.measure else run(D,args,repo)
   row=dict(fixture_set='vc09-corpus',fixture=name,mode=mode,args=args,expected=expected,actual=actual,unchanged=before==state(repo));rows.append(row)
   if expected!=actual or before!=state(repo):fail.append(['inherited',name,mode,args]);print('FAIL inherited',name,mode,args,expected,actual,flush=True)
summary=dict(rows=rows,clients=clients,named_scope=scopes,fixture_states=snapshots,failures=fail,zero_skips=True)
(R/f'target/blame-{a.tier}.json').write_text(json.dumps(summary,indent=2)+'\n')
print('blame',len(rows),'rows',len(clients),'clients',len(scopes),'named scopes',len(fail),'failures',flush=True)
raise SystemExit(bool(fail))
