"""Exact isolated daily-use rows; only the pinned Git executable is an oracle."""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import termios
import zlib

R = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser()
p.add_argument('--tier', default='native')
p.add_argument('--family', choices=['dates', 'decorations', 'config'], required=True)
a = p.parse_args()
G = Path(os.environ['DEN_GIT'])
assert hashlib.sha256(G.read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
D = R / 'target' / a.tier / 'den'
root = R / 'target' / ('daily-' + a.family + '-' + a.tier)
if root.exists():
    shutil.rmtree(root)
root.mkdir(parents=True)
base = root / 'base'
base.mkdir()
env = dict(os.environ)
rows = []

def run(exe, args, cwd=base, changes=None, terminal=False, data=None):
    e = dict(env)
    for key, value in (changes or {}).items():
        if value is None:
            e.pop(key, None)
        else:
            e[key] = value
    if not terminal:
        q = subprocess.run([str(exe), *args], cwd=cwd, env=e, input=data, capture_output=True)
        return {'status': q.returncode, 'stdout': q.stdout.hex(), 'stderr': q.stderr.hex()}
    master, slave = pty.openpty()
    attrs = termios.tcgetattr(slave)
    attrs[1] &= ~termios.OPOST
    termios.tcsetattr(slave, termios.TCSANOW, attrs)
    q = subprocess.Popen([str(exe), *args], cwd=cwd, env=e, stdin=subprocess.DEVNULL, stdout=slave, stderr=subprocess.PIPE)
    os.close(slave)
    out = bytearray()
    while True:
        assert select.select([master], [], [], 60)[0], 'PTY timeout'
        try:
            chunk = os.read(master, 65536)
        except OSError as ex:
            if ex.errno != errno.EIO:
                raise
            break
        if not chunk:
            break
        out.extend(chunk)
    os.close(master)
    err = q.communicate(timeout=60)[1]
    return {'status': q.returncode, 'stdout': out.hex(), 'stderr': err.hex()}

def g(*args, data=None):
    q = run(G, args, data=data)
    assert q['status'] == 0, (args, q)
    return bytes.fromhex(q['stdout']).decode().strip()

def state(path):
    result = {}
    for f in sorted(path.rglob('*')):
        rel = f.relative_to(path).as_posix()
        if f.is_symlink():
            result[rel] = ['symlink', os.readlink(f)]
        elif f.is_file():
            b = f.read_bytes()
            if '/objects/' in '/' + rel and len(f.name) == 38:
                b = zlib.decompress(b)
            result[rel] = [f.stat().st_mode & 0o777, b.hex()]
        elif f.is_dir():
            result[rel] = ['dir', f.stat().st_mode & 0o777]
    return result

def check(name, args, changes=None, terminal=False, mutate=False):
    if mutate:
        left, right = root / 'git', root / 'den'
        for path in [left, right]:
            if path.exists():
                shutil.rmtree(path)
            shutil.copytree(base, path)
        expected = run(G, args, left, changes, terminal)
        actual = run(D, args, right, changes, terminal)
        states = [state(left), state(right)]
        equal = states[0] == states[1]
    else:
        before = state(base)
        expected = run(G, args, changes=changes, terminal=terminal)
        middle = state(base)
        actual = run(D, args, changes=changes, terminal=terminal)
        states = [before, middle, state(base)]
        equal = states[0] == states[1] == states[2]
    ok = expected == actual and equal
    rows.append({'name': name, 'args': args, 'environment': changes, 'terminal': terminal,
                 'expected': expected, 'actual': actual, 'states': states, 'equal': ok})
    print(('PASS' if ok else 'FAIL'), name, flush=True)
    if not ok:
        print('  expected', expected, 'actual', actual, 'state-equal', equal, flush=True)

g('init', '-q')
(base / 'file').write_text('one\ntwo\n')
g('add', 'file')
g('commit', '-qm', 'first')
if a.family == 'dates':
    assert not Path('/usr/share/zoneinfo/UTC').exists(), 'run with an empty zone database'
    assert not Path('/etc/localtime').exists() or Path('/etc/localtime').stat().st_size == 0
    g('stash', 'store', '-m', 'saved', 'HEAD')
    for zone in [None, 'UTC', 'Missing/Zone']:
        changes = {'TZ': zone, 'TZDIR': str(root / 'empty-zones')}
        label = 'unset' if zone is None else zone.replace('/', '-')
        for args in [['log'], ['log', '--date=local'], ['show', '-s'], ['blame', 'file'], ['stash', 'list']]:
            check('date-no-db-' + label + '-' + args[0] + ('-local' if '--date=local' in args else ''), args, changes)
        check('date-no-db-' + label + '-commit', ['commit', '--allow-empty', '-m', 'daily'], changes, mutate=True)
else:
    raise AssertionError('family not yet defined')
(root / 'captures.json').write_text(json.dumps(rows, indent=2) + '\n')
failed = [row['name'] for row in rows if not row['equal']]
print(f'daily {a.family}: {len(rows)-len(failed)}/{len(rows)} exact; zero skips', flush=True)
raise SystemExit(bool(failed))
