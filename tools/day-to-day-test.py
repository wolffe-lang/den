"""Exact isolated daily-use rows; only the pinned Git executable is an oracle."""
import argparse
import errno
import hashlib
import json
import os
from pathlib import Path
import pty
import runpy
import select
import shutil
import subprocess
import termios
import zlib

R = Path(__file__).resolve().parent.parent
p = argparse.ArgumentParser()
p.add_argument('--tier', default='native')
p.add_argument('--family', choices=['dates', 'decorations', 'config'], required=True)
p.add_argument('--require-no-database', action='store_true',
               help='require the dedicated container with no system zone files')
a = p.parse_args()
G = Path(os.environ['DEN_GIT'])
D = R / 'target' / a.tier / 'den'
root = R / 'target' / ('daily-' + a.family + '-' + a.tier)
if root.exists():
    shutil.rmtree(root)
root.mkdir(parents=True)
base = root / 'base'
base.mkdir()
env = dict(os.environ)
rows = []
zone_fixture = {}

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
    proof_error = None
    index_proofs = []
    input_state = state(base)
    if mutate:
        left, right = root / 'git', root / 'den'
        for path in [left, right]:
            if path.exists():
                shutil.rmtree(path)
            shutil.copytree(base, path)
        expected = run(G, args, left, changes, terminal)
        actual = run(D, args, right, changes, terminal)
        states = [state(left), state(right)]
        compared = [dict(s) for s in states]
        proof = runpy.run_path(str(R / 'tools/index-proof.py'))
        li, ri = (left / '.git/index').read_bytes(), (right / '.git/index').read_bytes()
        index_proofs = [proof['proof'](left, li), proof['proof'](right, ri)]
        try:
            lc, rc, count = proof['canonical_pair'](li, ri, *index_proofs)
        except ValueError as error:
            # An unequal unproven cache is an observable difference, not a
            # reason to lose this row or the rest of the family's captures.
            proof_error = str(error)
            equal = False
        else:
            compared[0]['.git/index'] = [states[0]['.git/index'][0], lc.hex()]
            compared[1]['.git/index'] = [states[1]['.git/index'][0], rc.hex()]
            equal = compared[0] == compared[1]
    else:
        before = state(base)
        expected = run(G, args, changes=changes, terminal=terminal)
        middle = state(base)
        actual = run(D, args, changes=changes, terminal=terminal)
        states = [before, middle, state(base)]
        equal = states[0] == states[1] == states[2]
    ok = expected == actual and equal
    rows.append({'name': name, 'args': args, 'environment': changes, 'terminal': terminal,
                 'expected': expected, 'actual': actual, 'states': states, 'input_state': input_state,
                 'index_proofs': index_proofs, 'index_proof_error': proof_error,
                 'zone_fixture': dict(zone_fixture), 'equal': ok})
    print(('PASS' if ok else 'FAIL'), name, flush=True)
    if not ok:
        print('  expected', expected, 'actual', actual, 'state-equal', equal,
              'index-proof-error', proof_error, flush=True)

