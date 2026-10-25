"""Measure Git-produced index extensions and den's named reader policy."""
import hashlib,json,os,pathlib,shutil,struct,subprocess
R=pathlib.Path(__file__).resolve().parent.parent;G=os.environ['DEN_GIT'];C=str(R/'target/native/index-client')
base=R/'target/index-extension-census'
if base.exists():shutil.rmtree(base)
base.mkdir();rows=[]
def git(repo,*args,data=None):
 p=subprocess.run([G,*args],cwd=repo,input=data,capture_output=True)
 rows.append(dict(repo=repo.name,args=args,status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex()))
 return p

def fresh(name,source='two'):
 p=base/name;shutil.copytree(R/'target/corpus'/source,p,symlinks=True);return p

def extensions(raw):
 assert raw[:4]==b'DIRC' and hashlib.sha1(raw[:-20]).digest()==raw[-20:]
 version,count=struct.unpack_from('>II',raw,4);pos=12;end=len(raw)-20
 for _ in range(count):
  start=pos;flags=struct.unpack_from('>H',raw,pos+60)[0];pos+=62
  if flags&0x4000:pos+=2
  if version==4:
   while raw[pos]&128:pos+=1
   pos+=1
  pos=raw.index(b'\0',pos,end)+1
  if version!=4:pos=start+((pos-start+7)//8)*8
 out=[]
 while pos<end:
  size=struct.unpack_from('>I',raw,pos+4)[0];out.append(dict(name=raw[pos:pos+4].decode(),payload_hex=raw[pos+8:pos+8+size].hex()));pos+=8+size
 assert pos==end
 return out

def record(repo):
 raw=(repo/'.git/index').read_bytes();ext=extensions(raw)
 p=subprocess.run([C,'inspect',str(repo/'.git/index')],capture_output=True)
 result=dict(repo=repo.name,index_hex=raw.hex(),extensions=ext,den_status=p.returncode,den_stdout=p.stdout.hex(),den_stderr=p.stderr.hex())
 rows.append(result);print(repo.name,[x['name'] for x in ext],p.returncode,repr(p.stderr))
 known={'TREE','REUC'};unsupported=[x['name'] for x in ext if x['name'] not in known]
 if unsupported:
  assert p.returncode==1 and any(x.encode() in p.stderr for x in unsupported)
 else:
  assert p.returncode==0
  output=base/(repo.name+'-roundtrip');q=subprocess.run([C,'roundtrip',str(repo/'.git/index'),str(output)],capture_output=True);assert q.returncode==0,q.stderr
  assert output.read_bytes()==raw
repo=fresh('resolve-undo')
ids=[git(repo,'hash-object','-w','--stdin',data=text).stdout.strip().decode() for text in (b'base\n',b'ours\n',b'theirs\n')]
data=b'0 '+b'0'*40+b'\ta.txt\n'+b''.join(f'100644 {id} {stage}\ta.txt\n'.encode() for stage,id in enumerate(ids,1))
assert git(repo,'update-index','--index-info',data=data).returncode==0
(repo/'a.txt').write_bytes(b'resolved\n');assert git(repo,'add','a.txt').returncode==0;record(repo)
for name,args,source in [('untracked',['update-index','--untracked-cache'],'two'),('fsmonitor',['update-index','--fsmonitor'],'two'),('offsets',['-c','index.threads=2','update-index','--force-write-index'],'thousand'),('split',['update-index','--split-index'],'two')]:
 repo=fresh(name,source);git(repo,*args);record(repo)
repo=fresh('sparse')
for d in ('keep','omit'):
 (repo/d).mkdir();(repo/d/'file').write_text(d+'\n')
git(repo,'add','.');git(repo,'commit','-qm','directories');git(repo,'sparse-checkout','init','--cone','--sparse-index');git(repo,'sparse-checkout','set','keep');record(repo)
(R/'target/index-extension-census.json').write_text(json.dumps(rows,indent=2)+'\n')
print('index extension census: all produced records preserved or refused by exact extension name')
