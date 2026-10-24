"""Independent Git -> den -> Git index format, mutation and lock witnesses."""
import argparse,hashlib,json,os,pathlib,runpy,shutil,struct,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
args=argparse.ArgumentParser();args.add_argument('--tier',default='native');args=args.parse_args()
G=os.environ['DEN_GIT'];C=str(R/f'target/{args.tier}/index-client')
P=runpy.run_path(str(R/'tools/index-proof.py'))
O=runpy.run_path(str(R/'tools/oracle.py'))
base=R/f'target/index-integration-{args.tier}'
if base.exists():shutil.rmtree(base)
base.mkdir()
rows=[]
def run(command,cwd=None,status=0,data=None):
 p=subprocess.run(command,cwd=cwd,input=data,capture_output=True,timeout=60)
 rows.append(dict(command=command,status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex()))
 assert p.returncode==status,(command,p.returncode,p.stdout,p.stderr)
 assert b'wolf-trap' not in p.stderr
 return p.stdout

def git(repo,*argv,**kwargs):return run([G,*argv],cwd=repo,**kwargs)
def client(*argv,**kwargs):return run([C,*map(str,argv)],**kwargs)
def fresh(name):
 p=base/name;p.mkdir();git(p,'init','-q');return p

def compare_indexes(a,b):
 x,y=(a/'.git/index').read_bytes(),(b/'.git/index').read_bytes()
 xx,yy,n=P['canonical_pair'](x,y,P['proof'](a,x),P['proof'](b,y))
 assert xx==yy,('index byte mismatch',a,b,x.hex(),y.hex())
 aa=O['comparable']({'repository':O['snapshot'](a)},'loose-object-raw')
 bb=O['comparable']({'repository':O['snapshot'](b)},'loose-object-raw')
 aa['repository']['.git/index']['hex']=xx.hex()
 bb['repository']['.git/index']['hex']=yy.hex()
 assert aa==bb,('repository byte mismatch',a,b,aa,bb)
 return n

proof_rows=0
for version in (2,3,4):
 repo=fresh(f'format-{version}')
 for name in ('a','a./file','a0/file','long-name-'+'x'*200,'space name'):
  p=repo/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(name.encode()+b'\n')
 (repo/'link').symlink_to('a');os.chmod(repo/'a',0o755)
 git(repo,'-c',f'index.version={version}','add','.')
 git(repo,'add','-N','--','space name') # Existing path stays fully staged.
 git(repo,'write-tree')
 source=repo/'.git/index';original=source.read_bytes()
 result=base/f'roundtrip-{version}'
 client('roundtrip',source,result)
 assert result.read_bytes()==original,('roundtrip',version)
 # Independently build trees and compare both root OID and serialized TREE.
 out=base/f'trees-{version}'
 expected=git(repo,'write-tree')
 assert client('trees',source,out)==expected
 # Index transaction writes precisely Git's TREE without changing other bytes.
 assert client('write-tree',repo/'.git')==expected
 assert source.read_bytes()==original
 git(repo,'fsck','--full')
 # Entry modes and symlink metadata have independent OS stat witnesses.
 actual=[int(x) for x in client('stat',repo/'a','100755').splitlines()]
 actual_link=[int(x) for x in client('lstat',repo/'link').splitlines()]
 by_name={x['path_hex']:x for x in P['proof'](repo,original)}
 assert actual==by_name[b'a'.hex()]['own_worktree_stat']
 assert actual_link==by_name[b'link'.hex()]['own_worktree_stat']
 # All truncated prefixes must reject without a trap. Bound this set explicitly.
 for length in (0,3,11,12,31,32,61,62,63,len(original)-1):
  bad=base/f'truncated-{version}-{length}';bad.write_bytes(original[:length])
  client('inspect',bad,status=1)
 # Valid checksum, but an unknown extension must be refused by its name.
 unknown=original[:-20]+b'ZZZZ'+struct.pack('>I',0)
 unknown+=hashlib.sha1(unknown).digest();bad=base/f'extension-{version}';bad.write_bytes(unknown)
 client('inspect',bad,status=1)
 assert b'ZZZZ' in bytes.fromhex(rows[-1]['stderr'])

