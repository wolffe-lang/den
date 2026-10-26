"""Exact pinned-Git history commands, raw objects, and read-only state witnesses."""
import argparse,hashlib,json,os,pathlib,random,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser();p.add_argument('--tier',default='native');a=p.parse_args()
G=os.environ['DEN_GIT']; DEN=R/f'target/{a.tier}/den'; root=R/f'target/history-{a.tier}'
if root.exists(): shutil.rmtree(root)
root.mkdir(parents=True)
rows=[]; failures=[]
def run(exe,args,data=None):
 q=subprocess.run([str(exe),*args],cwd=root,input=data,capture_output=True)
 return {'status':q.returncode,'stdout':q.stdout.hex(),'stderr':q.stderr.hex()}
def g(*args,data=None):
 q=run(G,args,data);assert q['status']==0,(args,q);return bytes.fromhex(q['stdout']).strip().decode()
def state():
 return {str(f.relative_to(root)):[f.lstat().st_mode,hashlib.sha256(f.read_bytes()).hexdigest()] for f in sorted(root.rglob('*')) if f.is_file()}
def check(name,args):
 before=state(); expected=run(G,args); after_git=state(); actual=run(DEN,args); after=state()
 row={'name':name,'args':args,'expected':expected,'actual':actual,'unchanged':before==after_git==after}
 rows.append(row)
 if actual!=expected or not row['unchanged']:
  failures.append(name)
  print('FAIL',name,args,'expected',bytes.fromhex(expected['stdout']),bytes.fromhex(expected['stderr']),'actual',bytes.fromhex(actual['stdout']),bytes.fromhex(actual['stderr']),flush=True)
def raw(msg,parents=(),seconds=1700000000,zone='+0530',committer=None,tree=None):
 if tree is None: tree=empty
 data=f'tree {tree}\n'.encode()+b''.join(f'parent {x}\n'.encode() for x in parents)+f'author A <a@b> {seconds} {zone}\ncommitter C <c@d> {seconds if committer is None else committer} -0230\n\n'.encode()+msg
 return g('hash-object','--literally','-w','-t','commit','--stdin',data=data)
def head(c):g('update-ref','refs/heads/main',c)
g('init','-q');empty=g('mktree',data=b'')
(root/'dirty').write_bytes(b'not staged\n');(root/'.git/index.lock').write_bytes(b'foreign lock\n')
for n,msg in enumerate([b'hello\n',b'hello',b'\n\n  hello  \nnext\t\n\nbody\n\n',b'',b'one\n\tindent\n',b'\xff\n',b'a\0b\n',b'  \n',b'tab\there\n']):
 c=raw(msg);head(c)
 for args in [['log'],['log','--oneline'],['show'],['show','--stat'],['log','--pretty=oneline'],['log','--pretty=short'],['log','--pretty=full'],['log','--pretty=fuller']]: check(f'message-{n}-{args}',args)
for seconds in [0,1,951782400,1700000000,2147483648,4102444800]:
 for zone in ['+0000','+0530','-0330','+1245']:
  head(raw(b'date\n',seconds=seconds,zone=zone))
  for style in ['default','iso','iso-strict','rfc','short','raw','unix','default-local','iso-local']:
   check(f'date-{seconds}-{zone}-{style}',['log','--date='+style])
# Empty and nonempty roots, edits, renames and binary objects use real shared diff.
parent=None; nodes=[]
for n,content in enumerate([b'old\n',b'new\n',b'new\nmore\n',b'new\nmore\n',b'bin\0ary\xff']):
 blob=g('hash-object','-w','--stdin',data=content)
 tree=g('mktree',data=f'100644 blob {blob}\t{"renamed" if n>=3 else "file"}\n'.encode())
 c=raw(f'change {n}\n'.encode(),[parent] if parent else [],tree=tree,seconds=1700000100+n);nodes.append(c);parent=c;head(c)
 for args in [['log'],['log','-p'],['log','--stat'],['log','-p','--stat'],['log','--oneline','-p'],['show'],['show','--stat'],['show','--oneline'],['show','--no-patch'],['log','-n','2'],['log','-n0'],['log','--max-count=2','--reverse'],['log','--skip=1'],['show',blob],['show','HEAD:'],['show','HEAD:'+('renamed' if n>=3 else 'file')]]: check(f'changes-{n}-{args}',args)
# DAGs with tied and skewed committer clocks and author clocks unrelated to order.
rng=random.Random(5)
for fixture in range(24):
 nodes=[]
 for n in range(8):
  parents=rng.sample(nodes,min(len(nodes),rng.randrange(1,4))) if nodes else []
  nodes.append(raw(f'node {fixture}/{n}\n'.encode(),parents,seconds=1700000100+n,committer=1700000000+rng.randrange(4)))
 head(nodes[-1])
 for args in [['log'],['log','--oneline'],['log','-p'],['log','-n3'],['log','--first-parent'],['log','--reverse'],['show','-s']]: check(f'dag-{fixture}-{args}',args)
