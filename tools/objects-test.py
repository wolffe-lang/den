"""Independent black-box interop, malformed rows, atomic failure and race witnesses."""
import argparse,concurrent.futures,hashlib,json,os,pathlib,shutil,subprocess,time,zlib
R=pathlib.Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser();p.add_argument('--tier',choices=['native','release'],required=True);a=p.parse_args()
D=R/f'target/{a.tier}/den'; C=R/f'target/{a.tier}/object-client'; G=pathlib.Path(os.environ['DEN_GIT'])
root=R/f'target/objects-{a.tier}'
if root.exists(): shutil.rmtree(root)
root.mkdir();repo=root/'repo';repo.mkdir();gd=repo/'.git';rows=[]
def run(exe,args,data=b'',cwd=repo,expect=0,env=None):
 r=subprocess.run([str(exe),*map(str,args)],input=data,capture_output=True,cwd=cwd,env=env,timeout=60)
 assert r.returncode==expect,(exe,args,r.returncode,r.stdout,r.stderr)
 return r
run(D,['init','-q'])
def oid(kind,body):return hashlib.sha1(kind.encode()+b' '+str(len(body)).encode()+b'\0'+body).hexdigest()
def location(id):return gd/'objects'/id[:2]/id[2:]
def object_raw(id):
 decoder=zlib.decompressobj();raw=decoder.decompress(location(id).read_bytes());assert decoder.eof and not decoder.unused_data
 assert hashlib.sha1(raw).hexdigest()==id
 return raw
# Both directions, independent contents and independently framed identities.
for n,body in enumerate([b'',b'abc',b'a\0b',bytes(range(256)),b'zero'*8192,bytes(range(255,-1,-1))*300]):
 expected=oid('blob',body)
 for exe in (D,G):
  result=run(exe,['hash-object','-w','--stdin'],body).stdout.strip().decode();assert result==expected
  assert object_raw(result)==b'blob '+str(len(body)).encode()+b'\0'+body
  assert run(D,['cat-file','-p',result]).stdout==body
  assert run(G,['cat-file','-p',result]).stdout==body
 rows.append(f'blob-{n}: bidirectional bytes/oid')
blob=oid('blob',b'abc');empty=run(D,['mktree']).stdout.strip().decode()
# Mixed modes, nested tree, directory-aware ordering and a raw invalid-UTF8 basename.
entries=[(b'100755',b'blob',blob,b'a0'),(b'040000',b'tree',empty,b'a'),(b'100644',b'blob',blob,b'a.c'),(b'120000',b'blob',blob,b'\xff')]
text=b''.join(mode+b' '+kind+b' '+id.encode()+b'\t'+name+b'\0' for mode,kind,id,name in entries)
tree=run(D,['mktree','-z'],text).stdout.strip().decode();assert run(G,['mktree','-z'],text).stdout.strip().decode()==tree
assert run(D,['cat-file','-p',tree]).stdout==run(G,['cat-file','-p',tree]).stdout
parents=[]
for msg in [b'root',b'second\n',b'merge\n']:
 args=['commit-tree',tree]+sum((['-p',id] for id in parents),[])
 commit=run(D,args,msg).stdout.strip().decode();assert run(G,args,msg).stdout.strip().decode()==commit
 assert run(D,['cat-file','-p',commit]).stdout==run(G,['cat-file','-p',commit]).stdout
 parents.append(commit)
(gd/'refs/heads/main').write_text(commit+'\n')
unknown=(f'tree {tree}\nauthor Den Tester <den@example.invalid> 1700000000 +0000\ncommitter Den Tester <den@example.invalid> 1700000000 +0000\nencoding ISO-8859-1\ngpgsig one\n two\n \nx-unknown a\n\n'.encode()+b'\xff\n')
unknown_id=run(G,['hash-object','--literally','-t','commit','-w','--stdin'],unknown).stdout.strip().decode()
assert run(D,['cat-file','-p',unknown_id]).stdout==unknown
for msg in [b'',b'tag',b'tag\n',b'\xff\x00']:
 tag=(f'object {commit}\ntype commit\ntag v1\ntagger Den Tester <den@example.invalid> 1700000000 +0000\n\n'.encode()+msg)
 id=run(D,['mktag'],tag).stdout.strip().decode();assert run(G,['mktag'],tag).stdout.strip().decode()==id
 assert run(D,['cat-file','-p',id]).stdout==tag