for version in (2,3,4):
 for mode in ('100644','100755'):
  a=fresh(f'git-add-{version}-{mode}');b=fresh(f'den-add-{version}-{mode}')
  for repo in (a,b):(repo/'file').write_bytes(b'payload\n')
  option='--chmod=+x' if mode=='100755' else '--chmod=-x'
  git(a,'-c',f'index.version={version}','add',option,'file')
  client('add',b/'.git',version,b/'file','file',mode)
  proof_rows+=compare_indexes(a,b)
  assert git(a,'write-tree')==client('write-tree',b/'.git')
  proof_rows+=compare_indexes(a,b)
  assert (b/'file').stat().st_mode&0o777==0o644
  # Ordinary injected failures never publish partial data and clean own lock.
  old=(b/'.git/index').read_bytes()
  for fail in ('write','sync','rename','directory-sync'):
   client('rewrite',b/'.git',version,fail,status=1)
   assert not (b/'.git/index.lock').exists()
   assert (b/'.git/index').read_bytes()==old
  # Neither process may remove somebody else's existing lock.
  lock=b/'.git/index.lock';lock.write_bytes(b'owned-by-other-writer')
  client('rewrite',b/'.git',version,status=1)
  assert lock.read_bytes()==b'owned-by-other-writer'
  lock.unlink()

# Intent-only directories are absent from trees but retained as invalid TREE nodes.
for version in (2,3,4):
 a=fresh(f'git-ita-{version}');b=fresh(f'den-ita-{version}')
 for repo in (a,b):
  (repo/'d').mkdir();(repo/'d/pending').write_bytes(b'not staged\n')
 git(a,'-c',f'index.version={version}','add','-N','d/pending')
 client('add',b/'.git',version,b/'d/pending','d/pending','100644',8192)
 assert (a/'.git/index').read_bytes()==(b/'.git/index').read_bytes()
 assert git(a,'write-tree')==client('write-tree',b/'.git')
 assert (a/'.git/index').read_bytes()==(b/'.git/index').read_bytes()
 proof_rows+=compare_indexes(a,b)
 # A nonempty root plus an ITA-only child must not publish extra loose objects.
 for repo in (a,b):(repo/'kept').write_bytes(b'kept\n')
 git(a,'add','kept')
 client('add',b/'.git',version,b/'kept','kept','100644')
 assert git(a,'write-tree')==client('write-tree',b/'.git')
 proof_rows+=compare_indexes(a,b)

# Fresh mixed index must not inherit an empty tree from an earlier write-tree.
for version in (2,3,4):
 a=fresh(f'git-fresh-mixed-{version}');b=fresh(f'den-fresh-mixed-{version}')
 for repo in (a,b):
  (repo/'d').mkdir();(repo/'d/pending').write_bytes(b'pending\n');(repo/'kept').write_bytes(b'kept\n')
 git(a,'-c',f'index.version={version}','add','-N','d/pending')
 git(a,'add','kept')
 client('add',b/'.git',version,b/'d/pending','d/pending','100644',8192)
 client('add',b/'.git',version,b/'kept','kept','100644')
 assert git(a,'write-tree')==client('write-tree',b/'.git')
 proof_rows+=compare_indexes(a,b)

# True held lock waits on our pipe; release affects only this owned process.
repo=fresh('held-lock')
p=subprocess.Popen([C,'lock',str(repo/'.git')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:
 assert p.stdout.readline()==b'locked\n'
 assert p.poll() is None
 client('rewrite',repo/'.git',2,status=1)
 assert (repo/'.git/index.lock').exists()
 p.stdin.write(b'x');p.stdin.flush()
 stdout,stderr=p.communicate(timeout=10)
 assert p.returncode==0 and not stderr,(p.returncode,stdout,stderr)
 assert not (repo/'.git/index.lock').exists()
finally:
 if p.poll() is None:p.kill();p.wait()
(R/f'target/index-integration-{args.tier}.json').write_text(json.dumps(dict(proof_rows=proof_rows,rows=rows),indent=2)+'\n')
print(f'index integration {args.tier}: {len(rows)} commands, {proof_rows} proven stat rows; roundtrip/interop/ITA/failure/lock pass')
