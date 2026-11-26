#!/usr/bin/env python3
"""index-trees-compares: index.build_trees' directory comparisons, counted, and its trees, checked.

probes/index-client trees-compares FILES builds the trees of a generated index in the pull rows' fixture shape
(tools/pull-scale-test.py: file i at d{i % 1000}/s{(i / 1000) % 4}/f{i}.txt, zero-padded, every blob the same
one-byte body `x`) and prints how many times finding each entry's directories compared a directory's path. A
pull's checkout builds these trees from an index of that size, and comparing against every directory made so
far cost a 10,500-file fast-forward about 51 million comparisons (6 G instructions).

  index-trees-compares  at most 2 x files x depth comparisons (each entry's directories, one comparison a
                        level, found by walking the open directories, with room for a second look);
  index-trees-root      the root tree's id equals the one this script computes from the same paths by Git's
                        tree format (mode, name, NUL, id; directories ordered as if named with a slash), so a
                        cheaper search builds the same trees.
"""
import argparse
import hashlib
from pathlib import Path
import subprocess

FILES = 10500
DEPTH = 2


def tree_id(entries):
    """A tree's id from (mode, name, id) entries, in Git's tree order."""
    def key(e):
        return e[1] + (b'/' if e[0] == b'40000' else b'')
    body = b''.join(m + b' ' + n + b'\0' + i for m, n, i in sorted(entries, key=key))
    return hashlib.sha1(b'tree %d\0' % len(body) + body).digest()


def expected_root(files):
    blob = hashlib.sha1(b'blob 1\0x').digest()
    dirs = {}
    for i in range(files):
        d, s = 'd%03d' % (i % 1000), 's%d' % ((i // 1000) % 4)
        dirs.setdefault(d, {}).setdefault(s, []).append((b'100644', ('f%05d.txt' % i).encode(), blob))
    top = []
    for d, subs in dirs.items():
        sub = [(b'40000', s.encode(), tree_id(entries)) for s, entries in subs.items()]
        top.append((b'40000', d.encode(), tree_id(sub)))
    return tree_id(top).hex(), 1 + len(dirs) + sum(len(s) for s in dirs.values())


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tier', default='native')
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    probe = root / 'target' / a.tier / 'index-client'
    r = subprocess.run([str(probe), 'trees-compares', str(FILES)], capture_output=True, timeout=600)
    line = r.stdout.decode(errors='replace').strip()
    fields = dict(f.split('=', 1) for f in line.split() if '=' in f)
    rows = []

    def row(name, ok, detail):
        rows.append(ok)
        print(('PASS ' if ok else 'FAIL ') + name + ': ' + detail, flush=True)

    want_root, trees = expected_root(FILES)
    ran = r.returncode == 0 and fields.get('files') == str(FILES) and fields.get('depth') == str(DEPTH)
    compares = int(fields.get('compares', '-1')) if ran else -1
    bound = 2 * FILES * DEPTH
    row('index-trees-compares', ran and 0 <= compares <= bound,
        f'compares={compares} for {FILES} files at depth {DEPTH}, {compares / FILES:.1f} a file; bound {bound}'
        + ('' if ran else f'; exit {r.returncode} {line!r} {r.stderr.decode(errors="replace")[-200:]!r}'))
    row('index-trees-root', ran and fields.get('root') == want_root and fields.get('directories') == str(trees - 1),
        f'root={fields.get("root")} directories={fields.get("directories")}; want {want_root} and {trees - 1}')
    failures = rows.count(False)
    print(f'index-trees: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
