#!/usr/bin/env python3
"""mergetree-at-compares: the merge planner's path lookups, counted, and its plan, checked.

probes/mergetree-client at-compares FILES plans a three-way merge of generated sides in the pull rows' fixture
shape (tools/pull-scale-test.py: file i at d{i % 1000}/s{(i / 1000) % 4}/f{i}.txt, in path order): ours changes
file 100's blob, theirs file 7000's and adds one file. The planner looks each path up in each side, and a lookup
that compares against every file before it cost a 10,500-file merge pull about 276 million comparisons (32 G
instructions).

  mergetree-at-compares  at most 2 x lookups x log2(files) comparisons, where the lookups are the planner's own
                         count for these sides: each of ours' paths in base, each of theirs' in base and, if
                         absent, in ours, then each planned path in all three;
  mergetree-at-plan      every file planned, no conflict, ours' change taken once and theirs' twice (its
                         change and its added file), so a cheaper lookup plans the same merge.
"""
import argparse
import math
from pathlib import Path
import subprocess

FILES = 10500


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tier', default='native')
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    probe = root / 'target' / a.tier / 'mergetree-client'
    r = subprocess.run([str(probe), 'at-compares', str(FILES)], capture_output=True, timeout=600)
    line = r.stdout.decode(errors='replace').strip()
    fields = dict(f.split('=', 1) for f in line.split() if '=' in f)
    rows = []

    def row(name, ok, detail):
        rows.append(ok)
        print(('PASS ' if ok else 'FAIL ') + name + ': ' + detail, flush=True)

    paths = FILES + 1
    lookups = FILES + (FILES + 1) + 1 + 3 * paths
    bound = 2 * lookups * math.ceil(math.log2(paths))
    ran = r.returncode == 0 and fields.get('files') == str(FILES)
    compares = int(fields.get('compares', '-1')) if ran else -1
    row('mergetree-at-compares', ran and 0 <= compares <= bound,
        f'compares={compares} for {lookups} lookups among {paths} paths, {compares / lookups:.1f} a lookup; '
        f'bound {bound}' + ('' if ran else f'; exit {r.returncode} {line!r} {r.stderr.decode(errors="replace")[-200:]!r}'))
    row('mergetree-at-plan', ran and fields.get('planned') == str(paths) and fields.get('conflicts') == '0'
        and fields.get('ours') == '1' and fields.get('theirs') == '2',
        f'planned={fields.get("planned")} conflicts={fields.get("conflicts")} ours={fields.get("ours")} '
        f'theirs={fields.get("theirs")}; want {paths}, 0, 1 and 2')
    failures = rows.count(False)
    print(f'mergetree-at: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
