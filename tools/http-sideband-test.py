#!/usr/bin/env python3
"""Pinned-Git captures of HTTP receive-pack sideband rendering and hostile frames.
The peer deliberately never applies an update. Its advertisement is produced by
Git; response bytes are independently constructed from gitprotocol-pack(5).
"""
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
helpers = runpy.run_path(str(root/'tools/http-git-test.py'))
Server = helpers['Server']
git = str(Path(os.environ['DEN_GIT']).resolve())
assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == helpers['GIT_SHA256']
tier = sys.argv[1] if len(sys.argv) > 1 else 'native'
den = root/'target'/tier/'den'
out = root/'target/runs'/('http-sideband-'+tier)
out.mkdir(parents=True, exist_ok=False)
captures = []

def run(argv, cwd=None, data=b'', check=True):
    got = subprocess.run(list(map(str,argv)), cwd=cwd, input=data, capture_output=True, timeout=30)
    captures.append(dict(argv=list(map(str,argv)), cwd=str(cwd), stdin=data.hex(), exit=got.returncode,
                         stdout=got.stdout.hex(), stderr=got.stderr.hex()))
    (out/'captures.json').write_text(json.dumps(captures,indent=2)+'\n')
    if check and got.returncode: raise RuntimeError('fixture setup failed')
    return got

def pkt(data):
    assert len(data) <= 65516
    return f'{len(data)+4:04x}'.encode()+data

remote=out/'remote.git'; local=out/'local'
run([git,'init','-q','--bare',remote])
tree=run([git,'mktree'],remote).stdout.strip().decode()
commit=run([git,'commit-tree',tree,'-m','fixture'],remote).stdout.strip().decode()
for ref in ['refs/heads/main','refs/heads/topic']:
    run([git,'update-ref',ref,commit],remote)
run([git,'symbolic-ref','HEAD','refs/heads/main'],remote)
run([git,'clone','-q',remote.as_uri(),local])
advertisement=run([git,'receive-pack','--advertise-refs',remote]).stdout
assert b'side-band-64k' in advertisement
service=pkt(b'# service=git-receive-pack\n')+b'0000'
report=pkt(b'unpack ok\n')+pkt(b'ng refs/heads/topic deletion prohibited\n')+b'0000'

class Peer(Server):
    def response(self, request):
        method,target,headers,body=request
        if method == 'GET':
            content=service+advertisement
            kind='advertisement'
        else:
            self.requests.append(dict(negotiated=b'side-band-64k' in body))
            content=self.payload
            kind='result'
        return (f'HTTP/1.1 200 OK\r\nContent-Type: application/x-git-receive-pack-{kind}\r\nContent-Length: {len(content)}\r\nConnection: close\r\n\r\n'.encode()+content)

peer=Peer(out,git,dict(os.environ),'plain',None,'',lambda _:None)
rows=[]; failed=[]
try:
    cases=[
        ('http-sideband-progress', pkt(b'\x02error: denied\n')+pkt(b'\x01'+report)+b'0000', None),
        ('http-sideband-split-lines', pkt(b'\x02one')+pkt(b'\x02 line\nsecond\rthird')+pkt(b'\x01'+report)+b'0000', None),
        ('http-sideband-unknown-band', pkt(b'\x04unexpected')+b'0000', b'HTTP unknown sideband'),
        ('http-sideband-truncated-frame', b'0010\x02short', b'HTTP truncated sideband'),
        ('http-sideband-band3-mid-pack', pkt(b'\x01'+report[:8])+pkt(b'\x03fatal: deliberate stop\n')+b'0000', None),
    ]
    for name,payload,named in cases:
        peer.payload=payload
        outcomes=[]
        for binary in [git,str(den)]:
            before=len(peer.requests)
            result=run([binary,'push','-q',peer.url,':refs/heads/topic'],local,check=False)
            outcomes.append(dict(exit=result.returncode,stdout=result.stdout.hex(),stderr=result.stderr.hex(),requests=peer.requests[before:]))
        a,b=outcomes
        ok=a['exit']!=0 and b['exit']!=0 and b['requests']==[{'negotiated':True}]
        if named is None:
            ok=ok and all(a[k]==b[k] for k in ['exit','stdout','stderr'])
        else:
            ok=ok and named in bytes.fromhex(b['stderr'])
        assert run([git,'rev-parse','refs/heads/topic'],remote).stdout.strip().decode()==commit
        rows.append(dict(name=name,passed=ok,comparison='exact process' if named is None else 'both reject; den named refusal',outcomes=outcomes))
        (out/'rows.json').write_text(json.dumps(rows,indent=2)+'\n')
        print(('PASS ' if ok else 'FAIL ')+name,flush=True)
        if not ok: failed.append(name)
finally:
    peer.close()
    assert not peer.errors, 'HTTP fixture failed'
if failed: raise SystemExit('failed sideband rows: '+', '.join(failed))