rows.append('trees/commits/tags: modes/nesting/order/parents/continuations/binary messages')
# Same invalid byte through stdin/-F/mktag, two locales and explicit encoding.
initial_config=(gd/'config').read_bytes();(repo/'message-ff').write_bytes(b'\xff')
for locale,encoding in [('C',None),('C.UTF-8',None),('C','ISO-8859-1')]:
 e=dict(os.environ,LC_ALL=locale)
 (gd/'config').write_bytes(initial_config+(b'\n[i18n]\ncommitEncoding=ISO-8859-1\n' if encoding else b''))
 for args,data in [(['commit-tree',tree],b'\xff'),(['commit-tree',tree,'-F','message-ff'],b''),(['mktag'],f'object {commit}\ntype commit\ntag t\ntagger A <a> 1700000000 +0000\n\n'.encode()+b'\xff')]:
  actual=run(D,args,data,env=e);expected=run(G,args,data,env=e)
  assert (actual.stdout,actual.stderr)==(expected.stdout,expected.stderr),(locale,encoding,args,actual.stderr,expected.stderr)
(gd/'config').write_bytes(initial_config)
rows.append('encoding: stdin/-F/mktag; C/C.UTF-8/ISO-8859-1 byte-and-warning parity')
run(G,['fsck','--full'])
# Exclusive install, each injected phase, existing valid/corrupt objects, races.
payload=root/'payload';payload.write_bytes(b'atomic payload')
expected=oid('blob',payload.read_bytes())
for failure in ('write','sync','install'):
 r=run(C,['write',gd,'blob',payload,failure],expect=1);assert r.stderr==b'io\n'
 assert not location(expected).exists()
 assert not list((gd/'objects').glob('*/tmp_den_*'))
run(C,['write',gd,'blob',payload,'directory-sync'],expect=1)
assert object_raw(expected).endswith(payload.read_bytes())
assert not list((gd/'objects').glob('*/tmp_den_*'))
run(C,['write',gd,'blob',payload,'write']) # preexisting wins before failpoint
location(expected).chmod(0o644);location(expected).write_bytes(b'corrupt')
run(C,['write',gd,'blob',payload,''],expect=1)
assert location(expected).read_bytes()==b'corrupt';location(expected).unlink()
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
 results=list(pool.map(lambda _:run(C,['write',gd,'blob',payload,'']).stdout,range(16)))
assert len(set(results))==1 and results[0].strip().decode()==expected
assert not list((gd/'objects').glob('*/tmp_den_*'));assert object_raw(expected).endswith(payload.read_bytes())
assert location(expected).stat().st_mode&0o777==0o444
rows.append('atomic: write/sync/install/parent-sync, existing valid/corrupt, 16 racing writers')
# Independent malformed corpus: require named errors, never trap or signal.
malformed=[]
for raw,tag in [(b'blob 1\0',b'bad_size'),(b'blob 0\0x',b'bad_size'),(b'blob -1\0',b'bad_size'),(b'blob 01\0x',b'bad_size'),(b'blob x\0',b'bad_size'),(b'bad 0\0',b'bad_header'),(b'blob\0',b'bad_header'),(b'blob \0',b'bad_header'),(b'blob 0',b'bad_header'),(b'blob 999999999999999999999999\0',b'limit')]:
 malformed.append((zlib.compress(raw),hashlib.sha1(raw).hexdigest(),tag))
