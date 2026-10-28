"""Retain all final top-level component JSON and complete main-case captures."""
import gzip,hashlib,json,pathlib,tarfile
R=pathlib.Path(__file__).resolve().parents[2];T=R/'target';O=R/'notes/vc12-evidence'
index={}
for p in sorted(T.glob('*.json')):
 raw=p.read_bytes();dest=O/('component-'+p.name+'.gz')
 with dest.open('wb') as f:
  with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as z:z.write(raw)
 index[str(p.relative_to(R))]=dict(capture=dest.name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
cases=json.loads((R/'tests/cases.json').read_text())
main={}
with tarfile.open(O/'main-captures.tar.gz','w:gz') as tar:
 for case in cases:
  for name in ('before.json','git.json','den.json'):
   p=T/'runs'/case['name']/name
   assert p.is_file(),p
   raw=p.read_bytes();key=f'{case["name"]}/{name}'
   main[key]=dict(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
   tar.add(p,arcname=key,recursive=False)
(O/'additional-captures.json').write_text(json.dumps(dict(components=index,main=main),indent=2)+'\n')
print('retained',len(index),'component JSON captures;',len(cases),'main cases;',len(main),'complete main process/state captures',flush=True)
