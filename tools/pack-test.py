#!/usr/bin/env python3
"""Independent pack/idx writer from gitformat-pack; no implementation oracle code."""
import argparse, hashlib, json, pathlib, random, shutil, struct, subprocess, zlib
P = argparse.ArgumentParser(); P.add_argument('--tier', default='native'); A = P.parse_args()
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'target' / ('pack-' + A.tier); OUT.mkdir(parents=True, exist_ok=True)
CLIENT = ROOT / 'target' / A.tier / 'pack-client'
rows = []
def sha(b): return hashlib.sha1(b).digest()
def oid(kind, b): return sha(kind.encode() + b' ' + str(len(b)).encode() + b'\0' + b)
def u32(n): return struct.pack('>I', n)
def size(n):
    b = bytearray()
    while n >= 128: b.append((n & 127) | 128); n >>= 7
    b.append(n); return bytes(b)
def header(t, n):
    b = bytearray([(t << 4) | (n & 15)]); n >>= 4
    while n: b[-1] |= 128; b.append(n & 127); n >>= 7
    return bytes(b)
def ofs(n):
    b = [n & 127]
    while n >> 7:
        n = (n >> 7) - 1; b.append(128 | (n & 127))
    return bytes(reversed(b))
def insert(base, target):
    return size(len(base)) + size(len(target)) + b''.join(bytes([len(target[i:i+127])]) + target[i:i+127] for i in range(0, len(target), 127))
def make(entries, large=False):
    data = bytearray(b'PACK' + u32(2) + u32(len(entries))); records = []; offsets = []
    for t, body, raw, reference in entries:
        pos = len(data); offsets.append(pos)
        if t == 6: reference = ofs(pos - offsets[reference])
        encoded = header(t, len(raw)) + reference + zlib.compress(raw)
        data.extend(encoded); records.append((oid('blob', body), zlib.crc32(encoded), pos))
    pack = bytes(data) + sha(data)
    records.sort(); fan = b''.join(u32(sum(x[0][0] <= n for x in records)) for n in range(256))
    offsets_table = b''.join(u32(0x80000000+i if large else x[2]) for i,x in enumerate(records))
    extra = b''.join(struct.pack('>Q', x[2]) for x in records) if large else b''
    idx = b'\xfftOc' + u32(2) + fan + b''.join(x[0] for x in records) + b''.join(u32(x[1]) for x in records) + offsets_table + extra + pack[-20:]
    return pack, idx + sha(idx), records

def repo(name, pack, idx):
    r = OUT / name
    if r.exists(): shutil.rmtree(r)
    d = r / 'objects' / 'pack'; d.mkdir(parents=True)
    (r/'HEAD').write_text('ref: refs/heads/main\n'); (r/'config').write_text('[core]\nrepositoryformatversion = 0\nbare = true\n')
    (d/'pack-fixture.pack').write_bytes(pack); (d/'pack-fixture.idx').write_bytes(idx)
    return r

def check(name, r, body, expected=None, cap=16777216, name_id=None):
    full = oid('blob', body).hex(); arg = name_id or full
    p = subprocess.run([str(CLIENT), str(r), arg, str(cap)], capture_output=True, timeout=60)
    good = (p.returncode == 0 and p.stdout == f'blob {len(body)} {full}\n'.encode() + body and not p.stderr) if expected is None else (p.returncode == 1 and expected.encode() in p.stderr and not p.stdout)
    rows.append(dict(name=name, ok=good, code=p.returncode, stdout_sha256=hashlib.sha256(p.stdout).hexdigest(), stderr=p.stderr.decode(errors='replace')))
    if not good: print(name, p.returncode, p.stdout[:200], p.stderr, flush=True)

def resign_idx(idx): return idx[:-20] + sha(idx[:-20])
base = b'abcdef' * 20000
middle = base[:40000] + b'NEW' + base[40003:]
last = b'last body'
entries = [(3,base,base,b''), (6,middle,insert(base,middle),0), (7,last,insert(middle,last),oid('blob',middle))]
pack, idx, records = make(entries)
r = repo('ofs-ref', pack, idx)
for body in (base,middle,last):
    check('read-'+oid('blob',body).hex(),r,body)
    check('prefix-'+oid('blob',body).hex(),r,body,name_id=oid('blob',body).hex()[:7])
