#!/usr/bin/env python3
"""Three whole-object file-driver runs; warm-up excluded. Sizes are byte exact."""
import hashlib
import json
from pathlib import Path
import random
import statistics
import subprocess
import time
import zlib
ROOT=Path(__file__).resolve().parents[1]
def main():
 work=ROOT/'target/codec-bench';work.mkdir(exist_ok=True);n=100_000_000;results=[]
 load=Path('/proc/loadavg').read_text().strip();print('load',load,flush=True)
 for name in ['random','zero']:
  payload=random.Random(0x76633031).randbytes(n) if name=='random' else bytes(n)
  digest=hashlib.sha256(payload).hexdigest();plain=work/(name+'.raw');plain.write_bytes(payload)
  c=zlib.compressobj(1);oracle=c.compress(payload)+c.flush();packed=work/(name+'.zlib');packed.write_bytes(oracle)
  for tier in ['native','release']:
   binary=ROOT/'target'/tier/'zpipe'
   for op,source,expected in [('deflate',plain,None),('inflate',packed,payload)]:
    rows=[];out=work/(name+'-'+tier+'-'+op)
    for repetition in range(3):
     timing=work/'time.txt';start=time.monotonic()
     p=subprocess.run(['/usr/bin/time','-f','%e %M','-o',str(timing),str(binary),op,str(source),str(out),str(2*n+100000),'1'],capture_output=True,timeout=300)
     elapsed=time.monotonic()-start;assert p.returncode==0 and not p.stderr,(op,p.returncode,p.stderr)
     data=out.read_bytes();assert (zlib.decompress(data) if op=='deflate' else data)==payload
     seconds,rss=timing.read_text().split();rows.append(dict(repetition=repetition,seconds=float(seconds),wall_seconds=elapsed,rss_kib=int(rss),size=len(data)))
     print(name,tier,op,repetition,rows[-1],flush=True)
    seconds=statistics.median(r['wall_seconds'] for r in rows[1:]);rss=max(r['rss_kib'] for r in rows[1:])
    results.append(dict(input=name,sha256=digest,bytes=n,tier=tier,operation=op,median_seconds=seconds,MB_per_second=n/seconds/1e6,peak_rss_kib=rss,size=rows[-1]['size'],zlib_level1_size=len(oracle),ratio=rows[-1]['size']/len(oracle) if op=='deflate' else None,runs=rows))
    out.unlink()
  plain.unlink();packed.unlink()
 summary=dict(host='hasu',cpus='0-5',load=load,bytes=n,method='whole-object file driver including read/write; 3 runs, first warm-up',zlib=zlib.ZLIB_RUNTIME_VERSION,results=results)
 (work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 assert all(r['ratio'] is None or r['ratio']<=1.25 for r in results)
 print(json.dumps(summary),flush=True)
if __name__=='__main__':main()