# Independent public consumer cannot invoke the porcelain dispatcher.
client=R/f'target/{a.tier}/history-client'
before=state(); expected=run(G,['log','--oneline']); actual=run(client,[])
assert actual==expected and before==state(),('external client',expected,actual)
for mode,status,stderr in [('zero',0,b''),('limit',1,b'limit\n')]:
 before=state(); actual=run(client,[mode])
 assert actual=={'status':status,'stdout':'','stderr':stderr.hex()} and before==state(),(mode,actual)
for kind,obj in [('blob',blob),('tree',tree)]:
 for extra in [[],['--oneline'],['-s']]: check(f'show-{kind}-{extra}',['show',*extra,obj])
for msg in [b'tag message\n',b'tag message\n\n',b'tag message',b'']:
 tag=g('hash-object','-w','-t','tag','--stdin',data=f'object {nodes[-1]}\ntype commit\ntag v1\ntagger A <a@b> 1700000000 +0530\n\n'.encode()+msg)
 for extra in [['-s'],['--oneline','-s'],['-s','--date=iso']]: check(f'tag-{msg!r}-{extra}',['show',*extra,tag])
 check(f'log-tag-{msg!r}',['log',tag])
for items in [[blob,tree],[tree,blob],[blob,nodes[-1]],[nodes[-1],blob],[nodes[-1],nodes[-2]],[nodes[-1],tree,nodes[-2]]]:
 check(f'multi-{items}',['show','-s',*items])
refusals=[]
for extra in [['-n0'],['-n1'],['--skip=1'],['--reverse']]:
 args=['show','-s',*extra,nodes[-1],nodes[-2]]
 before=state(); expected=run(G,args); actual=run(DEN,args)
 assert actual=={'status':2,'stdout':'','stderr':b'den: not yet implemented: show revision limiting\n'.hex()} and state()==before
 refusals.append({'args':args,'expected':expected,'actual':actual,'reason':'show revision limiting is not implemented; NOT parity'})
for key,value,args in [('log.date','iso',['log']),('format.pretty','fuller',['log']),('log.abbrevCommit','true',['log']),('log.showRoot','false',['log','-p'])]:
 g('config',key,value);check('config-'+key,args);g('config','--unset',key)
g('config','log.decorate','full');check('override-decoration',['log','--no-decorate']);g('config','--unset','log.decorate')
(root/'.mailmap').write_text('Other <other@example.invalid> A <a@b>\n')
check('no-mailmap',['log','--no-mailmap']);(root/'.mailmap').unlink()
# Prefix collisions must grow the requested minimum, not print ambiguous names.
full=nodes[-1]
for nonce in range(1000000):
 payload=f'collision {nonce}'.encode()
 digest=hashlib.sha1(f'blob {len(payload)}\0'.encode()+payload).hexdigest()
 if digest[:4]==full[:4]:
  assert g('hash-object','-w','--stdin',data=payload)==digest
  break
else: raise AssertionError('deterministic collision search exhausted')
check('abbrev-collision',['log','--oneline','--abbrev=4','-n1'])
# Explicit unsupported surface rows are NOT parity and are never skipped.
for args,feature in [(['log','--graph'],'log option --graph'),(['log','main..HEAD'],'history revision expression main..HEAD'),(['log','--','dirty'],'history path limiting'),(['log','--date=relative'],'history date format relative')]:
 before=state();q=run(DEN,args)
 assert q=={'status':2,'stdout':'','stderr':f'den: not yet implemented: {feature}\n'.encode().hex()},(args,q)
 assert state()==before
 refusals.append({'args':args,'actual':q})
# Detached HEAD reads must not change provenance, and an explicit loose ancestor works.
(root/'.git/HEAD').write_text(nodes[-1]+'\n');check('detached',['log']);check('ancestry',['log','HEAD~1','-n1'])
# Unborn error bytes and no index requirements.
(root/'.git/HEAD').write_text('ref: refs/heads/unborn\n')
check('unborn-log',['log']);check('unborn-show',['show'])
summary={'tier':a.tier,'total':len(rows),'exact':len(rows)-len(failures),'failures':failures,'zero_skips':True,'rows':rows,'named_refusals':refusals,'external_clients':3}
(R/f'target/history-{a.tier}.json').write_text(json.dumps(summary,indent=2)+'\n')
print(f'history: {len(rows)-len(failures)}/{len(rows)} exact stdout/stderr/status and state; zero skips',flush=True)
raise SystemExit(bool(failures))
