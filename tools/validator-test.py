"""Independent graph fixtures, exact fsck bytes/status and complete immutability."""
import argparse,base64,hashlib,json,os,pathlib,runpy,shutil,struct,subprocess,zlib
R=pathlib.Path(__file__).resolve().parent.parent
G=str(next((R/'target/oracle').glob('*/root/opt/git/bin/git')))
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest()=='c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
os.environ['GIT_EXEC_PATH']=str(pathlib.Path(G).parent.parent/'libexec/git-core')
a=argparse.ArgumentParser();a.add_argument('--tier',default='native');a.add_argument('--run',default='final');args=a.parse_args()
D=R/'target'/args.tier/'den';root=R/'target'/('validator-'+args.tier+'-'+args.run);root.mkdir()
rows=[];clients=[];contents={};states={}
decode_batch=runpy.run_path(str(R/'tools/pack-batch.py'))['decode']
def snap(p):
 out={}
 for f in sorted(p.rglob('*')):
  data=os.fsencode(os.readlink(f)) if f.is_symlink() else f.read_bytes() if f.is_file() else b''
  key=hashlib.sha256(data).hexdigest();contents[key]=base64.b64encode(data).decode();out[str(f.relative_to(p))]=[f.lstat().st_mode,key]
 key=hashlib.sha256(json.dumps(out,sort_keys=True).encode()).hexdigest();states[key]=out;return key
def git(p,*args,data=None):
 q=subprocess.run([G,*args],cwd=p,input=data,capture_output=True);assert q.returncode==0,(args,q.stderr);return q.stdout

def compare(p,label,options=()):
 before=snap(p);results=[]
 for tool in (G,D):
  q=subprocess.run([str(tool),'fsck','--full','--no-progress',*options],cwd=p,capture_output=True)
  results.append(dict(stdout=q.stdout.hex(),stderr=q.stderr.hex(),status=q.returncode,state=snap(p)))
 row=dict(label=label,before=before,git=results[0],den=results[1]);rows.append(row)
 assert results[0]==results[1],row
 assert results[0]['state']==before,(label,'mutation')
 print('VALIDATOR',label,results[0]['status'],flush=True)
