"""Pinned Git interop: every object listed in each packed fixture, exact raw bytes."""
import argparse, hashlib, json, os, pathlib, runpy, shutil, subprocess, zlib, struct
R=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(); p.add_argument('--tier',default='native'); a=p.parse_args()
G=os.environ['DEN_GIT']; client=R/f'target/{a.tier}/pack-client'
out=R/f'target/pack-interop-{a.tier}'; out.mkdir(parents=True,exist_ok=True)
pack_fixture=runpy.run_path(str(R/'tools/packed-fixture.py'))['pack_fixture']
rows=[]; inventories=[]
def entry_types(path):
 data=path.read_bytes(); pos=12; counts={str(t):0 for t in (1,2,3,4,6,7)}
 for _ in range(struct.unpack('>I',data[8:12])[0]):
  b=data[pos]; kind=(b>>4)&7; pos+=1; counts[str(kind)]+=1
  while b&128: b=data[pos];pos+=1
  if kind==7: pos+=20
  elif kind==6:
   b=data[pos];pos+=1
   while b&128: b=data[pos];pos+=1
  inflater=zlib.decompressobj(); inflater.decompress(data[pos:]); assert inflater.eof
  pos=len(data)-len(inflater.unused_data)
 assert pos==len(data)-20
 return counts

def git(repo,*args,data=None):
 q=subprocess.run([G,*args],cwd=repo,input=data,capture_output=True)
 assert q.returncode==0,(args,q.stdout,q.stderr)
 return q.stdout
sources=sorted(p.parent for p in (R/'target/corpus').rglob('.git') if p.is_dir())
assert len(sources)>=16,len(sources)
# Additional repeated-data history forces real oracle delta heuristics.
seed=out/'generated'
if seed.exists(): shutil.rmtree(seed)
seed.mkdir();git(seed,'init','-q')
for i in range(30):
 content=(b'common line content\n'*2000)+f'change {i}\n'.encode()
 (seed/'a').write_bytes(content);git(seed,'add','a');git(seed,'commit','-qm',f'commit {i}')
git(seed,'tag','-am','annotated','v1')
sources.append(seed)
for i,source in enumerate(sources):
 for form in ('ofs','ref'):
  repo=out/f'{i}-{form}'
  if repo.exists(): shutil.rmtree(repo)
  shutil.copytree(source,repo,symlinks=True)
  before=git(repo,'cat-file','--batch-all-objects','--batch-check=%(objectname) %(objecttype) %(objectsize)').splitlines()
  if i==len(sources)-1 and form=='ofs':
   git(repo,'-c','gc.writeCommitGraph=false','-c','gc.packRefs=false','-c','repack.writeBitmaps=false','gc')
  packs=pack_fixture(G,repo)
  if form=='ref':
   # The same oracle writes REF_DELTA when --delta-base-offset is absent.
   names=b''.join(line.split()[0]+b'\n' for line in before)
   pack=git(repo,'pack-objects','--stdout','--window=50','--depth=40',data=names)
   d=repo/'.git/objects/pack'
   for old in d.iterdir(): old.unlink()
   target=d/('pack-'+pack[-20:].hex()+'.pack');target.write_bytes(pack)
   git(repo,'index-pack','--index-version=2',str(target))
   packs=1
  after=git(repo,'cat-file','--batch-all-objects','--batch-check=%(objectname) %(objecttype) %(objectsize)').splitlines()
  assert set(before)==set(after),(source,form,'lost namespace')
  verify=[]
  for idx in (repo/'.git/objects/pack').glob('*.idx'):
   v=git(repo,'verify-pack','-v',str(idx));verify.extend(v.decode().splitlines())
  fsck=subprocess.run([G,'fsck','--full','--no-reflogs'],cwd=repo,capture_output=True)
  assert fsck.returncode==0,(source,fsck.stdout,fsck.stderr)
  counts={str(t):0 for t in (1,2,3,4,6,7)}
  for path in (repo/'.git/objects/pack').glob('*.pack'):
   for kind,count in entry_types(path).items(): counts[kind]+=count
  inventories.append(dict(fixture=source.name,form=form,packs=packs,objects=len(after),entry_types=counts,verify_pack=verify,fsck_stdout=fsck.stdout.hex(),fsck_stderr=fsck.stderr.hex()))
  for line in after:
   name,kind,size=line.decode().split()
   body=git(repo,'cat-file',kind,name)
   q=subprocess.run([str(client),str(repo/'.git'),name,'16777216'],capture_output=True,timeout=60)
   expected=f'{kind} {size} {name}\n'.encode()+body
   good=q.returncode==0 and q.stdout==expected and not q.stderr
   rows.append(dict(fixture=source.name,form=form,oid=name,kind=kind,size=int(size),equal=good,expected_sha256=hashlib.sha256(expected).hexdigest(),actual_sha256=hashlib.sha256(q.stdout).hexdigest(),status=q.returncode,stderr=q.stderr.hex()))
   assert good,rows[-1]
  print('pack interop',source.name,form,len(after),flush=True)
report=dict(tier=a.tier,objects=len(rows),exact=sum(r['equal'] for r in rows),zero_skips=True,inventories=inventories,rows=rows)
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
assert all(sum(inv['entry_types'][kind] for inv in inventories)>0 for kind in ('1','2','3','4','6','7')), 'oracle type coverage incomplete'
assert any(len(line.split())==7 for inv in inventories for line in inv['verify_pack']),'oracle produced no deltas'
print(f'pack interop: {len(rows)}/{len(rows)} exact raw objects; {len(inventories)} packed fixtures; zero skips',flush=True)
