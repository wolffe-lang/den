"""Black-box witnesses for intent-to-add and cache-tree child order."""
import hashlib,json,os,pathlib,shutil,struct,subprocess,runpy
R=pathlib.Path(__file__).resolve().parent.parent
G=os.environ['DEN_GIT']
P=runpy.run_path(str(R/'tools/index-proof.py'))
base=R/'target/vc03-index-measure'
if base.exists():shutil.rmtree(base)
base.mkdir()
rows=[]
def run(repo,*args):
 p=subprocess.run([G,*args],cwd=repo,capture_output=True)
 rows.append(dict(repo=repo.name,args=args,status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex()))
 assert p.returncode==0,rows[-1]
 return p.stdout

def snapshot(repo):
 raw=(repo/'.git/index').read_bytes()
 items=P['entries'](raw)
 pos=12
 if items:
  last=items[-1]; start=last['offset']; pos=start+62+(2 if raw[start+60]&0x40 else 0)
  pos=raw.index(b'\0',pos)+1; pos=start+((pos-start+7)//8)*8
 ext=[]
 while pos<len(raw)-20:
  size=struct.unpack_from('>I',raw,pos+4)[0]
  ext.append(dict(name=raw[pos:pos+4].decode(),hex=raw[pos+8:pos+8+size].hex()))
  pos+=8+size
 return dict(raw_hex=raw.hex(),extensions=ext)

for name in ('ita-only','ita-mixed','ita-nested-only','ita-nested-mixed','child-order'):
 repo=base/name;repo.mkdir();run(repo,'init','-q')
 if name=='child-order':
  for folder in ('a','a.','a0'):
   (repo/folder).mkdir();(repo/folder/'file').write_text(folder+'\n')
  run(repo,'add','.')
 else:
  path='d/intent' if 'nested' in name else 'intent'
  if 'nested' in name:(repo/'d').mkdir()
  (repo/path).write_text('intent\n')
  run(repo,'add','-N',path)
  if name.endswith('mixed'):
   (repo/'kept').write_text('kept\n');run(repo,'add','kept')
 rows.append(dict(repo=name,before=snapshot(repo)))
 tree=run(repo,'write-tree').decode().strip()
 rows.append(dict(repo=name,tree=tree,after=snapshot(repo)))
 run(repo,'ls-tree','-r',tree)
repo=base/'chmod';repo.mkdir();run(repo,'init','-q')
(repo/'file').write_bytes(b'file\n');os.chmod(repo/'file',0o644)
run(repo,'add','--chmod=+x','file')
raw=(repo/'.git/index').read_bytes()
rows.append(dict(repo='chmod',proof=P['proof'](repo,raw),index=snapshot(repo)))
for number in (2,3,4):
 repo=base/f'version-{number}';repo.mkdir();run(repo,'init','-q')
 (repo/'file').write_bytes(b'file\n')
 run(repo,'-c',f'index.version={number}','add','file')
 raw=(repo/'.git/index').read_bytes()
 rows.append(dict(repo=repo.name,case='normal',version=int.from_bytes(raw[4:8],'big')))
 (repo/'intent').write_bytes(b'intent\n')
 run(repo,'-c',f'index.version={number}','add','-N','intent')
 raw=(repo/'.git/index').read_bytes()
 rows.append(dict(repo=repo.name,case='intent',version=int.from_bytes(raw[4:8],'big')))
 run(repo,'-c',f'index.version={number}','add','intent')
 raw=(repo/'.git/index').read_bytes()
 rows.append(dict(repo=repo.name,case='intent-cleared',version=int.from_bytes(raw[4:8],'big')))
out=R/'target/vc03-index-measure.json';out.write_text(json.dumps(rows,indent=2)+'\n')
for row in rows:
 if 'after' in row:print(row['repo'],row['tree'],row['after']['extensions'])
print(out)
