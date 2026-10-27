"""Independent public-API records; no fixture-specific production exceptions."""
import argparse, hashlib, json, pathlib, random, subprocess
R=pathlib.Path(__file__).resolve().parent.parent
p=argparse.ArgumentParser(); p.add_argument('--tier',default='native'); a=p.parse_args()
root=R/f'target/sequencer-api-{a.tier}'; root.mkdir(parents=True,exist_ok=True)
exe=R/f'target/{a.tier}/sequencer-client'
rng=random.Random(8056)
rows=[]
for n in range(128):
    lines=[]
    for i in range(n%17):
        name=hashlib.sha1(f'{n}:{i}'.encode()).hexdigest()[:rng.randrange(4,41)]
        lines.append(f'pick {name} subject {i}\n'.encode())
    body=b''.join(lines)
    data=b'# ignored comment\n\n'+body
    path=root/'input'; path.write_bytes(data)
    got=subprocess.run([exe,path],capture_output=True)
    assert (got.returncode,got.stdout,got.stderr)==(0,body,b''),(n,got)
    assert path.read_bytes()==data
    rows.append(dict(name=f'roundtrip-{n}',sha256=hashlib.sha256(data).hexdigest(),status=0))
invalid=[b'exec anything\n',b'pick ../HEAD title\n',b'pick 123 title\n',b'pick '+b'a'*41+b' title\n',b'pick ABCD title\n',b'pick abcd title\0\n',b'pick abcd title\r\n',b'pick abcd \xff\n']
for n,data in enumerate(invalid):
    path=root/'input'; path.write_bytes(data)
    got=subprocess.run([exe,path],capture_output=True)
    assert got.returncode==2 and got.stdout==b'',(n,got)
    assert path.read_bytes()==data
    rows.append(dict(name=f'reject-{n}',sha256=hashlib.sha256(data).hexdigest(),status=2))
(root/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
print(f'sequencer API: {len(rows)}/{len(rows)} exact; input immutable')