check('inclusive-cap',r,last,cap=len(last)); check('output-cap',r,last,expected='pack object size limit',cap=len(last)-1)
pack2, idx2, _ = make(entries, large=True)
r2 = repo('large-offset-table',pack2,idx2)
for body in (base,middle,last): check('large-offset-'+oid('blob',body).hex(),r2,body)
# Forward REF chain uses identity, not physical order.
p,i,_ = make([(7,last,insert(base,last),oid('blob',base)),(3,base,base,b'')])
check('forward-ref',repo('forward-ref',p,i),last)
# Copy with omitted size is 65536, with noncontiguous optional offset bytes.
copybase = bytes(range(256)) * 300
copybody = copybase[:65536]
p,i,_ = make([(3,copybase,copybase,b''),(6,copybody,size(len(copybase))+size(len(copybody))+b'\x80',0)])
check('copy-default-65536',repo('copy-default',p,i),copybody)
p,i,_ = make([(7,last,insert(base,last),oid('blob',base))])
check('thin-ref',repo('thin',p,i),last,expected='thin pack')
# Self-reference has no valid body identity in the pack; the cycle must be bounded.
p,i,_ = make([(7,last,insert(last,last),oid('blob',last))])
check('cycle',repo('cycle',p,i),last,expected='pack delta cycle')
chain = [(3,b'0',b'0',b'')]
for n in range(1,66):
    b = str(n).encode(); prev = str(n-1).encode(); chain.append((6,b,insert(prev,b),n-1))
p,i,_ = make(chain)
check('depth-limit',repo('depth',p,i),b'65',expected='pack delta depth limit')
# An incompressible object crosses many 64-KiB windows, not a full-pack allocation.
big = random.Random(901).randbytes(300000)
p,i,_ = make([(3,big,big,b'')]); check('window-crossing',repo('windows',p,i),big)
# Trailer failures do not disappear when resolving a prefix.
for name,p,i,reason in [('short-pack',pack[:11],idx,'pack truncated'),('bad-pack-trailer',pack[:-1]+bytes([pack[-1]^1]),idx,'pack checksum'),('bad-idx-trailer',pack,idx[:-1]+bytes([idx[-1]^1]),'pack index checksum'),('short-idx',pack,idx[:1020],'pack index truncated')]:
    rr=repo(name,p,i); check(name,rr,last,expected=reason); check(name+'-prefix',rr,last,expected=reason,name_id=oid('blob',last).hex()[:7])
# Re-sign malformed indexes so structure/CRC guards, not just SHA, must fire.
for name,offset,value,reason in [('fanout',8,u32(999),'pack index fanout'),('crc',1032+20*3,b'\0'*4,'pack entry CRC'),('offset',1032+24*3+4*next(n for n,x in enumerate(records) if x[2]==12),u32(13),'pack index offsets'),('pack-binding',len(idx)-40,b'\0'*20,'pack index binding')]:
    bad=idx[:offset]+value+idx[offset+len(value):]; rr=repo(name,pack,resign_idx(bad))
    target = next(b for b in (base,middle,last) if oid('blob',b)==records[0][0]) if name=='crc' else last
    check(name,rr,target,expected=reason)
# Corrupt the delta instruction and repair every outer integrity layer.
for name,delta,reason in [('zero-op',size(len(base))+b'\x00\x00','pack delta invalid'),('truncated-copy',size(len(base))+b'\x01\x91','pack delta invalid'),('base-size',b'\x01\x01\x01x','pack delta invalid')]:
    p,i,_=make([(3,base,base,b''),(6,last,delta,0)]); check(name,repo(name,p,i),last,expected=reason)
# Correct pack+idx bytes but advertised object identity lies.
p,i,_=make([(3,last,b'wrong',b'')]); check('object-identity',repo('identity',p,i),last,expected='pack object identity')
# Multiple packs, loose precedence, .keep are transparent; duplicates deduplicate.
r=repo('multi',pack,idx); d=r/'objects'/'pack'; (d/'pack-other.pack').write_bytes(pack2); (d/'pack-other.idx').write_bytes(idx2); (d/'pack-fixture.keep').write_text('keep\n')
check('multi-duplicate-prefix',r,last,name_id=oid('blob',last).hex()[:7])
loose=r/'objects'/oid('blob',last).hex()[:2]; loose.mkdir(); (loose/oid('blob',last).hex()[2:]).write_bytes(zlib.compress(b'blob 9\0'+last))
check('loose-prefix-dedup',r,last,name_id=oid('blob',last).hex()[:7]); check('loose-read',r,last)
for marker,reason in [('multi-pack-index','multi-pack-index'),('pack-fixture.bitmap','pack bitmap')]:
    rr=repo('unsupported-'+marker,pack,idx); (rr/'objects'/'pack'/marker).write_bytes(b'unsupported')
    check(marker,rr,last,expected=reason)
(OUT/'results.json').write_text(json.dumps(rows,indent=2)+'\n')
print(f'pack structural: {sum(x["ok"] for x in rows)}/{len(rows)}; zero skips',flush=True)
raise SystemExit(not all(x['ok'] for x in rows))
