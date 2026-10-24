#!/usr/bin/env python3
"""Measure shipped one-byte lazy lookahead against a lane-owned greedy variant."""
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import time
import zlib
ROOT=Path(__file__).resolve().parents[1]
def main():
 work=ROOT/'target/codec-strategy';work.mkdir(exist_ok=True);variant=work/'src'
 if variant.exists():shutil.rmtree(variant)
 shutil.copytree(ROOT/'src',variant)
 path=variant/'zlib/deflate.lu';original=path.read_text();needle='if found.value >= 3 && found.value < 258 && end - pos > 3 {'
 assert original.count(needle)==1
 path.write_text(original.replace(needle,'if found.value < 0 && found.value < 258 && end - pos > 3 {'))
 subprocess.run([str(ROOT/'.wolf-bin/wolf'),'build','--release','--deny-warnings',str(variant/'zpipe.lu'),'-o',str(work/'greedy')],check=True)
 rng=random.Random(0x1951)
 words=[rng.randbytes(rng.randrange(3,40)) for _ in range(300)]
 synthetic=b''.join(words[rng.randrange(len(words))] for _ in range(300000))
 datasets={'text':(b'The quick brown wolf keeps its history in the den.\n'*200000),'phrases':synthetic}
 rows=[]
 for name,data in datasets.items():
  inp=work/'input';inp.write_bytes(data)
  for strategy,binary in [('lazy',ROOT/'target/release/zpipe'),('greedy',work/'greedy')]:
   times=[]
   for _ in range(3):
    t=time.monotonic();c=subprocess.run([str(binary),'deflate',str(inp),str(work/'output'),str(len(data)*2+100),'1'],capture_output=True,timeout=60);times.append(time.monotonic()-t)
    assert c.returncode==0 and not c.stderr,(strategy,c.stderr)
    encoded=(work/'output').read_bytes();assert zlib.decompress(encoded)==data
   row=dict(dataset=name,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),strategy=strategy,encoded=len(encoded),seconds=times,median_seconds=statistics.median(times[1:]));rows.append(row);print(json.dumps(row),flush=True)
 (work/'summary.json').write_text(json.dumps(rows,indent=2)+'\n')
 # Deliberately keep the variant source for measurement reproducibility.
if __name__=='__main__':main()