def suite():
    assert hashlib.sha256(G.read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    g('init', '-q')
    (base / 'file').write_text('one\ntwo\n')
    g('add', 'file')
    g('commit', '-qm', 'first')
    if a.family == 'dates':
        no_database = (not Path('/usr/share/zoneinfo/UTC').exists() and
                       (not Path('/etc/localtime').exists() or Path('/etc/localtime').stat().st_size == 0))
        if a.require_no_database:
            assert no_database, 'dedicated no-database container required'
        (root / 'empty-zones').mkdir()
        zone_fixture.update(system_zone_database_absent=no_database,
                            empty_tzdir=str(root / 'empty-zones'), required=a.require_no_database)
        print('date fixture: empty TZDIR; system_zone_database_absent=' + str(no_database), flush=True)
        (base / 'file').write_text('one\ntwo\nchanged\n')
        g('stash', 'push', '-qm', 'saved')
        for zone in [None, 'UTC', 'Missing/Zone']:
            changes = {'TZ': zone, 'TZDIR': str(root / 'empty-zones')}
            label = 'unset' if zone is None else zone.replace('/', '-')
            for args in [['log'], ['log', '--date=local'], ['show', '-s'], ['blame', 'file'], ['stash', 'list']]:
                check('date-no-db-' + label + '-' + args[0] + ('-local' if '--date=local' in args else ''), args, changes)
            check('date-no-db-' + label + '-commit',
                  ['commit', '--allow-empty', '--date', '1700000001 +0530', '-m', 'daily'],
                  changes, mutate=True)
    elif a.family == 'decorations':
        g('branch', 'zebra')
        g('branch', 'alpha')
        g('tag', 'light')
        g('tag', '-a', 'annotated', '-m', 'tag')
        g('update-ref', 'refs/remotes/origin/main', 'HEAD')
        g('symbolic-ref', 'refs/remotes/origin/HEAD', 'refs/remotes/origin/main')
        for terminal in [False, True]:
            stream = 'pty' if terminal else 'pipe'
            for options in [[], ['--decorate'], ['--decorate=short'], ['--decorate=full'], ['--decorate=no'], ['--decorate=auto'], ['--no-decorate'], ['--decorate', '--no-decorate'], ['--no-decorate', '--decorate=full']]:
                for style in [[], ['--oneline'], ['--pretty=fuller']]:
                    check('decorate-' + stream + '-' + repr(options + style), ['log', *options, *style], terminal=terminal)
            for setting in ['auto', 'short', 'full', 'no', 'true', 'false']:
                changes = {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'log.decorate', 'GIT_CONFIG_VALUE_0': setting}
                check('decorate-config-' + stream + '-' + setting, ['log', '--oneline'], changes, terminal)
                check('decorate-override-' + stream + '-' + setting, ['log', '--oneline', '--no-decorate'], changes, terminal)
            check('decorate-default-color-' + stream, ['log', '--oneline'], {'GIT_CONFIG_GLOBAL': '/dev/null', 'TERM': 'xterm'}, terminal)
        g('checkout', '-q', '--detach')
        check('decorate-detached', ['log', '--oneline', '--decorate'])
        g('pack-refs', '--all')
        check('decorate-packed', ['log', '--oneline', '--decorate=full'])
    elif a.family == 'config':
        original = (base / '.git/config').read_bytes()
        home = base / 'home'
        home.mkdir()
        (home / '.config/git').mkdir(parents=True)
        changes = {'HOME': str(home), 'XDG_CONFIG_HOME': str(home / '.config'), 'GIT_CONFIG_GLOBAL': None}
        initial = '# keep heading\n[demo]\n\tvalue = old # inline\n\tother = keep\n; final comment\n'.encode()
        cases = [
            ('set-existing', [], 'demo.value', ['new'], initial),
            ('set-section', [], 'fresh.value', ['hello'], initial),
            ('set-subsection', [], 'remote.Mixed.url', ['ssh://example.invalid/repo'], initial),
            ('add', ['--add'], 'demo.value', ['new'], initial),
            ('unset', ['--unset'], 'demo.value', [], initial),
            ('unset-missing', ['--unset'], 'demo.missing', [], initial),
            ('unset-all-missing', ['--unset-all'], 'demo.missing', [], initial),
            ('unset-all', ['--unset-all'], 'demo.value', [], initial + b'[demo]\n\tvalue = second\n'),
            ('replace-all', ['--replace-all'], 'demo.value', ['new'], initial + b'[demo]\n\tvalue = second\n'),
            ('set-multiple', [], 'demo.value', ['new'], initial + b'[demo]\n\tvalue = second\n'),
            ('unset-multiple', ['--unset'], 'demo.value', [], initial + b'[demo]\n\tvalue = second\n'),
            ('set-no-final-lf', [], 'demo.value', ['new'], b'[demo]\nvalue=old'),
            ('set-inline-header', [], 'demo.value', ['new'], b'[demo] value=old\n'),
            ('set-crlf', [], 'demo.value', ['new'], b'[demo]\r\nvalue=old\r\nother=keep\r\n'),
            ('set-continued', [], 'demo.value', ['new'], b'[demo]\nvalue=one\\\n two\nother=keep\n'),
        ]
        for n, value in enumerate(['', ' hello ', 'a#b;c', 'quote"slash\\', 'one\ntwo\tthree\b']):
            cases.append(('quote-' + str(n), [], 'demo.value', [value], initial))
        for scope in ['local', 'global', 'file']:
            for label, op, key, values, content in cases:
                dest = base / '.git/config' if scope == 'local' else home / '.gitconfig' if scope == 'global' else base / 'chosen.config'
                args = ['config', '--' + scope] + (['chosen.config'] if scope == 'file' else []) + op + [key] + values
                def restore():
                    (base / '.git/config').write_bytes(original)
                    dest.write_bytes((original if scope == 'local' else b'') + content)
                restore()
                input_state = state(base)
                expected = run(G, args, changes=changes)
                expected_state = state(base)
                restore()
                actual = run(D, args, changes=changes)
                actual_state = state(base)
                ok = expected == actual and expected_state == actual_state
                name = 'config-' + scope + '-' + label
                rows.append({'name': name, 'args': args, 'environment': dict(changes), 'input': content.hex(), 'input_state': input_state, 'expected': expected, 'actual': actual, 'states': [expected_state, actual_state], 'equal': ok})
                print(('PASS' if ok else 'FAIL'), name, flush=True)
                if not ok:
                    print('  expected', expected, 'actual', actual, flush=True)
                dest.unlink(missing_ok=True)
                (base / '.git/config').write_bytes(original)
        def special(name, args, prepare):
            prepare()
            input_state = state(base)
            expected = run(G, args, changes=changes)
            expected_state = state(base)
            prepare()
            actual = run(D, args, changes=changes)
            actual_state = state(base)
            ok = expected == actual and expected_state == actual_state
            rows.append({'name': name, 'args': args, 'environment': dict(changes),
                         'input_state': input_state, 'expected': expected, 'actual': actual,
                         'states': [expected_state, actual_state], 'equal': ok})
            print(('PASS' if ok else 'FAIL'), name, flush=True)
            if not ok:
                print('  expected', expected, 'actual', actual, flush=True)

        def clear_special():
            for path in [base / 'chosen.config', base / 'target.config', base / 'alias.config', home / '.gitconfig', home / '.config/git/config']:
                path.unlink(missing_ok=True)
            (base / '.git/config').write_bytes(original)

        for destination, options in [(base / 'chosen.config', ['--file', 'chosen.config']), (home / '.gitconfig', ['--global'])]:
            special('config-new-' + ('global' if '--global' in options else 'file'),
                    ['config', *options, 'demo.value', 'new'], clear_special)

        def new_local():
            clear_special()
            (base / '.git/config').unlink()
        special('config-new-local', ['config', '--local', 'demo.value', 'new'], new_local)

        def xdg_only():
            clear_special()
            (home / '.config/git/config').write_bytes(initial)
        changes['XDG_CONFIG_HOME'] = ''
        special('config-global-empty-xdg', ['config', '--global', 'demo.value', 'new'], xdg_only)
        changes['XDG_CONFIG_HOME'] = str(home / '.config')

        def unrelated_bad_local():
            clear_special()
            (base / '.git/config').write_bytes(original + b'[broken\n')
            (base / 'chosen.config').write_bytes(initial)
        special('config-file-bad-local-preflight', ['config', '--file', 'chosen.config', 'demo.value', 'new'], unrelated_bad_local)

        def default_local():
            clear_special()
            (base / '.git/config').write_bytes(original + initial)
        special('config-default-local', ['config', 'demo.value', 'new'], default_local)

        def regular():
            clear_special()
            (base / 'chosen.config').write_bytes(initial)
        def linked():
            regular()
            (base / 'alias.config').hardlink_to(base / 'chosen.config')
        special('config-atomic-hardlink', ['config', '--file', 'chosen.config', 'demo.value', 'new'], linked)

        def symlinked():
            clear_special()
            (base / 'target.config').write_bytes(initial)
            (base / 'chosen.config').symlink_to('target.config')
        special('config-symlink-target', ['config', '--file', 'chosen.config', 'demo.value', 'new'], symlinked)

        def private_mode():
            regular()
            (base / 'chosen.config').chmod(0o600)
        special('config-private-mode', ['config', '--file', 'chosen.config', 'demo.value', 'new'], private_mode)
        clear_special()
        dest = base / 'chosen.config'
        dest.write_bytes(initial)
        (base / 'chosen.config.lock').write_text('foreign lock\n')
        check('config-foreign-lock', ['config', '--file', 'chosen.config', 'demo.value', 'new'])

try:
    suite()
finally:
    (root / 'captures.json').write_text(json.dumps(rows, indent=2) + '\n')
failed = [row['name'] for row in rows if not row['equal']]
print(f'daily {a.family}: {len(rows)-len(failed)}/{len(rows)} exact; zero skips', flush=True)
raise SystemExit(bool(failed))
