"""Generate den#50's deterministic shape, never a copy of a user repository.

Run inside the pinned Linux oracle environment. Destination must be new. The
copy preserves mtimes/modes via cp -a; its changed inode/ctime words are retained
before an explicit refresh, then independently proved against destination lstat.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import struct
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--root', type=Path, required=True)
a = p.parse_args()
R = Path(__file__).resolve().parent.parent
G = Path(os.environ['DEN_GIT'])
assert hashlib.sha256(G.read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
root = a.root.resolve()
root.mkdir(parents=True, exist_ok=False)
source = root / 'source'
source.mkdir()
proof = runpy.run_path(str(R / 'tools/index-proof.py'))


def git(*args, cwd=source):
    q = subprocess.run([str(G), *args], cwd=cwd, capture_output=True, check=True)
    return q.stdout


def pseudorandom(seed, size):
    # Hash-counter bytes, stable across Python versions and machines.
    data = bytearray()
    counter = 0
    while len(data) < size:
        data.extend(hashlib.sha256(seed + counter.to_bytes(8, 'big')).digest())
        counter += 1
    return bytes(data[:size])


def inspect(repo):
    raw = (repo / '.git/index').read_bytes()
    entries = proof['entries'](raw)
    assert struct.unpack_from('>I', raw, 4)[0] == 2
    last = entries[-1]
    pos = last['offset'] + ((62 + len(last['name']) + 1 + 7) // 8) * 8
    extensions = []
    while pos < len(raw) - 20:
        signature = raw[pos:pos+4].decode('ascii')
        size = struct.unpack_from('>I', raw, pos+4)[0]
        extensions.append(signature)
        pos += 8 + size
    files = [f for f in repo.rglob('*') if f.is_file() and '.git' not in f.relative_to(repo).parts]
    return dict(index_sha256=hashlib.sha256(raw).hexdigest(), index_version=2,
                tracked=len(entries), extensions=extensions,
                index_proof=proof['proof'](repo, raw),
                worktree_bytes=sum(f.stat().st_size for f in files),
                pack_bytes=sum(f.stat().st_size for f in (repo / '.git/objects/pack').glob('*.pack')),
                untracked=git('ls-files', '--others', '--exclude-standard', '-z', cwd=repo).count(b'\0'))


git('init', '-q', '-b', 'main')
git('config', 'index.version', '2')
git('config', 'core.autocrlf', 'false')
git('config', 'gc.auto', '0')
git('config', 'maintenance.auto', 'false')
(source / '.gitignore').write_bytes(b'/build/\n')
tracked_payload = 18_960_000
for n in range(453):
    path = source / 'src' / ('d%02d' % (n // 30)) / ('f%03d.bin' % n)
    path.parent.mkdir(parents=True, exist_ok=True)
    size = tracked_payload // 453 + (n < tracked_payload % 453)
    path.write_bytes(pseudorandom(('file-%d' % n).encode(), size))
    os.utime(path, ns=(1_700_000_000_123456789, 1_700_000_000_123456789))
git('add', '.')
git('commit', '-qm', 'deterministic status fixture')
git('repack', '-ad')
for n in range(42):
    (source / ('untracked-%02d' % n)).write_bytes(pseudorandom(('untracked-%d' % n).encode(), 512))
remaining = 187_000_000 - tracked_payload - len(b'/build/\n') - 42 * 512
for n in range(2048):
    path = source / 'build' / ('output-%02d' % (n // 64)) / ('f%04d.o' % n)
    path.parent.mkdir(parents=True, exist_ok=True)
    size = remaining // 2048 + (n < remaining % 2048)
    path.write_bytes((b'ignored build output\n' * ((size + 20) // 21))[:size])
# The ignored-output size formula is independently checked, not assumed.
before = inspect(source)
assert before['tracked'] == 454 and before['untracked'] == 42, before
assert before['extensions'] == ['TREE'], before['extensions']
assert before['worktree_bytes'] == 187_000_000, before['worktree_bytes']
assert abs(before['pack_bytes'] - 19_000_000) <= 95_000, before['pack_bytes']
copy = root / 'case'
subprocess.run(['cp', '-a', str(source), str(copy)], check=True)
pre_refresh = inspect(copy)
(root / 'cold.index').write_bytes((copy / '.git/index').read_bytes())
git('update-index', '--refresh', cwd=copy)
post_refresh = inspect(copy)
(root / 'warm.index').write_bytes((copy / '.git/index').read_bytes())
assert all(row['own_stat_equal'] for row in post_refresh['index_proof'])
assert post_refresh['extensions'] == ['TREE']
summary = dict(source=before, copied_before_refresh=pre_refresh, copied_after_refresh=post_refresh,
               note='cp -a preserves mtimes, not inode/ctime; explicit destination refresh is proved',
               decimal_pack_target=19_000_000, pack_tolerance=95_000,
               decimal_worktree_bytes=187_000_000)
(root / 'fixture.json').write_text(json.dumps(summary, indent=2) + '\n')
print('PASS status-fixture-shape tracked=454 untracked=42 worktree=187000000 pack=' + str(post_refresh['pack_bytes']), flush=True)
print('PASS status-fixture-stat-proof entries=454', flush=True)
