"""Blame documentation and pinned black-box contract; complete immutable state."""
import argparse, hashlib, json, os, pathlib, runpy, shutil, subprocess
p=argparse.ArgumentParser();p.add_argument('--tier',default='native');p.add_argument('--measure',action='store_true');a=p.parse_args()
R=pathlib.Path(__file__).resolve().parent.parent
G=os.environ['DEN_GIT'];D=R/f'target/{a.tier}/den';client=R/f'target/{a.tier}/blame-client'
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest()=='c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
pack=runpy.run_path(str(R/'tools/packed-fixture.py'))['pack_fixture']
root=R/f'target/blame-{a.tier}';shutil.rmtree(root,ignore_errors=True);root.mkdir(parents=True)
rows=[];clients=[];scopes=[];fail=[]
def run(exe,args,cwd,data=None):
 q=subprocess.run([str(exe),*args],cwd=cwd,input=data,capture_output=True)
 return dict(status=q.returncode,stdout=q.stdout.hex(),stderr=q.stderr.hex())
def g(cwd,*args,data=None):
 q=run(G,args,cwd,data);assert q['status']==0,(args,q);return bytes.fromhex(q['stdout']).strip().decode()
def state(cwd):
 return {str(f.relative_to(cwd)):[f.lstat().st_mode,hashlib.sha256(f.read_bytes()).hexdigest()] for f in sorted(cwd.rglob('*')) if f.is_file()}
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
for name,id in [('main',cre),('root',c0),('one',c1),('two',c2),('merge',cm),('reversed',reverse),('rename',cr),('white',cw),('binary',cb)]:g(base,'update-ref','refs/heads/'+name,id)
g(base,'tag','-a','-m','tag','v1',cm)
(base/'dirty').write_bytes(b'leave unchanged\n');(base/'.git/index.lock').write_bytes(b'foreign\n')
commands=[]
for rev,path in [('root','file'),('one','file'),('two','file'),('merge','file'),('reversed','file'),('rename','new name'),('HEAD','new name'),('white','file'),('binary','file'),('root','empty')]:
 for flags in [[],['--porcelain'],['--line-porcelain'],['--root'],['-l'],['-s'],['-e'],['-n'],['-f'],['--first-parent'],['-w']]:commands.append(['blame',*flags,rev,'--',path])
for flags in [['-L','2,4'],['-L2,+2'],['-L','4,-2'],['-L',',3'],['-L','3,'],['-L','3'],['-L','4,2'],['-L','1,2','-L','2,4'],['-L','5,99'],['-L','0,2'],['-L','99,100'],['-L','2,+0'],['-L','2,-0'],['-L','2,2','--line-porcelain']]:commands.append(['blame',*flags,'merge','--','file'])
for rev in ['HEAD^','v1^0','merge^2','merge~1',cm,cm[:9]]:commands.append(['blame',rev,'--','file' if rev!='HEAD^' else 'new name'])
for rev,path in [('root','missing'),('none','file'),('root^','file')]:commands.append(['blame',rev,'--',path])
# Ranges are selected once against the final contents; raw bytes remain untouched.
for mode in ['loose','packed']:
 repo=root/mode;shutil.copytree(base,repo)
 if mode=='packed':pack(G,repo)
 for args in commands:
  before=state(repo);expected=run(G,args,repo);actual=expected if a.measure else run(D,args,repo)
  row=dict(mode=mode,args=args,expected=expected,actual=actual,unchanged=before==state(repo));rows.append(row)
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
summary=dict(rows=rows,clients=clients,named_scope=scopes,failures=fail,zero_skips=True)
(R/f'target/blame-{a.tier}.json').write_text(json.dumps(summary,indent=2)+'\n')
print('blame',len(rows),'rows',len(clients),'clients',len(scopes),'named scopes',len(fail),'failures',flush=True)
raise SystemExit(bool(fail))
