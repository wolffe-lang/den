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
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

root = Path(__file__).resolve().parent.parent
helpers = runpy.run_path(str(root/'tools/http-git-test.py'))
Server = helpers['Server']
git = str(Path(os.environ['DEN_GIT']).resolve())
assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == helpers['GIT_SHA256']
tier = sys.argv[1] if len(sys.argv) > 1 else 'native'
den = root/'target'/tier/'den'
selected = sys.argv[2] if len(sys.argv) > 2 else ''
if selected and not selected.startswith('http-sideband-'): raise SystemExit('invalid sideband selector')
if '/' in selected or '..' in selected: raise SystemExit('invalid sideband selector')
out = root/'target/runs'/('http-sideband-'+tier+('-'+selected if selected else ''))
out.mkdir(parents=True, exist_ok=False)
captures = []

def identity(pid):
    try:
        fields=Path(f'/proc/{pid}/stat').read_text().rpartition(')')[2].split()
        return dict(parent=int(fields[1]), session=int(fields[3]), start=int(fields[19]))
    except (FileNotFoundError, ProcessLookupError):
        return None

def owned_session(pid):
    # Each command starts its own session. This inventories only that command's
    # descendants; signals below always target one captured PID, never a group.
    found={}
    for path in Path('/proc').iterdir():
        if not path.name.isdecimal(): continue
        child=int(path.name); info=identity(child)
        if info and info['session']==pid and child!=pid: found[child]=info['start']
    return found

def run(argv, cwd=None, data=b'', check=True, timeout_review=False):
    started=time.monotonic()
    process=subprocess.Popen(list(map(str,argv)),cwd=cwd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,start_new_session=True)
    timed_out=False
    descendants={}
    try:
        stdout,stderr=process.communicate(data,timeout=30)
    except subprocess.TimeoutExpired:
        timed_out=True
        assert process.poll() is None, 'oracle was not waiting at the bound'
        descendants=owned_session(process.pid)
        process.kill()  # This exact spawned Git PID only.
        process.wait(timeout=5)
        for pid,start in descendants.items():
            current=identity(pid)
            if current and current['start']==start:
                try: os.kill(pid,signal.SIGTERM)
                except ProcessLookupError: pass
        stdout,stderr=process.communicate(timeout=5)
        deadline=time.monotonic()+5
        while owned_session(process.pid) and time.monotonic()<deadline: time.sleep(0.02)
        assert not owned_session(process.pid), 'stray oracle descendant after timeout'
        assert identity(process.pid) is None and process.returncode is not None, 'oracle was not reaped'
    elapsed=time.monotonic()-started
    got=SimpleNamespace(returncode=None if timed_out else process.returncode,stdout=stdout,stderr=stderr,
                        timed_out=timed_out,elapsed=elapsed)
    captures.append(dict(argv=list(map(str,argv)),cwd=str(cwd),stdin=data.hex(),exit=got.returncode,
                         stdout=stdout.hex(),stderr=stderr.hex(),elapsed=elapsed,
                         observation='ORACLE-TIMEOUT' if timed_out else 'completed',pid=process.pid,
                         reaped=process.returncode is not None,descendants=list(descendants),strays=[]))
    (out/'captures.json').write_text(json.dumps(captures,indent=2)+'\n')
    if timed_out:
        if not timeout_review: raise RuntimeError('unexpected process timeout')
        print('ORACLE-TIMEOUT http-sideband-truncated-frame bound=30s git-reaped=yes strays=0',flush=True)
    if check and got.returncode!=0: raise RuntimeError('fixture setup failed')
    return got

def state(path):
    result={}
    for entry in sorted(path.rglob('*')):
        name=entry.relative_to(path).as_posix()
        if entry.is_symlink(): result[name]=dict(link=os.readlink(entry))
        elif entry.is_file(): result[name]=dict(mode=entry.stat().st_mode&0o777,bytes=entry.read_bytes().hex())
        elif entry.is_dir(): result[name]=dict(directory=True,mode=entry.stat().st_mode&0o777)
    return result

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
        ('http-sideband-empty-lines', pkt(b'\x02\n\r\n')+pkt(b'\x01'+report)+b'0000', None),
        ('http-sideband-band3-after-progress', pkt(b'\x02working')+pkt(b'\x03fatal: stop')+b'0000', None),
        ('http-sideband-unknown-band', pkt(b'\x04unexpected')+b'0000', b'HTTP unknown sideband'),
        ('http-sideband-band3-mid-pack', pkt(b'\x01'+report[:8])+pkt(b'\x03fatal: deliberate stop\n')+b'0000', None),
        ('http-sideband-truncated-frame', b'0010\x02short', b'HTTP truncated sideband'),
    ]
    if selected and selected not in [case[0] for case in cases]: raise RuntimeError('unknown sideband selector')
    for name,payload,named in cases:
        if selected and selected != name: continue
        peer.payload=payload
        outcomes=[]
        for binary in [git,str(den)]:
            before=len(peer.requests)
            snapshot=dict(remote=state(remote),local=state(local))
            result=run([binary,'push','-q',peer.url,':refs/heads/topic'],local,check=False,
                       timeout_review=name=='http-sideband-truncated-frame' and binary==git)
            after=dict(remote=state(remote),local=state(local))
            outcomes.append(dict(exit=result.returncode,stdout=result.stdout.hex(),stderr=result.stderr.hex(),requests=peer.requests[before:],
                                 timed_out=result.timed_out,elapsed=result.elapsed,before=snapshot,after=after))
        a,b=outcomes
        ok=b['exit'] is not None and b['exit']!=0 and not b['timed_out'] and b['elapsed']<10 and b['before']==b['after'] and b['requests']==[{'negotiated':True}]
        if name=='http-sideband-truncated-frame':
            ok=ok and a['timed_out'] and a['before']==a['after'] and b['exit']==2 and bytes.fromhex(b['stderr'])==b'den: wire: Unsupported(push: Unsupported(HTTP truncated sideband))\n'
            comparison='reviewed ORACLE-TIMEOUT; den exact refusal and unchanged complete state; not parity'
        elif named is None:
            ok=ok and not a['timed_out'] and all(a[k]==b[k] for k in ['exit','stdout','stderr'])
            comparison='exact process'
        else:
            ok=ok and not a['timed_out'] and a['exit']!=0 and named in bytes.fromhex(b['stderr'])
            comparison='both reject; den named refusal'
        assert run([git,'rev-parse','refs/heads/topic'],remote).stdout.strip().decode()==commit
        rows.append(dict(name=name,passed=ok,comparison=comparison,outcomes=outcomes))
        (out/'rows.json').write_text(json.dumps(rows,indent=2)+'\n')
        verdict='REVIEW ' if ok and name=='http-sideband-truncated-frame' else 'PASS ' if ok else 'FAIL '
        print(verdict+name,flush=True)
        if not ok: failed.append(name)
finally:
    peer.close()
    assert not peer.errors, 'HTTP fixture failed'
if failed: raise SystemExit('failed sideband rows: '+', '.join(failed))