valid=zlib.compress(b'blob 3\0abc');bid=oid('blob',b'abc')
for n in range(min(8,len(valid))):malformed.append((valid[:n],bid,b'truncated' if n<2 else None))
malformed.extend([(valid+b'x',bid,b'trailing'),(valid[:-1]+bytes([valid[-1]^1]),bid,b'checksum'),(zlib.compress(b'blob 3\0abd'),bid,b'bad_oid'),(b'\x00\x00',bid,b'bad_header')])
for i,(encoded,id,tag) in enumerate(malformed):
 path=location(id);path.parent.mkdir(exist_ok=True)
 if path.exists():path.chmod(0o644)
 path.write_bytes(encoded)
 r=run(C,['read',gd,id,128],expect=1)
 assert b'trap' not in r.stderr and (tag is None or r.stderr==tag+b'\n'),(i,tag,r.stderr)
 path.unlink()
rows.append(f'malformed: {len(malformed)} header/length/truncation/trailing/checksum/oid rows')
# Inclusive output boundary, zero, negative, and a compression bomb bounded to 64.
for body,cap,status in [(b'',0,0),(b'abc',3,0),(b'abc',2,1),(b'abc',-1,1),(b'x'*100000,64,1)]:
 id=oid('blob',body);path=location(id);path.parent.mkdir(exist_ok=True)
 if path.exists():path.chmod(0o644)
 path.write_bytes(zlib.compress(b'blob '+str(len(body)).encode()+b'\0'+body))
 r=run(C,['read',gd,id,cap],expect=status)
 if status:assert r.stderr in (b'limit\n',b'invalid\n')
# deterministic prefix collision, no fabricated names: two real SHA-1 objects
seen={};collision=None
for n in range(5000):
 body=str(n).encode();id=oid('blob',body);key=id[:4]
 if key in seen:collision=(seen[key],(id,body));break
 seen[key]=(id,body)
assert collision
for id,body in collision:
 path=location(id);path.parent.mkdir(exist_ok=True)
 if path.exists():path.chmod(0o644)
 path.write_bytes(zlib.compress(b'blob '+str(len(body)).encode()+b'\0'+body))
assert run(C,['lookup',gd,collision[0][0][:4]],expect=1).stderr==b'ambiguous\n'
for option in ('-p','-t','-s'):
 actual=run(D,['cat-file',option,collision[0][0][:4]],expect=128)
 expected=run(G,['cat-file',option,collision[0][0][:4]],expect=128)
 assert (actual.stdout,actual.stderr)==(expected.stdout,expected.stderr)
run(C,['lookup',gd,'ffffffffff'],expect=1)
rows.append('caps: inclusive/negative/bomb; real SHA-1 ambiguous prefix')
# Reject all unsupported repository/compression formats before writes.
config=(gd/'config').read_bytes()
for extra,name in [(b'\n[extensions]\nobjectFormat=sha256\n','extensions.objectformat'),(b'\n[extensions]\nunknown=true\n','extensions.unknown'),(b'\n[core]\nrepositoryFormatVersion=9\n','core.repositoryformatversion'),(b'\n[core]\ncompression=9\n','core.compression')]:
 (gd/'config').write_bytes(config+extra)
 before={str(p):p.read_bytes() for p in (gd/'objects').glob('*/*') if p.is_file()}
 r=run(D,['hash-object','-w','--stdin'],b'no writes please',expect=2);assert name.encode() in r.stderr
 assert before=={str(p):p.read_bytes() for p in (gd/'objects').glob('*/*') if p.is_file()}
(gd/'config').write_bytes(config)
# Gitfile discovery, plain/bare init exact files and bytes.
linked=root/'gitfile';linked.mkdir();(linked/'.git').write_text('gitdir: ../repo/.git\n')
assert run(D,['cat-file','-t',tree],cwd=linked).stdout==b'tree\n'
for bare in (False,True):
 d=root/('bare' if bare else 'plain');d.mkdir()
 args=['init','-q']+(['--bare'] if bare else [])
 run(D,args,cwd=d);dr=d if bare else d/'.git'
 ours={str(p.relative_to(dr)):p.read_bytes() for p in dr.rglob('*') if p.is_file()}
 shutil.rmtree(d);d.mkdir();run(G,args,cwd=d)
 expected_files={str(p.relative_to(dr)):p.read_bytes() for p in dr.rglob('*') if p.is_file()}
 assert ours==expected_files
