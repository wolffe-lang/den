#!/usr/bin/env python3
"""den#100: no bound on the fetch, pull, clone, merge or checkout paths
returns the bare `limit` tag, which a command can only print as `fatal: limit`.

Every statement in the scoped modules that originates `limit` (a `return
limit` or a `{ limit }` value that is not the pass-through arm `limit => {
return limit }` of an exhaustive match over a callee's errors) is a FAIL by
file and line. Pass-through arms are counted and listed, not failed: they
originate nothing, and the callee's own sites are in scope or named at the
call. Modules outside the scope (log, blame, notes, the pack writer, diff's
own command, the configuration reader, submodules) are listed as such.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SCOPE = [
    'src/walk', 'src/mergetree', 'src/refcmd', 'src/worktree', 'src/transport', 'src/pktline',
    'src/wire', 'src/wiregit', 'src/pack/read.lu', 'src/pack/stream.lu', 'src/pack/ingest.lu',
    'src/pack/index.lu', 'src/pack/inspect.lu', 'src/object/store.lu', 'src/refs/read.lu',
    'src/repository/repository.lu',
]
ORIGIN = re.compile(r'(?<!=> \{ )\breturn limit\b|\{ limit \}')
PASS_THROUGH = re.compile(r'\blimit => \{ return limit \}')


def files():
    for entry in SCOPE:
        path = ROOT / entry
        if path.is_dir():
            yield from sorted(p for p in path.rglob('*.lu') if not p.name.endswith('_test.lu'))
        else:
            yield path


def main():
    failures, passes = [], []
    for path in files():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            code = line.split('//', 1)[0]
            where = f'{path.relative_to(ROOT)}:{number}'
            if PASS_THROUGH.search(code):
                passes.append(where)
                continue
            if ORIGIN.search(code):
                failures.append(f'{where}: {line.strip()}')
    for item in failures:
        print(f'FAIL limit-census {item}')
    print(f'limit-census: {len(failures)} unnamed bounds, {len(passes)} pass-through arms in {len(SCOPE)} scoped paths')
    for item in passes:
        print(f'  pass-through {item}')
    if not failures:
        print('PASS limit-census')
    return int(bool(failures))


if __name__ == '__main__':
    sys.exit(main())
