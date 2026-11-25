#!/usr/bin/env python3
"""Pack indexes malformed entry by entry, read beside the pinned Git (black-box). Git refuses at open only what
it must to use the index at all (its header, version, monotonic fanout and length); each entry is checked when
it is used, and every entry by verify-pack (fsck checks the objects it reads). So a read of an object the
malformation does not touch answers as with a sound index, a lookup bounded by the fanout misses a name outside
its bucket, and verify-pack refuses every one of these. den's fsck checks the index as its verify-pack does
(the owner's ruling: a malformed index is refused at first use, and in fsck and verify-pack), so where Git's fsck
passes an index it does not check (a name outside its bucket, an unused large-offset entry), den's fsck refuses
it by name; wherever Git's fsck refuses, den's must too.

A repository of a few commits is packed by Git; each row group copies it and rewrites the idx one way, re-signed
so its own checksum is right:
  name-order        the first two names swapped
  fanout-entry      the fanout still monotonic, one name left outside its bucket
  large-unused      a large-offset entry that no slot uses
  duplicate-offset  the last object's slot moved onto the first object's offset
  offset-below-12   the last object's offset inside the pack header
  offset-past-end   the last object's offset past the pack's end
For each, the reads (READS) must equal Git's exit status, and when Git's is 0 its standard output and error;
verify-pack must succeed or fail as Git's does; fsck must fail where Git's does, and may fail where Git's
passes only with a named pack index refusal.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess

READS = [['status', '--porcelain'], ['cat-file', '-p', 'HEAD'], ['cat-file', '-p', 'HEAD:a.txt'],
         ['log', '--oneline'], ['rev-parse', 'HEAD~1^{tree}']]
CHECKS = [['fsck', '--full'], ['verify-pack', 'IDX']]


def u32(n):
    return struct.pack('>I', n)


def variants(idx):
    """name -> the idx's bytes, malformed one way (not yet re-signed)."""
    count = struct.unpack_from('>I', idx, 1028)[0]
    names = [idx[1032 + 20 * i:1052 + 20 * i] for i in range(count)]
    table = 1032 + 24 * count
    offsets = [struct.unpack_from('>I', idx, table + 4 * i)[0] for i in range(count)]
    first = min(range(count), key=lambda i: offsets[i])
    last = max(range(count), key=lambda i: offsets[i])
    k = next(i for i in range(count - 1)
             if (i == 0 or names[i - 1][0] < names[i][0]) and names[i][0] < names[i + 1][0])
    fan = bytearray(idx)
    for b in range(names[k][0], names[k + 1][0]):
        fan[8 + 4 * b:12 + 4 * b] = u32(k)

    def at(slot, value):
        return idx[:table + 4 * slot] + u32(value) + idx[table + 4 * slot + 4:]
    return {
        'name-order': idx[:1032] + names[1] + names[0] + idx[1072:],
        'fanout-entry': bytes(fan),
        'large-unused': idx[:-40] + struct.pack('>Q', 12) + idx[-40:],
        'duplicate-offset': at(last, offsets[first]),
        'offset-below-12': at(last, 4),
        'offset-past-end': at(last, 0x7ffffff0),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--dev-oracle', action='store_true', help='Darwin development evidence only; not the pinned Linux oracle')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target' / ('pack-idx-entries-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    digest = hashlib.sha256(Path(git).read_bytes()).hexdigest()
    if a.dev_oracle:
        assert os.uname().sysname == 'Darwin', 'development oracle is Darwin-only'
        print('DEV ORACLE (not pinned Linux evidence):', digest, flush=True)
    else:
        assert digest == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = str(root / 'target' / a.tier / 'den')
    env = dict(os.environ, GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
               GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid')

    def run(args, cwd):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, env=env)
        assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p.stdout

    seed = out / 'seed'
    run([git, 'init', '-q', '-b', 'main', seed], out)
    for i in range(4):
        (seed / 'a.txt').write_text(f'revision {i}\n' + 'line\n' * 50)
        (seed / f'f{i}.txt').write_text(f'file {i}\n')
        run([git, 'add', '-A'], seed)
        run([git, 'commit', '-q', '--date', f'{1700000000 + 60 * i} +0000', '-m', f'commit {i}'], seed)
    run([git, '-c', 'gc.writeCommitGraph=false', '-c', 'repack.writeBitmaps=false', 'gc', '-q'], seed)
    idx = list((seed / '.git/objects/pack').glob('*.idx'))
    assert len(idx) == 1 and not list((seed / '.git/objects').glob('[0-9a-f][0-9a-f]/*')), idx
    rows = []
    for name, body in variants(idx[0].read_bytes()).items():
        repo = out / name
        shutil.copytree(seed, repo)
        target = repo / '.git/objects/pack' / idx[0].name
        target.chmod(0o644)
        target.write_bytes(body[:-20] + hashlib.sha1(body[:-20]).digest())
        for argv in READS:
            g = subprocess.run([git, *argv], cwd=repo, capture_output=True)
            d = subprocess.run([den, *argv], cwd=repo, capture_output=True)
            if g.returncode == 0:
                ok = (d.returncode, d.stdout, d.stderr) == (0, g.stdout, g.stderr)
            else:
                ok = d.returncode == g.returncode
            label = '-'.join(x.replace('^{tree}', '-tree').replace('~', '-').replace(':', '-') for x in argv)
            print(('PASS ' if ok else 'FAIL ') + f'idx-entries-{name}-read-{label}: git {g.returncode} den {d.returncode}' +
                  ('' if ok else f' git {g.stdout[-100:]!r} {g.stderr[-140:]!r} den {d.stdout[-100:]!r} {d.stderr[-140:]!r}'),
                  flush=True)
            rows.append(ok)
        for argv in CHECKS:
            argv = [str(target) if x == 'IDX' else x for x in argv]
            g = subprocess.run([git, *argv], cwd=repo, capture_output=True)
            d = subprocess.run([den, *argv], cwd=repo, capture_output=True)
            if argv[0] == 'fsck' and g.returncode == 0 and d.returncode != 0:
                ok = b'pack index' in d.stderr
            else:
                ok = (g.returncode == 0) == (d.returncode == 0)
            print(('PASS ' if ok else 'FAIL ') + f'idx-entries-{name}-check-{argv[0]}: git {g.returncode} den {d.returncode}' +
                  ('' if ok else f' den {d.stderr[-160:]!r}'), flush=True)
            rows.append(ok)
    failures = sum(not ok for ok in rows)
    print(f'pack-idx-entries: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
