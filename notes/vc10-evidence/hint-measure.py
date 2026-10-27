import hashlib,json,os,pathlib,subprocess
repo=pathlib.Path('target/revision-native/loose')
G=os.environ['DEN_GIT']
def g(*args,data=None):
 q=subprocess.run([G,*args],cwd=repo,input=data,capture_output=True);assert q.returncode==0,q.stderr;return q.stdout.strip().decode()
head=g('rev-parse','HEAD');tree=g('rev-parse','HEAD^{tree}')
commit=g('hash-object','-w','-t','commit','--stdin',data=f'tree {tree}\nauthor A <a@b> 946684800 +0530\ncommitter C <c@d> 1700000000 -0230\n\nfirst line\nsecond line\n\nbody\n'.encode())
tag=g('hash-object','-w','-t','tag','--stdin',data=f'object {head}\ntype commit\ntag hint-tag\ntagger A <a@b> 946684800 +0530\n\nmessage\n'.encode())
for kind,id in [('commit',commit),('tag',tag)]:
 for n in range(2000000):
  data=f'hint collision {kind} {n}\n'.encode();oid=hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest()
  if oid[:4]==id[:4]:g('hash-object','-w','--stdin',data=data);break
 else:raise AssertionError('collision search exhausted')
 for cmd in [['rev-parse','--verify',id[:4]],['log',id[:4]],['cat-file','-t',id[:4]]]:
  q=subprocess.run([G,*cmd],cwd=repo,capture_output=True)
  print(json.dumps(dict(kind=kind,args=cmd,status=q.returncode,stdout=q.stdout.decode(),stderr=q.stderr.decode())))
