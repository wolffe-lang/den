"""vc14 independent pinned-binary observations; no Git implementation input."""
import base64, hashlib, json, os, pathlib, shutil, struct, subprocess, zlib
R = pathlib.Path(__file__).resolve().parent.parent
G = str(next((R/'target/oracle').glob('*/root/opt/git/bin/git')))
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
os.environ['GIT_EXEC_PATH'] = str(pathlib.Path(G).parent.parent/'libexec/git-core')
root = R/'target/vc14-measure'
root.mkdir(parents=True, exist_ok=True)
rows, states, contents = [], {}, {}
def snap(p):
    out = {}
    for f in sorted(p.rglob('*')):
        data = os.fsencode(os.readlink(f)) if f.is_symlink() else f.read_bytes() if f.is_file() else b''
        key = hashlib.sha256(data).hexdigest()
        contents[key] = base64.b64encode(data).decode()
        out[str(f.relative_to(p))] = [f.lstat().st_mode, key]
    key = hashlib.sha256(json.dumps(out, sort_keys=True).encode()).hexdigest()
    states[key] = out
    return key
def run(p, *args, data=None, checked=True):
    q = subprocess.run([G, *args], cwd=p, input=data, capture_output=True)
    if checked: assert q.returncode == 0, (args, q.stdout, q.stderr)
    return q
def raw(p, kind, data):
    return run(p, 'hash-object', '-t', kind, '-w', '--stdin', data=data).stdout.strip().decode()
def init(name):
    p = root/name
    assert not p.exists(), p
    p.mkdir()
    run(p, 'init', '-q', '-b', 'main', '--template=')
    return p
def observe(p, label, args):
    before = snap(p)
    q = run(p, *args, checked=False)
    row = dict(label=label, args=args, before=before, after=snap(p), stdout=q.stdout.hex(), stderr=q.stderr.hex(), status=q.returncode)
    rows.append(row)
    print(label, q.returncode, repr(q.stdout), repr(q.stderr), flush=True)
    return row
def copy(p, name):
    target = root/name
    shutil.copytree(p, target)
    return target
def loose(p, name):
    return p/'.git/objects'/name[:2]/name[2:]
def commit(p, tree, parents=(), message=b'commit\n'):
    return run(p, 'commit-tree', tree, *[v for x in parents for v in ('-p', x)], data=message).stdout.strip().decode()
def fixsum(data):
    data[-20:] = hashlib.sha1(data[:-20]).digest()
    return data
