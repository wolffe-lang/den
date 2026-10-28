"""Independent publication, corruption, depth and scope witnesses; no parity inflation."""
import argparse,base64,hashlib,json,os,pathlib,random,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
G=str(next((R/'target/oracle').glob('*/root/opt/git/bin/git')))
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest()=='c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
os.environ['GIT_EXEC_PATH']=str(pathlib.Path(G).parent.parent/'libexec/git-core')
a=argparse.ArgumentParser();a.add_argument('--tier',default='native');args=a.parse_args()
D=R/'target'/args.tier/'den'; C=D.with_name('pack-write-client'); root=R/'target'/('pack-adversarial-'+args.tier)
if root.exists():shutil.rmtree(root)
root.mkdir(); rows=[]; cases=[]; contents={};states={}
def state(p):
 out={}
 for f in sorted(p.rglob('*')):
  data=os.fsencode(os.readlink(f)) if f.is_symlink() else f.read_bytes() if f.is_file() else b''
  digest=hashlib.sha256(data).hexdigest();contents[digest]=base64.b64encode(data).decode()
  out[str(f.relative_to(p))]={'mode':f.lstat().st_mode,'content':digest}
 key=hashlib.sha256(json.dumps(out,sort_keys=True).encode()).hexdigest();states[key]=out;return key
def run(cmd,p,data=None):
 q=subprocess.run(list(map(str,cmd)),cwd=p,input=data,capture_output=True)
 row={'args':list(map(str,cmd)),'out':q.stdout.hex(),'err':q.stderr.hex(),'status':q.returncode,'state':state(p)};rows.append(row);return row
def ok(cmd,p,data=None):
 q=run(cmd,p,data);assert q['status']==0,q;return bytes.fromhex(q['out'])
def refuse(p,cmd,feature):
 before=state(p);q=run([D]+cmd,p)
 assert q['status']==2 and feature.encode() in bytes.fromhex(q['err']) and q['state']==before,(cmd,q)
 cases.append({'case':feature,'classification':'named-refusal'})
src=R/'target'/('pack-write-'+args.tier)/'corpus/two'
try:
 # Fixed entropy and successive equal-size edits force a real chain, not a vacuous depth bound.
 p=root/'chain';p.mkdir();ok([G,'init','-q'],p)
 rng=random.Random(130013); body=bytearray(rng.randbytes(4096));names=[]
 for n in range(75):
  body[n*32:n*32+32]=rng.randbytes(32)
  names.append(ok([G,'hash-object','-w','--stdin'],p,bytes(body)).strip())
 listing=root/'chain.names';listing.write_bytes(b'\n'.join(names)+b'\n')
 for mode in ('ofs','ref'):
  dest=root/('chain-'+mode);shutil.copytree(p,dest)
  name=ok([C,dest/'.git',listing,mode],dest).decode().strip();idx=dest/'.git/objects/pack'/('pack-'+name+'.idx')
  output=ok([G,'verify-pack','-v',idx],dest).decode()
  depths=[int(line.split()[5]) for line in output.splitlines() if len(line.split())==7]
  assert depths and max(depths)==50,(mode,max(depths,default=0))
  for id in names:
   path=dest/'.git/objects'/id[:2].decode()/id[2:].decode();path.unlink()
  ok([G,'fsck','--full'],dest)
  for id in names:assert ok([G,'cat-file','blob',id.decode()],dest)==ok([G,'cat-file','blob',id.decode()],p)
  cases.append({'case':'chain-'+mode,'classification':'interop','objects':len(names),'max_depth':max(depths)})
 # Prepare a den pair with retained loose copies, so corruption cannot hide behind them.
 good=root/'valid';shutil.copytree(src,good)
 ids=ok([G,'cat-file','--batch-all-objects','--batch-check=%(objectname)'],good)
 namesfile=root/'valid.names';namesfile.write_bytes(ids)
 name=ok([C,good/'.git',namesfile,'ofs'],good).decode().strip()
 stem='pack-'+name
 mutations=['idx-checksum','pack-checksum','entry-crc','missing-idx','missing-pack']
 for mutation in mutations:
  p=root/mutation;shutil.copytree(good,p)
  idx=p/'.git/objects/pack'/(stem+'.idx');pack=idx.with_suffix('.pack')
  if mutation=='missing-idx':idx.unlink()
  elif mutation=='missing-pack':pack.unlink()
  elif mutation=='pack-checksum':
   b=bytearray(pack.read_bytes());b[12]^=1;pack.chmod(0o644);pack.write_bytes(b)
  else:
   b=bytearray(idx.read_bytes());b[-1 if mutation=='idx-checksum' else 1032+20*len(ids.splitlines())]^=1
   if mutation=='entry-crc':b[-20:]=hashlib.sha1(b[:-20]).digest()
   idx.chmod(0o644);idx.write_bytes(b)
  before=state(p); oracle=run([G,'verify-pack',idx],p);assert oracle['status']!=0
  q=run([D,'verify-pack',idx],p);assert q['status']!=0 and q['state']==before
  q=run([D,'fsck','--full'],p);assert q['status']!=0 and q['state']==before
  cases.append({'case':mutation,'classification':'corruption-rejected'})
 for suffix,feature in [('.keep','pack .keep policy'),('.bitmap','pack bitmap'),('.mtimes','cruft packs')]:
  p=root/('scope-'+suffix[1:]);shutil.copytree(good,p);(p/'.git/objects/pack'/(stem+suffix)).write_bytes(b'')
  refuse(p,['pack-objects','-q','.git/objects/pack/pack'],feature)
 p=root/'midx';shutil.copytree(good,p);(p/'.git/objects/pack/multi-pack-index').write_bytes(b'')
 refuse(p,['pack-objects','-q','.git/objects/pack/pack'],'multi-pack-index')
 p=root/'config';shutil.copytree(src,p);ok([G,'config','pack.window','11'],p)
 refuse(p,['pack-objects','-q','.git/objects/pack/pack'],'pack-objects configuration pack.window')
 p=root/'foreign-temp';shutil.copytree(src,p)
 (p/'.git/objects/pack'/('tmp_den_'+name+'.idx')).write_bytes(b'foreign')
 before=state(p);q=run([C,p/'.git',namesfile,'ofs'],p)
 assert q['status']==1 and q['state']==before,q
 cases.append({'case':'foreign-temp','classification':'immutable-failure'})
 for command in [['gc'],['repack','-d'],['pack-objects','--stdout'],['pack-objects','--thin'],['pack-objects','--window=11'],['pack-objects','--depth=51'],['pack-objects','--write-bitmap-index'],['pack-objects','--cruft'],['pack-objects','--honor-pack-keep']]:
  refuse(good,command,command[0] if command[0] in ('gc','repack') else ' '.join(command))
finally:
 (R/'target'/('pack-adversarial-'+args.tier+'.json')).write_text(json.dumps({'rows':rows,'cases':cases,'states':states,'contents':contents}))
print('PACK ADVERSARIAL COMPLETE',len(cases),'cases',len(rows),'process captures')
