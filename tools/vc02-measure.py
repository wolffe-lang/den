"""Black-box plumbing census; no implementation source access."""
import os,pathlib,subprocess,json,hashlib
R=pathlib.Path(__file__).resolve().parent.parent
G=os.environ['DEN_GIT']; root=R/'target/vc02-measure';root.mkdir(exist_ok=True)
def run(cwd,args,data=b''):
 p=subprocess.run([G,*args],cwd=cwd,input=data,capture_output=True)
 return dict(args=args,status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex())
rows=[]
for name,args in [('plain',[]),('bare',['--bare']),('quiet',['-q']),('branch',['-b','topic'])]:
 d=root/name;d.mkdir(exist_ok=True); rows.append(run(d,['init','--template='+os.environ['DEN_EMPTY_TEMPLATE'],*args]))
 gd=d if name=='bare' else d/'.git'
 rows.append(dict(inventory=name,dirs=sorted(str(p.relative_to(gd)) for p in gd.rglob('*') if p.is_dir()),files={str(p.relative_to(gd)):dict(hex=p.read_bytes().hex(),mode=p.stat().st_mode&0o777) for p in gd.rglob('*') if p.is_file()}))
 rows.append(run(d,['init','--template='+os.environ['DEN_EMPTY_TEMPLATE'],*args]))
d=root/'plain'
for kind,body in [('blob',b''),('blob',b'abc'),('blob',bytes(range(256))),('tree',b''),('commit',b''),('tag',b'')]: rows.append(run(d,['hash-object','-w','--stdin','-t',kind],body))
empty='4b825dc642cb6eb9a060e54bf8d69288fbee4904'
for args,body in [([empty],b''),([empty],b'abc'),([empty,'-m','abc'],b''),([empty,'-m',''],b''),([empty,'-m','one','-m','two'],b'')]:
 a=run(d,['commit-tree',*args],body); rows.append(a)
 if a['status']==0: rows.append(run(d,['cat-file','-p',bytes.fromhex(a['stdout']).decode().strip()]))
for op in ('-p','-t','-s'):
 for obj in ('missing','0000000000000000000000000000000000000000','f2ba',empty): rows.append(run(d,['cat-file',op,obj]))
for body in (b'',b'object '+b'e69de29bb2d1d6434b8b29ae775ad8c2e48c5391'+b'\ntype blob\ntag t\ntagger A <a> 1700000000 +0000\n\n', b'bad\n'): rows.append(run(d,['mktag'],body))
rows.append(run(d,['hash-object','missing-file']))
rows.append(run(d,['hash-object','--stdin','-t','bad'],b'a'))
rows.append(run(d,['write-tree']))
print(json.dumps(rows,indent=2))