try:
    p = init('base')
    blob = raw(p, 'blob', b'content\n')
    tree = raw(p, 'tree', b'100644 file\0'+bytes.fromhex(blob))
    head = commit(p, tree)
    run(p, 'update-ref', 'refs/heads/main', head)
    run(p, 'read-tree', head)
    orphan = raw(p, 'blob', b'unreachable\n')
    logtree = raw(p, 'tree', b'100644 old\0'+bytes.fromhex(raw(p, 'blob', b'old\n')))
    old = commit(p, logtree)
    run(p, 'update-ref', '--create-reflog', 'refs/heads/past', old)
    run(p, 'update-ref', 'refs/heads/past', head)
    staged = raw(p, 'blob', b'staged\n')
    run(p, 'update-index', '--add', '--cacheinfo', '100644', staged, 'staged')
    for args in [ ['repack','-q','-n'], ['repack','-a','-q','-n'], ['repack','-a','-d','-q','-n'], ['repack','-A','-d','-q','-n'], ['repack','-a','-d','-k','-q','-n'], ['repack','-a','-d','-q'], ['gc','--no-cruft','--no-prune','--quiet'], ['gc','--quiet'], ['gc','--no-cruft','--prune=now','--quiet'] ]:
        q = copy(p, 'policy-'+str(len(rows)))
        observe(q, 'loose '+str(args), args)
        observe(q, 'repeat '+str(args), args)
    packed = copy(p, 'packed-base')
    names = run(p, 'cat-file', '--batch-all-objects', '--batch-check=%(objectname)').stdout
    run(packed, 'pack-objects', '-q', '.git/objects/pack/pack', data=names)
    for args in [ ['repack','-q','-n'], ['repack','-a','-d','-q','-n'], ['repack','-A','-d','-q','-n'], ['repack','-a','-d','-k','-q','-n'], ['prune-packed','-n'], ['prune-packed','-q'] ]:
        q = copy(packed, 'packed-policy-'+str(len(rows)))
        observe(q, 'packed '+str(args), args)
    for label, target in [('missing-blob', blob), ('missing-tree', tree), ('missing-head', head), ('missing-reflog', old), ('missing-index', staged)]:
        q = copy(p, label); loose(q, target).unlink()
        observe(q, label, ['fsck','--full','--no-progress'])
    for label, content in [('empty', b''), ('zlib', b'not-zlib'), ('wrong-hash', zlib.compress(b'blob 4\0oops'))]:
        q = copy(p, 'corrupt-'+label); loose(q, blob).write_bytes(content)
        observe(q, 'corrupt-'+label, ['fsck','--full','--no-progress'])
    for label, ref, value in [('bad-head', 'HEAD', blob), ('bad-branch', 'refs/heads/main', blob), ('missing-ref', 'refs/tags/missing', '1'*40), ('invalid-ref', 'refs/tags/invalid', 'xyz')]:
        q = copy(p, label); f = q/'.git'/ref; f.parent.mkdir(parents=True, exist_ok=True); f.write_text(value+'\n')
        observe(q, label, ['fsck','--full','--no-progress'])
    for label, kind, content in [('wrong-tree', 'commit', f'tree {blob}\nauthor A <a@b> 1700000000 +0000\ncommitter A <a@b> 1700000000 +0000\n\nx\n'.encode()), ('wrong-entry', 'tree', b'100644 wrong\0'+bytes.fromhex(head))]:
        q = copy(p, label); raw(q, kind, content)
        observe(q, label, ['fsck','--full','--no-progress'])
    q = init('dangling-order')
    for i in range(80): raw(q, 'blob', f'loose dangling {i}\n'.encode())
    observe(q, 'dangling-loose-80', ['fsck','--full','--no-progress'])
    names = run(q, 'cat-file','--batch-all-objects','--batch-check=%(objectname)').stdout
    run(q, 'pack-objects','-q','.git/objects/pack/pack',data=names)
    observe(q, 'dangling-duplicate-80', ['fsck','--full','--no-progress'])
    run(q, 'prune-packed','-q')
    observe(q, 'dangling-packed-80', ['fsck','--full','--no-progress'])
    q = copy(p, 'graph-base')
    run(q, 'commit-graph','write','--reachable','--no-progress')
    observe(q, 'graph-valid', ['fsck','--full','--no-progress'])
    graph = (q/'.git/objects/info/commit-graph').read_bytes()
    chunks = {}
    for i in range(graph[6]):
        tag, start = struct.unpack_from('>4sQ', graph, 8+i*12)
        end = struct.unpack_from('>Q', graph, 8+(i+1)*12+4)[0]
        chunks[tag.decode()] = [start, end]
    mutations = [('checksum',len(graph)-1,1,False),('signature',0,1,True),('version',4,1,True),('hash',5,1,True),('tree',chunks['CDAT'][0],1,True),('parent',chunks['CDAT'][0]+20,1,True),('time',chunks['CDAT'][0]+35,1,True),('generation',chunks['CDAT'][0]+31,4,True),('oid',chunks['OIDL'][0]+19,1,True),('fanout',chunks['OIDF'][0]+1023,1,True)]
    for label, offset, mask, checksum in mutations:
        dest = copy(q, 'graph-'+label); data = bytearray(graph); data[offset] ^= mask
        if checksum: fixsum(data)
        (dest/'.git/objects/info/commit-graph').write_bytes(data)
        observe(dest, 'graph-'+label, ['fsck','--full','--no-progress'])
finally:
    out = R/'target/vc14-measure.json'
    out.write_text(json.dumps(dict(rows=rows, states=states, contents=contents)))
    print('VC14 OBSERVATIONS', len(rows), out, flush=True)
