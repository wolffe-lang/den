"""Pinned revision grammar observations; immutable loose/packed fixtures, exact bytes."""
import argparse, hashlib, json, os, pathlib, runpy, shutil, subprocess
p=argparse.ArgumentParser();p.add_argument('--tier',default='native');p.add_argument('--measure',action='store_true');a=p.parse_args()
R=pathlib.Path(__file__).resolve().parent.parent
G=os.environ['DEN_GIT'];D=R/f'target/{a.tier}/den';client=R/f'target/{a.tier}/revision-client'
pack=runpy.run_path(str(R/'tools/packed-fixture.py'))['pack_fixture']
root=R/f'target/revision-{a.tier}';shutil.rmtree(root,ignore_errors=True);root.mkdir(parents=True)
rows=[];fail=[];clients=[];scopes=[]
def run(exe,args,cwd,data=None):
 q=subprocess.run([str(exe),*args],cwd=cwd,input=data,capture_output=True)
 return dict(status=q.returncode,stdout=q.stdout.hex(),stderr=q.stderr.hex())
def g(cwd,*args,data=None):
 q=run(G,args,cwd,data);assert q['status']==0,(args,q);return bytes.fromhex(q['stdout']).strip().decode()
def state(cwd):
 return {str(f.relative_to(cwd)):[f.lstat().st_mode,hashlib.sha256(f.read_bytes()).hexdigest()] for f in sorted(cwd.rglob('*')) if f.is_file()}
base=root/'seed';base.mkdir();g(base,'init','-q')
blob=g(base,'hash-object','-w','--stdin',data=b'content\n')
rawblob=g(base,'hash-object','-w','--stdin',data=b'raw path\n')
tree=g(base,'mktree','-z',data=f'100644 blob {blob}\tfile'.encode()+b'\0'+f'100644 blob {rawblob}\t'.encode()+b'\xff\0')
def commit(subject,parents=(),n=0):
 data=f'tree {tree}\n'.encode()+b''.join(f'parent {x}\n'.encode() for x in parents)+f'author A <a@b> {1700000000+n} +0000\ncommitter C <c@d> {1700000000+n} +0000\n\n{subject}\n'.encode()
 return g(base,'hash-object','-w','-t','commit','--stdin',data=data)
c0=commit('root');c1=commit('one',[c0],1);c2=commit('two',[c1],2);side=commit('side',[c0],3);merge=commit('merge',[c2,side],4)
for name,id in [('main',merge),('topic',c2),('side',side)]:g(base,'update-ref','refs/heads/'+name,id)
g(base,'tag','-a','-m','tag','v1',merge);g(base,'tag','-a','-m','nested','v2','v1')
# Deliberately ambiguous ref namespace and search-order levels.
for name,id in [('refs/tags/dup',c1),('refs/heads/dup',c2),('refs/order',c0),('refs/tags/order',c1),('refs/heads/order',c2),('refs/remotes/origin/main',c1),('refs/remotes/origin/HEAD',c2)]:g(base,'update-ref',name,id)
# Deterministically find a real short-SHA collision, independent of den.
seen={}
for n in range(100000):
 data=f'collision {n}\n'.encode();oid=hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest();prefix=oid[:4]
 if prefix in seen:
  g(base,'hash-object','-w','--stdin',data=seen[prefix]);g(base,'hash-object','-w','--stdin',data=data);collision=prefix;break
 seen[prefix]=data
