#!/usr/bin/env python3
"""Bounded deterministic black-box differential fuzz; no codec source imports."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import subprocess
import zlib
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--binary',default='target/zpipe');p.add_argument('--rounds',type=int,default=250);a=p.parse_args()
 rng=random.Random(0x76633031);work=ROOT/'target/codec-fuzz';work.mkdir(exist_ok=True);binary=ROOT/a.binary
 count=accepted=rejected=0;manifest=hashlib.sha256()
 def den(op,data,cap,level):
  nonlocal count
  (work/'input').write_bytes(data);(work/'output').unlink(missing_ok=True)
  c=subprocess.run([str(binary),op,str(work/'input'),str(work/'output'),str(cap),str(level)],capture_output=True,timeout=10)
  count+=1;manifest.update(data)
  assert c.returncode in [0,1],(count,c.returncode,c.stderr)
  if c.returncode:assert c.stderr.strip() in [b'truncated',b'bad_header',b'dictionary',b'checksum',b'invalid',b'limit'],c.stderr
  return c,(work/'output').read_bytes() if c.returncode==0 else None
 for i in range(a.rounds):
  n=rng.randrange(2049);data=rng.randbytes(n) if i%3==0 else bytes(rng.randrange(16) for _ in range(n)) if i%3==1 else bytes([i%256])*n
  level=rng.choice([0,1,6,9]);raw=bool(i%2);window=-15 if raw else 15
  c=zlib.compressobj(level,zlib.DEFLATED,window,8,rng.choice([zlib.Z_DEFAULT_STRATEGY,zlib.Z_FIXED,zlib.Z_HUFFMAN_ONLY]))
  split=rng.randrange(n+1);encoded=c.compress(data[:split])+c.flush(zlib.Z_SYNC_FLUSH)+c.compress(data[split:])+c.flush()
  result,out=den('inflate_raw' if raw else 'inflate',encoded,n,1);assert result.returncode==0 and out==data
  result,enc=den('deflate_raw' if raw else 'deflate',data,n*2+100,1);assert result.returncode==0 and zlib.decompress(enc,window)==data
  for variant in range(3):
   mutated=bytearray(encoded)
   if variant==0:mutated=mutated[:rng.randrange(len(mutated))]
   elif variant==1:
    for _ in range(rng.randrange(1,5)):mutated[rng.randrange(len(mutated))]^=1<<rng.randrange(8)
   else:mutated=bytearray(rng.randbytes(rng.randrange(100)))
   result,out=den('inflate_raw' if raw else 'inflate',mutated,65536,1)
   try:
    d=zlib.decompressobj(window);expected=d.decompress(mutated,65537);valid=d.eof and len(expected)<=65536
   except zlib.error:valid=False
   if result.returncode==0:
    assert valid and out==expected,(i,variant,result.stdout,result.stderr,bytes(mutated).hex());accepted+=1
   else:
    assert not valid,(i,variant,result.stderr,bytes(mutated).hex());rejected+=1
  if i%50==0:print('fuzz',i,'calls',count,flush=True)
 summary=dict(seed=0x76633031,rounds=a.rounds,calls=count,mutated_accepted=accepted,mutated_rejected=rejected,input_sha256=manifest.hexdigest(),zlib=zlib.ZLIB_RUNTIME_VERSION)
 (work/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
if __name__=='__main__':main()
