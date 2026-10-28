"""Independent spot-check of the retained main `stash` case (not the harness).

From main-captures.tar.gz: inflate den's and git's loose W object, recompute
its SHA-1, require refs/stash to name it in both, parents [HEAD, I], the exact
message "On main: scratch" with no final LF, I's message with one, and the
reflog record's message.
"""
import hashlib,json,pathlib,tarfile,zlib
O=pathlib.Path(__file__).resolve().parent
with tarfile.open(O/'main-captures.tar.gz') as tar:
 runs={tool:json.loads(tar.extractfile(f'stash/{tool}.json').read()) for tool in ('git','den')}
def obj(repo,hexid):
 raw=zlib.decompress(bytes.fromhex(repo[f'.git/objects/{hexid[:2]}/{hexid[2:]}']['hex']))
 assert hashlib.sha1(raw).hexdigest()==hexid
 head,body=raw.split(b'\0',1);return head,body
ids={}
for tool,run in runs.items():
 repo=run['repository']
 w=bytes.fromhex(repo['.git/refs/stash']['hex']).decode().strip()
 head,body=obj(repo,w);assert head.startswith(b'commit ')
 lines=body.split(b'\n');parents=[l[7:].decode() for l in lines if l.startswith(b'parent ')]
 assert len(parents)==2 and body.endswith(b'\n\nOn main: scratch'),body
 _,ibody=obj(repo,parents[1]);assert ibody.endswith(b'\n\nindex on main: '+ibody.split(b'index on main: ')[1]) and ibody.endswith(b'\n')
 log=bytes.fromhex(repo['.git/logs/refs/stash']['hex'])
 assert log.startswith(b'0'*40+b' '+w.encode()+b' ') and log.endswith(b'\tOn main: scratch\n'),log
 assert bytes.fromhex(run['stdout'])==b'Saved working directory and index state On main: scratch\n'
 ids[tool]=(w,parents)
assert ids['git']==ids['den'],ids
print('spot-check: main stash W',ids['den'][0],'parents',ids['den'][1],'identical in git and den; SHA-1 recomputed from stored bytes')
