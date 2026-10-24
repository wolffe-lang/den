"""Regress exclusive temporary-name reuse after successful object publication."""
import argparse,concurrent.futures,json,os,pathlib,shutil,subprocess
R=pathlib.Path(__file__).resolve().parent.parent
ap=argparse.ArgumentParser();ap.add_argument('--rounds',type=int,default=40);ap.add_argument('--label',default='current');ap.add_argument('--tier',choices=['native','release'],default='native');a=ap.parse_args()
assert 1 <= a.rounds <= 1000 and a.label and all(c.isalnum() or c=='-' for c in a.label)
base=R/f'target/object-temp-race-{a.label}'
if base.exists():shutil.rmtree(base)
base.mkdir();repo=base/'repo'
subprocess.run([str(R/f'target/{a.tier}/den'),'init','-q',str(repo)],check=True)
client=R/f'target/{a.tier}/object-client';payload=base/'payload';rows=[]
for iteration in range(a.rounds):
 payload.write_bytes(f'temporary ownership {iteration}\n'.encode()*64)
 def writer(number):
  p=subprocess.run([str(client),'write',str(repo/'.git'),'blob',str(payload),''],capture_output=True,timeout=30)
  return dict(writer=number,status=p.returncode,stdout=p.stdout.hex(),stderr=p.stderr.hex())
 with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:result=list(pool.map(writer,range(32)))
 rows.append(dict(iteration=iteration,results=result))
 bad=[x for x in result if x['status']!=0]
 if bad:
  print('FAIL temporary ownership round',iteration,bad,flush=True);break
 assert len({x['stdout'] for x in result})==1
 assert not list((repo/'.git/objects').glob('*/tmp_den_*'))
 if iteration%10==0:print('temporary ownership round',iteration,'PASS',flush=True)
(R/f'target/object-temp-race-{a.label}.json').write_text(json.dumps(rows,indent=2)+'\n')
failed=any(x['status']!=0 for row in rows for x in row['results'])
print('object temporary race:',len(rows),'rounds',32*len(rows),'writers','FAIL' if failed else 'PASS')
raise SystemExit(failed)
