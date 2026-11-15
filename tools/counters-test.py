"""DEN_COUNTERS: off unless it is 1, and normal output unchanged byte for byte.

One script of den commands (clone over file://, status, log, add, commit, a
merging pull, rev-parse and a failing switch) runs four times on fresh copies
of one fixture, with DEN_COUNTERS unset, empty, 0 and 1. Every run uses the
same directory, since the merge commit's message names the remote's path; each
run's tree is moved aside when it ends. With the variable unset, empty or 0
every step's stdout, stderr and exit status, and the repository left behind,
are the same bytes. With 1 they are the same too, except that each step's
stderr ends with exactly one counter line, and the counters a step must have
done are not zero.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

p = argparse.ArgumentParser()
p.add_argument('--tier', default='native')
a = p.parse_args()
R = Path(__file__).resolve().parent.parent
G = Path(os.environ['DEN_GIT'])
D = R / 'target' / a.tier / 'den'
assert hashlib.sha256(G.read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
root = R / 'target' / ('counters-' + a.tier)
if root.exists():
    shutil.rmtree(root)
root.mkdir(parents=True)
VARIANTS = [('unset', None), ('empty', ''), ('zero', '0'), ('one', '1')]
NAMES = ('index-parses', 'pack-index-loads', 'objects-read', 'files-read', 'scans', 'commits-parsed')
LINE = re.compile(rb'den-counters ' + rb' '.join(n.encode() + rb'=(\d+)' for n in NAMES) + rb'\n\Z')
# What each step must have done at least once, by counter.
NEEDS = {
    'clone': ('objects-read', 'pack-index-loads'),
    'status': ('index-parses', 'scans'),
    'log': ('commits-parsed',),
    'pull': ('commits-parsed', 'objects-read', 'index-parses'),
}


def git(*args, cwd):
    q = subprocess.run([str(G), *args], cwd=cwd, capture_output=True, timeout=120)
    assert q.returncode == 0, (args, q.stdout, q.stderr)
    return q.stdout


def fixture(top):
    origin, server = top / 'origin', top / 'remote.git'
    git('init', '-q', str(origin), cwd=top)
    (origin / 'dir').mkdir()
    for i, name in enumerate(('a', 'b', 'dir/c')):
        (origin / name).write_text(f'line {i}\n')
        git('add', name, cwd=origin)
        git('commit', '-qm', f'add {name}', cwd=origin)
    git('clone', '-q', '--bare', str(origin), str(server), cwd=top)
    return origin, server


def upstream(top):
    origin = top / 'origin'
    (origin / 'a').write_text('line 0\ntheirs\n')
    git('commit', '-qam', 'theirs', cwd=origin)
    git('push', '-q', (top / 'remote.git').as_uri(), 'HEAD:refs/heads/main', cwd=origin)


def local(top):
    (top / 'work' / 'new.txt').write_text('ours\n')


def script(top):
    work = top / 'work'
    return [
        ('clone', ['clone', (top / 'remote.git').as_uri(), 'work'], top, None),
        ('status', ['status'], work, None),
        ('log', ['log', '--oneline'], work, None),
        ('add', ['add', 'new.txt'], work, local),
        ('commit', ['commit', '-m', 'ours'], work, None),
        ('pull', ['pull', '--no-rebase'], work, upstream),
        ('status-after', ['status', '--short'], work, None),
        ('rev-parse', ['rev-parse', 'HEAD'], work, None),
        ('switch-missing', ['switch', 'no-such-branch'], work, None),
    ]


def state(top):
    work = top / 'work'
    files = {}
    for path in sorted(work.rglob('*')):
        rel = path.relative_to(work).as_posix()
        if rel == '.git/index' or not path.is_file() or path.is_symlink():
            continue
        files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(
        files=files,
        stage=git('ls-files', '-s', cwd=work).decode(),
        refs=git('for-each-ref', cwd=work).decode(),
        status=git('status', '--porcelain', cwd=work).decode(),
    )


runs = {}
for label, value in VARIANTS:
    top = root / 'run'
    top.mkdir()
    fixture(top)
    env = {k: v for k, v in os.environ.items() if k != 'DEN_COUNTERS'}
    env['GIT_MERGE_AUTOEDIT'] = 'no'
    if value is not None:
        env['DEN_COUNTERS'] = value
    steps = []
    for name, argv, cwd, before in script(top):
        if before:
            before(top)
        q = subprocess.run([str(D), *argv], cwd=cwd, env=env, input=b'', capture_output=True, timeout=120)
        steps.append(dict(name=name, exit=q.returncode, stdout=q.stdout, stderr=q.stderr))
    runs[label] = dict(steps=steps, state=state(top))
    top.rename(root / label)

failures = []
base = runs['unset']
for label in ('empty', 'zero', 'one'):
    run = runs[label]
    if run['state'] != base['state']:
        failures.append(f'{label}: repository differs from unset')
    for want, got in zip(base['steps'], run['steps']):
        name = want['name']
        if (want['exit'], want['stdout']) != (got['exit'], got['stdout']):
            failures.append(f'{label} {name}: exit or stdout differs')
        if label != 'one':
            if got['stderr'] != want['stderr']:
                failures.append(f'{label} {name}: stderr differs')
            continue
        if not got['stderr'].startswith(want['stderr']):
            failures.append(f'{label} {name}: stderr is not unset\'s plus a line')
            continue
        m = LINE.match(got['stderr'][len(want['stderr']):])
        if not m:
            failures.append(f'{label} {name}: no single counter line at the end: {got["stderr"][-200:]!r}')
            continue
        counts = dict(zip(NAMES, map(int, m.groups())))
        got['counters'] = counts
        for need in NEEDS.get(name, ()):
            if counts[need] == 0:
                failures.append(f'{label} {name}: {need} is 0')
exits = [s['exit'] for s in base['steps']]
if any(exits[:-1]) or exits[-1] == 0:
    failures.append(f'unset: exits {exits}, every step but the failing switch must succeed')

out = R / 'target' / 'runs'
out.mkdir(parents=True, exist_ok=True)
summary = dict(
    tier=a.tier,
    exits=exits,
    counters={s['name']: s.get('counters') for s in runs['one']['steps']},
    failures=failures,
    zero_skips=True,
)
(out / f'counters-{a.tier}.json').write_text(json.dumps(summary, indent=2) + '\n')
for s in runs['one']['steps']:
    print(f"  {s['name']}: exit {s['exit']} {s.get('counters')}")
for f in failures:
    print('FAIL', f)
print(('PASS' if not failures else 'FAIL') + f' counters-{a.tier}: unset, empty and 0 agree byte for byte; 1 adds one line per step')
raise SystemExit(int(bool(failures)))
