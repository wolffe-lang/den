"""Independent positive and corruption witnesses for R-vc03-1's verifier."""
import hashlib, os, pathlib, runpy, shutil, struct
R = pathlib.Path(__file__).resolve().parent.parent
P = runpy.run_path(str(R/'tools/index-proof.py'))
base = R/'target/index-proof-test'
if base.exists(): shutil.rmtree(base)
base.mkdir(parents=True)

def fixture(directory):
    directory.mkdir()
    path = directory/'file'
    path.write_bytes(b'alpha\n')
    os.chmod(path, 0o644)
    st = path.stat()
    words = [st.st_ctime_ns//10**9, st.st_ctime_ns%10**9,
             st.st_mtime_ns//10**9, st.st_mtime_ns%10**9,
             st.st_dev, st.st_ino, 0o100644, st.st_uid, st.st_gid, st.st_size]
    raw = b'DIRC'+struct.pack('>II', 2, 1)
    entry = struct.pack('>10I',*[v & 0xffffffff for v in words])+hashlib.sha1(b'blob 6\0alpha\n').digest()
    entry += struct.pack('>H',4)+b'file\0'
    entry += b'\0'*((-len(entry))%8)
    raw += entry
    return raw+hashlib.sha1(raw).digest()

def reject(fn):
    try: fn()
    except ValueError: return
    raise AssertionError('corruption accepted')

a,b=fixture(base/'a'),fixture(base/'b')
pa,pb=P['proof'](base/'a',a),P['proof'](base/'b',b)
x,y,n=P['canonical_pair'](a,b,pa,pb)
assert a != b and x == y and n == 2
# Recompute the checksum after a one-bit stat corruption: checksum alone must
# never stand in for the independent own-worktree stat proof.
bad=bytearray(b); bad[15]^=1; bad[-20:]=hashlib.sha1(bad[:-20]).digest(); bad=bytes(bad)
reject(lambda: P['canonical_pair'](a,bad,pa,P['proof'](base/'b',bad)))
reject(lambda: P['canonical_pair'](a,bad,pa,pb))
reject(lambda: P['canonical_pair'](a,b,[],pb))
for position in (0,7,11,60,74,78,len(b)-1):
    damaged=bytearray(b); damaged[position]^=1
    reject(lambda: P['entries'](damaged))
# An unchanged stale cached entry needs no normalization and remains byte exact.
stale=[{**pa[0], 'own_worktree_stat':None,'proven':False}]
x,y,n=P['canonical_pair'](a,a,stale,stale)
assert x==y==a and n==0
# Different mode bytes cannot disappear under timing/identity normalization.
os.chmod(base/'b/file',0o755)
c=bytearray(b)
st=(base/'b/file').stat()
words=[st.st_ctime_ns//10**9,st.st_ctime_ns%10**9,st.st_mtime_ns//10**9,
       st.st_mtime_ns%10**9,st.st_dev,st.st_ino,0o100755,st.st_uid,st.st_gid,st.st_size]
struct.pack_into('>10I',c,12,*[v&0xffffffff for v in words]); c[-20:]=hashlib.sha1(c[:-20]).digest()
x,y,n=P['canonical_pair'](a,bytes(c),pa,P['proof'](base/'b',bytes(c)))
assert x!=y and n==2
print('index proof: two proven rows; stat/checksum/proof-binding corruptions rejected; modes remain exact')