try:
 for shape in ('root','linear','octopus'):
  p=root/shape;p.mkdir();git(p,'init','-q','-b','main','--template=')
  tree=git(p,'mktree',data=b'').strip().decode();parents=[]
  for i in range(1 if shape=='root' else 12):
   selected=parents[-1:] if shape=='linear' else []
   oid=git(p,'commit-tree',tree,*[x for parent in selected for x in ('-p',parent)],data=f'commit {i}\n'.encode()).strip().decode();parents.append(oid)
  if shape=='octopus':
   oid=git(p,'commit-tree',tree,*[x for parent in parents for x in ('-p',parent)],data=b'merge\n').strip().decode()
  git(p,'update-ref','refs/heads/main',oid)
  git(p,'commit-graph','write','--reachable','--no-progress')
  compare(p,shape+' valid')
  graph=(p/'.git/objects/info/commit-graph').read_bytes();chunks={}
  for i in range(graph[6]):
   tag,offset=struct.unpack_from('>4sQ',graph,8+12*i);chunks[tag]=offset
  count=struct.unpack_from('>I',graph,chunks[b'OIDF']+1020)[0]
  assert count=={'root':1,'linear':12,'octopus':13}[shape]
  ids=[graph[chunks[b'OIDL']+20*i:chunks[b'OIDL']+20*(i+1)].hex() for i in range(count)]
  before=snap(p);listing=('\n'.join(ids)+'\n').encode()
  q=subprocess.run([G,'cat-file','--batch'],cwd=p,input=listing,capture_output=True)
  g=dict(stdout=q.stdout.hex(),stderr=q.stderr.hex(),status=q.returncode,state=snap(p));assert q.returncode==0 and g['state']==before
  expected=[]
  for name,(kind,body) in decode_batch(q.stdout,ids).items():
   assert kind=='commit';headers=body.split(b'\n\n',1)[0].splitlines()
   tree=next(x[5:].decode() for x in headers if x.startswith(b'tree '))
   stamp=next(x.rsplit(b' ',2)[1].decode() for x in headers if x.startswith(b'committer '))
   expected.append(f'{name} {tree} {stamp} {sum(x.startswith(b"parent ") for x in headers)}\n')
  q=subprocess.run([str(D.with_name('housekeeping-client')),str(p/'.git'),'graph'],cwd=p,capture_output=True)
  d=dict(stdout=q.stdout.hex(),stderr=q.stderr.hex(),status=q.returncode,state=snap(p));clients.append(dict(shape=shape,before=before,git=g,den=d))
  assert q.returncode==0 and q.stdout==''.join(expected).encode() and q.stderr==b'' and d['state']==before,clients[-1]
  mutations=[('checksum',len(graph)-1,1,False),('signature',0,1,True),('version',4,1,True),('hash',5,1,True),('tree',chunks[b'CDAT'],1,True),('timestamp',chunks[b'CDAT']+35,1,True),('oid',chunks[b'OIDL']+19,1,True),('fanout',chunks[b'OIDF']+1023,1,True)]
  if shape=='root':mutations += [('parent',chunks[b'CDAT']+20,1,True),('v1 ignored with v2',chunks[b'CDAT']+31,4,True)]
  for label,pos,mask,checksum in mutations:
   q=root/(shape+'-'+str(len(rows)));shutil.copytree(p,q);data=bytearray(graph);data[pos]^=mask
   if checksum:data[-20:]=hashlib.sha1(data[:-20]).digest()
   (q/'.git/objects/info/commit-graph').write_bytes(data);compare(q,shape+' '+label)
 p=root/'diagnostic-base';p.mkdir();git(p,'init','-q','-b','main','--template=')
 (p/'file').write_bytes(b'content\n');git(p,'add','file');git(p,'commit','-qm','diagnostic')
 blob=git(p,'rev-parse','HEAD:file').strip().decode();tree=git(p,'rev-parse','HEAD^{tree}').strip().decode();head=git(p,'rev-parse','HEAD').strip().decode()
 for label,target,replacement in [('missing-blob',blob,None),('missing-tree',tree,None),('missing-head',head,None),('empty-blob',blob,b''),('zlib-blob',blob,b'not-zlib'),('hash-blob',blob,zlib.compress(b'blob 4\0oops'))]:
  q=root/label;shutil.copytree(p,q);f=q/'.git/objects'/target[:2]/target[2:]
  if replacement is None:f.unlink()
  else:f.write_bytes(replacement)
  compare(q,label,('--no-dangling',))
 for label,ref,value in [('bad-head','HEAD',blob),('bad-branch','refs/heads/main',blob),('missing-ref','refs/tags/missing','1'*40)]:
  q=root/label;shutil.copytree(p,q);f=q/'.git'/ref;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(value+'\n');compare(q,label,('--no-dangling',))
 q=root/'wrong-tree';shutil.copytree(p,q)
 body=f'tree {blob}\nauthor A <a@b> 1700000000 +0000\ncommitter A <a@b> 1700000000 +0000\n\nx\n'.encode()
 git(q,'hash-object','-w','-t','commit','--stdin',data=body);compare(q,'wrong-tree',('--no-dangling',))
 q=root/'wrong-entry';shutil.copytree(p,q);git(q,'hash-object','-w','-t','tree','--stdin',data=b'100644 wrong\0'+bytes.fromhex(head));compare(q,'wrong-entry',('--no-dangling',))
finally:
 (R/'target'/('validator-'+args.tier+'-'+args.run+'.json')).write_text(json.dumps(dict(rows=rows,clients=clients,states=states,contents=contents)))
print('VALIDATOR COMPLETE',len(rows),'exact immutable commands')
