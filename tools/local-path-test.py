"""Exact local-path clone/fetch rows, with retained raw state and object proofs.

The two tools receive identical input at the identical physical pathname. Raw
state differences remain failures; canonical object inventory is additional
evidence, never a substitute for config/ref/process identity.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zlib

p = argparse.ArgumentParser()
p.add_argument('--tier', default='native')
a = p.parse_args()
R = Path(__file__).resolve().parent.parent
G = Path(os.environ['DEN_GIT'])
D = R / 'target' / a.tier / 'den'
assert hashlib.sha256(G.read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
root = R / 'target' / ('local-path-' + a.tier)
if root.exists():
    shutil.rmtree(root)
root.mkdir(parents=True)
source = root / 'source'
source.mkdir()
world = root / 'world'
rows = []


def run(exe, args, cwd, data=None):
    q = subprocess.run([str(exe), *args], cwd=cwd, input=data, capture_output=True, timeout=120)
    return dict(status=q.returncode, stdout=q.stdout.hex(), stderr=q.stderr.hex())


def g(*args, cwd=source, data=None):
    q = run(G, args, cwd, data)
    assert q['status'] == 0, (args, q)
    return bytes.fromhex(q['stdout'])


def state(path):
    result = {}
    for f in sorted(path.rglob('*')):
        rel = f.relative_to(path).as_posix()
        if f.is_symlink():
            result[rel] = ['symlink', os.readlink(f)]
        elif f.is_file():
            raw = f.read_bytes()
            result[rel] = [f.stat().st_mode & 0o7777, raw.hex()]
        elif f.is_dir():
            result[rel] = ['directory', f.stat().st_mode & 0o7777]
    return result


def objects(repo):
    names = g('cat-file', '--batch-all-objects', '--batch-check=%(objectname)', cwd=repo).splitlines()
    result = {}
    for oid in names:
        kind = g('cat-file', '-t', oid.decode(), cwd=repo).strip()
        body = g('cat-file', kind.decode(), oid.decode(), cwd=repo)
        canonical = kind + b' ' + str(len(body)).encode() + b'\0' + body
        assert hashlib.sha1(canonical).hexdigest().encode() == oid
        result[oid.decode()] = canonical.hex()
    return result


def compare(name, args, cwd='.', target='clone.git'):
    outcomes = []
    for exe in [G, D]:
        if world.exists():
            shutil.rmtree(world)
        shutil.copytree(seed, world)
        before = state(world)
        q = run(exe, args, world / cwd)
        after = state(world)
        inventory = None
        if q['status'] == 0:
            inventory = objects(world / target)
        outcomes.append(dict(result=q, before=before, after=after, objects=inventory))
    left, right = outcomes
    assert left['before'] == right['before']
    ok = left['result'] == right['result'] and left['after'] == right['after']
    object_equal = left['objects'] == right['objects'] and left['objects'] is not None
    rows.append(dict(name=name, argv=args, cwd=cwd, environment=dict(os.environ),
                     expected=left, actual=right, equal=ok, canonical_objects_equal=object_equal))
    print(('PASS' if ok else 'FAIL'), name, 'canonical_objects_equal=' + str(object_equal), flush=True)
    if not ok:
        paths = sorted(k for k in left['after'].keys() | right['after'].keys()
                       if left['after'].get(k) != right['after'].get(k))
        print('  expected', left['result'], 'actual', right['result'], 'differing_paths', paths, flush=True)


try:
    g('init', '-q', '-b', 'main')
    (source / 'file').write_bytes(b'local path fixture\n')
    g('add', 'file')
    g('commit', '-qm', 'first')
    g('branch', 'side')
    g('tag', 'anchor')
    seed = root / 'seed'
    seed.mkdir()
    g('clone', '-q', '--bare', str(source), str(seed / 'peer.git'))
    g('hash-object', '-w', '--stdin', cwd=seed / 'peer.git', data=b'unreachable clone-copy witness\n')
    g('init', '-q', '--bare', str(seed / 'fetch.git'))
    g('config', 'remote.origin.url', '../peer.git', cwd=seed / 'fetch.git')
    g('config', 'remote.origin.fetch', '+refs/heads/*:refs/remotes/origin/*', cwd=seed / 'fetch.git')
    for label, url in [('absolute', str(world / 'peer.git')), ('relative', './peer.git')]:
        compare('local-clone-bare-' + label, ['clone', '-q', '--bare', url, 'clone.git'])
        compare('local-clone-no-local-' + label,
                ['clone', '-q', '--bare', '--no-local', url, 'clone.git'])
    for label, url in [('absolute', str(world / 'peer.git')), ('relative', '../peer.git')]:
        compare('local-fetch-explicit-' + label,
                ['fetch', '-q', url, 'refs/heads/main:refs/heads/fetched'],
                cwd='fetch.git', target='fetch.git')
        compare('local-fetch-head-' + label, ['fetch', '-q', url],
                cwd='fetch.git', target='fetch.git')
    compare('local-fetch-configured', ['fetch', '-q', 'origin'], cwd='fetch.git', target='fetch.git')
finally:
    output = R / 'target/runs' / ('local-path-' + a.tier + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(rows=rows), indent=2) + '\n')
raise SystemExit(0 if rows and all(row['equal'] for row in rows) else 1)
