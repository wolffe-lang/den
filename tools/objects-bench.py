"""Whole-object release write/read RSS and scaling, three runs (first warmup)."""
import hashlib,json,os,pathlib,random,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent;root=R/'target/objects-bench';root.mkdir(exist_ok=True)
D=R/'target/release/den';G=os.environ['DEN_GIT'];rows=[]
for pattern in ('random','zero'):
 for size in (50_000_000,100_000_000):
  payload=root/'payload';rng=random.Random(121)
  h=hashlib.sha1(b'blob '+str(size).encode()+b'\0')
  with payload.open('wb') as f:
   remaining=size
   while remaining:
    n=min(1_000_000,remaining);b=rng.randbytes(n) if pattern=='random' else bytes(n)
    f.write(b);h.update(b);remaining-=n
  id=h.hexdigest()
  for rep in range(3):
   repo=root/'repo'
   if repo.exists():shutil.rmtree(repo)
   repo.mkdir();subprocess.run([str(D),'init','-q'],cwd=repo,check=True)
   for action,args in [('write',['hash-object','-w',str(payload)]),('read',['cat-file','-p',id])]:
    stats=root/'time'
    p=subprocess.run(['/usr/bin/time','-f','%e %M','-o',str(stats),str(D),*args],cwd=repo,stdout=subprocess.PIPE if action=='write' else subprocess.DEVNULL,stderr=subprocess.PIPE)
    assert p.returncode==0,p.stderr
    if action=='write':assert p.stdout==id.encode()+b'\n'
    elapsed,rss=stats.read_text().split();rows.append(dict(pattern=pattern,size=size,rep=rep,action=action,seconds=float(elapsed),rss_kib=int(rss)))
    print(rows[-1],flush=True)
   encoded=repo/'.git/objects'/id[:2]/id[2:]
   den_size=encoded.stat().st_size
   encoded.unlink();subprocess.run([G,'hash-object','-w',str(payload)],cwd=repo,check=True,stdout=subprocess.DEVNULL)
   git_size=encoded.stat().st_size
   rows[-2]['encoded_bytes']=den_size;rows[-2]['git_bytes']=git_size
   assert den_size/git_size<=1.25
  payload.unlink()
for pattern in ('random','zero'):
 for action in ('write','read'):
  def peak(size):return max(r['rss_kib'] for r in rows if r['pattern']==pattern and r['action']==action and r['size']==size and r['rep']>0)
  assert peak(100_000_000)<1_258_291,('RSS exceeds predicted 1.2GiB',pattern,action,peak(100_000_000))
  assert peak(100_000_000)/peak(50_000_000)<2.7,('nonlinear RSS',pattern,action)
(root/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
print('PASS 50/100-MB linear-memory gate, three runs, warmup excluded')