else:raise AssertionError('collision not found')
# Explicit deterministic reflogs, including detach and checkout history.
zero='0'*40
identity='A <a@b> 1700000000 +0000'
(base/'.git/logs/HEAD').write_text(f'{zero} {c0} {identity}\tcommit (initial): root\n{c0} {c2} {identity}\tcheckout: moving from main to topic\n{c2} {merge} {identity}\tcheckout: moving from topic to main\n')
(base/'.git/logs/refs/heads/main').write_text(f'{zero} {c0} {identity}\tcommit (initial): root\n{c0} {c1} {identity}\tcommit: one\n{c1} {merge} {identity}\tmerge: main\n')
for name,id in [('ORIG_HEAD',c1),('CHERRY_PICK_HEAD',c2),('REBASE_HEAD',side),('MERGE_HEAD',side)]: (base/'.git'/name).write_text(id+'\n')
# A foreign index lock and dirty file are mandatory read-only witnesses.
(base/'dirty').write_bytes(b'leave unchanged\n');(base/'.git/index.lock').write_bytes(b'foreign\n')
atoms=['HEAD','@','main','heads/main','refs/heads/main','tags/v1','refs/tags/v1','origin/main','origin','order','dup','v1','v2',merge,merge[:10],'ORIG_HEAD','CHERRY_PICK_HEAD','REBASE_HEAD','MERGE_HEAD','HEAD^','HEAD^0','HEAD^1','HEAD^2','HEAD~','HEAD~2','HEAD^2~','v1^0','v2^{}','v2^{commit}','HEAD^{tree}','v2^{tag}','HEAD^{object}','HEAD@{0}','HEAD@{1}','main@{1}','@{1}','@{-1}','@{-2}']
bad=['does-not-exist','HEAD^3','HEAD~9','HEAD^{','HEAD^{bad}','HEAD^2x','a....b',collision,'file','HEAD@{99}']
commands=[]
for name in atoms: commands += [['log','--oneline','-n1',name],['show','-s',name]]
for name in ['HEAD:file','HEAD:','v2:file',tree+':file','HEAD:missing']:commands += [['show','-s',name]]
for names in [['topic..HEAD'],['topic...side'],['..HEAD'],['HEAD..'],['..'],['...'],['HEAD','^topic'],['topic..HEAD','side'],['topic...HEAD'],['side..topic']]:
 for flags in [[],['-n1'],['--skip=1'],['--first-parent'],['--reverse']]: commands += [['log','--oneline',*flags,*names]]
for name in ['topic..HEAD','topic...side','..HEAD','HEAD..']:
 commands += [['diff','--name-only',name]]
for name in bad:
 for command in ['log','show','diff']:commands += [[command,name]]
for mode in ['loose','packed']:
 repo=root/mode;shutil.copytree(base,repo)
 if mode=='packed':pack(G,repo)
 for args in commands:
  before=state(repo);expected=run(G,args,repo);after=state(repo)
  actual=expected if a.measure else run(D,args,repo)
  row=dict(mode=mode,args=args,expected=expected,actual=actual,unchanged=before==after==state(repo));rows.append(row)
  if actual!=expected or not row['unchanged']:
   fail.append([mode,args]);print('FAIL',mode,args,'expected',expected,'actual',actual,flush=True)
 if not a.measure:
  for name in atoms+['HEAD:file','v2:file',tree+':file']:
   expected=run(G,['rev-parse','--verify',name],repo);actual=run(client,[name],repo)
   clients.append(dict(mode=mode,name=name,expected=expected,actual=actual))
   if expected!=actual:fail.append(['client',mode,name]);print('FAIL client',mode,name,expected,actual,flush=True)
  # Raw byte path cannot be passed via wolf argv; public owned-byte API must support it.
  actual=run(client,['--raw'],repo);expected=dict(status=0,stdout=(rawblob+'\n').encode().hex(),stderr='')
  clients.append(dict(mode=mode,name='raw-byte-path',expected=expected,actual=actual))
  if expected!=actual:fail.append(['client',mode,'raw-byte-path'])
  for name,feature in [('@{yesterday}','revision date selector'),(':/text','revision message search'),('HEAD^@','revision parent-set shorthand'),('HEAD^!','revision parent-set shorthand'),('HEAD^-2','revision parent-set shorthand'),(':0:file','revision index expression'),('@{upstream}','revision upstream tracking'),('@{push}','revision push tracking')]:
   before=state(repo);actual=run(D,['show','-s',name],repo);expected=dict(status=2,stdout='',stderr=f'den: not yet implemented: {feature}\n'.encode().hex())
   scopes.append(dict(mode=mode,name=name,actual=actual,expected=expected,unchanged=state(repo)==before))
   if actual!=expected or state(repo)!=before:fail.append(['scope',mode,name])
summary=dict(rows=rows,clients=clients,named_scope=scopes,failures=fail,zero_skips=True)
(R/f'target/revision-{a.tier}.json').write_text(json.dumps(summary,indent=2)+'\n')
print('revision',len(rows),'rows',len(clients),'clients',len(scopes),'named scopes',len(fail),'failures',flush=True)
raise SystemExit(bool(fail))