# Read-only index: unknown extension, checksum, extended/stage flags rejected.
indexed=root/'indexed';shutil.copytree(R/'target/corpus/two',indexed)
idx=indexed/'.git/index';original=idx.read_bytes()
assert run(D,['write-tree'],cwd=indexed).stdout==run(G,['write-tree'],cwd=indexed).stdout
assert idx.read_bytes()==original
for variant in ('unknown','checksum','unmerged','extended'):
 raw=bytearray(original[:-20])
 if variant=='unknown':raw.extend(b'ZZZZ'+(0).to_bytes(4,'big'))
 if variant=='unmerged':raw[12+60]|=0x10
 if variant=='extended':raw[12+60]|=0x40
 checksum=hashlib.sha1(raw).digest()
 if variant=='checksum':checksum=bytes([checksum[0]^1])+checksum[1:]
 idx.write_bytes(raw+checksum)
 before={str(p):p.read_bytes() for p in (indexed/'.git/objects').glob('*/*') if p.is_file()}
 result=run(D,['write-tree'],cwd=indexed,expect=2 if variant=='unknown' else 128)
 assert b'trap' not in result.stderr
 assert before=={str(p):p.read_bytes() for p in (indexed/'.git/objects').glob('*/*') if p.is_file()}
idx.write_bytes(original)
rows.append('index: Git v2 byte-preserving read; unknown extension/checksum/stage/extended refusal')
# Permission failure is run as an unprivileged owned child inside the container.
# No host identity or process is touched.
permission=root/'permission';permission.mkdir();run(D,['init','-q'],cwd=permission)
if os.geteuid()==0:
 child=subprocess.run([str(C),'write',str(permission/'.git'),'blob',str(payload),''],cwd=permission,capture_output=True,preexec_fn=lambda:os.setuid(65534),timeout=30)
 assert child.returncode==1 and child.stderr==b'denied\n',child.stderr
else:
 (permission/'.git/objects').chmod(0o555)
 try:assert run(C,['write',permission/'.git','blob',payload,''],cwd=permission,expect=1).stderr==b'denied\n'
 finally:(permission/'.git/objects').chmod(0o755)
assert not list((permission/'.git/objects').glob('*/*'))
# Interrupt only this process, before publication; an abrupt process death is
# allowed to leave its exclusive temporary file, never a truncated final oid.
interrupt=root/'interrupt';interrupt.mkdir();run(D,['init','-q'],cwd=interrupt)
large=root/'interrupt-data';large.write_bytes(os.urandom(50_000_000))
child=subprocess.Popen([str(C),'write',str(interrupt/'.git'),'blob',str(large),''],cwd=interrupt,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
deadline=time.monotonic()+45
observed=False
while child.poll() is None and time.monotonic()<deadline:
 for temporary in (interrupt/'.git/objects').glob('*/tmp_den_*'):
  try:observed=temporary.stat().st_size>0
  except FileNotFoundError:pass
  if observed:break
 if observed:break
 time.sleep(0.001)
if child.poll() is None:child.terminate()
out,err=child.communicate(timeout=30)
assert observed and child.returncode==-15,(observed,child.returncode,err)
for path in (interrupt/'.git/objects').glob('*/*'):
 if path.name.startswith('tmp_den_'):continue
 raw=zlib.decompress(path.read_bytes());assert hashlib.sha1(raw).hexdigest()==path.parent.name+path.name
large.unlink()
rows.append('permissions: unprivileged child refused; owned interrupted writer leaves no partial final object')
rows.append('repository: plain/bare init exact files; gitfile; unsupported prewrite refusal')
summary=dict(tier=a.tier,rows=rows,malformed=len(malformed),status='PASS')
(R/f'target/objects-{a.tier}.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
