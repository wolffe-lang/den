#!/usr/bin/env python3
"""Revert supplies metadata bodies before publication: exact/over cap fixtures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tier', default='native')
    p.add_argument('--den')
    p.add_argument('--dev-oracle', action='store_true')
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    git = os.environ['DEN_GIT']
    digest = hashlib.sha256(Path(git).read_bytes()).hexdigest()
    if a.dev_oracle:
        assert os.uname().sysname == 'Darwin'
        print('DEV ORACLE (not pinned Linux evidence):', digest, flush=True)
    else:
        assert digest == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = a.den or str(root / 'target' / a.tier / 'den')
    out = root / 'target/runs' / ('supplied-attributes-limit-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    def run(tool, argv, cwd, check=True):
        q = subprocess.run([str(tool), *map(str, argv)], cwd=cwd, capture_output=True)
        if check:
            assert q.returncode == 0, (argv, q.returncode, q.stderr)
        return q

    def g(cwd, *argv):
        return run(git, argv, cwd).stdout

    def state(cwd):
        return dict(head=g(cwd, 'rev-parse', 'HEAD').hex(), index=g(cwd, 'ls-files', '-s').hex(),
                    files={str(x.relative_to(cwd)): hashlib.sha256(x.read_bytes()).hexdigest()
                           for x in sorted(cwd.rglob('*')) if '.git' not in x.relative_to(cwd).parts and x.is_file()})

    rows = []
    for size in (1048576, 1048577):
        name = 'supplied-attributes-limit-' + ('exact' if size == 1048576 else 'over')
        case = out / name
        case.mkdir()
        seed = case / 'seed'
        run(git, ['init', '-q', '-b', 'main', seed], root)
        (seed / '.gitattributes').write_bytes(b'#' + b'x' * (size - 2) + b'\n')
        (seed / 'a.txt').write_bytes(b'base\n')
        g(seed, 'add', '.')
        g(seed, 'commit', '-qm', 'large metadata')
        (seed / '.gitattributes').write_text('# small\n')
        g(seed, 'commit', '-qam', 'shrink metadata')
        target = g(seed, 'rev-parse', 'HEAD').decode().strip()
        results = {}
        for label, tool in (('git', git), ('den', den)):
            work = case / 'work'
            if work.exists():
                shutil.rmtree(work)
            shutil.copytree(seed, work)
            before = state(work)
            index = (work / '.git/index').read_bytes()
            head = (work / '.git/HEAD').read_bytes()
            objects = g(work, 'cat-file', '--batch-all-objects', '--batch-check=%(objectname) %(objecttype) %(objectsize)')
            q = run(tool, ['revert', '--no-edit', target], work, check=False)
            preserved = state(work) == before and (work / '.git/index').read_bytes() == index and (work / '.git/HEAD').read_bytes() == head and g(work, 'cat-file', '--batch-all-objects', '--batch-check=%(objectname) %(objecttype) %(objectsize)') == objects
            results[label] = dict(status=q.returncode, stdout=q.stdout.hex(), stderr=q.stderr.hex(), state=state(work), preserved=preserved)
        if size == 1048576:
            ok = results['git'] == results['den']
        else:
            d = results['den']
            ok = d['status'] == 128 and b'limit:' in bytes.fromhex(d['stderr']) and b'1048576' in bytes.fromhex(d['stderr']) and d['preserved']
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok:
            print(json.dumps(results), flush=True)
        rows.append(dict(name=name, passed=ok, **results))
    (out / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
    print('supplied-attributes-limit:', len(rows), 'rows,', sum(not x['passed'] for x in rows), 'failures; zero skips', flush=True)
    return int(any(not x['passed'] for x in rows))


if __name__ == '__main__':
    raise SystemExit(main())
