"""vc18 exact read-only porcelain rows; Git is a pinned Linux black box."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

P = argparse.ArgumentParser()
P.add_argument('--tier', default='native')
P.add_argument('--family', choices=['upstream', 'config', 'merge', 'descriptors'], required=True)
a = P.parse_args()
R = Path(__file__).resolve().parent.parent
G = Path(os.environ['DEN_GIT'])
D = R / 'target' / a.tier / 'den'
assert hashlib.sha256(G.read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
root = R / 'target' / ('everyday-' + a.family + '-' + a.tier)
if root.exists():
    shutil.rmtree(root)
root.mkdir(parents=True)
base = root / 'repo'
base.mkdir()
rows = []
env = dict(os.environ)


def state():
    files = {}
    for f in sorted(root.rglob('*')):
        name = f.relative_to(root).as_posix()
        if name in ('held-input', 'held-output'):
            continue  # Explicit process stream captures, not repository paths.
        if f.is_symlink():
            files[name] = ['symlink', os.readlink(f)]
        elif f.is_file():
            files[name] = [f.stat().st_mode & 0o7777, f.read_bytes().hex()]
        elif f.is_dir():
            files[name] = ['directory', f.stat().st_mode & 0o7777]
    return files


def run(exe, args, changes=None, data=None, inherited=False):
    e = dict(env)
    for key, value in (changes or {}).items():
        if value is None:
            e.pop(key, None)
        else:
            e[key] = value
    if inherited:
        # The runner is container root; the actual tools run without privilege.
        assert os.geteuid() == 0, 'descriptor rows require container root for uid drop'
        count = int(e.get('GIT_CONFIG_COUNT', '0'))
        e['GIT_CONFIG_COUNT'] = str(count + 1)
        e['GIT_CONFIG_KEY_' + str(count)] = 'safe.directory'
        e['GIT_CONFIG_VALUE_' + str(count)] = str(base)
        out = root / 'held-output'
        inp = root / 'held-input'
        out.write_bytes(b'')
        inp.write_bytes(data or b'')
        os.chown(out, 65534, 65534)
        os.chown(inp, 65534, 65534)
        out.chmod(0o600)
        inp.chmod(0o600)
        def drop():
            os.setgroups([])
            os.setgid(65534)
            os.setuid(65534)
        with out.open('wb') as stdout, inp.open('rb') as stdin:
            out.chmod(0o400)
            inp.chmod(0o200)
            probe = subprocess.run(['python3', '-I', '-c',
                'import os\nfor p,m in [("/dev/stdout",os.O_WRONLY),("/dev/stdin",os.O_RDONLY)]:\n'
                ' try: os.open(p,m)\n except PermissionError: continue\n'
                ' raise SystemExit("reopen unexpectedly allowed")\n'],
                cwd=base, env=e, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE,
                preexec_fn=drop, timeout=20)
            assert probe.returncode == 0, probe.stderr
            q = subprocess.run([str(exe), *args], cwd=base, env=e, stdin=stdin,
                stdout=stdout, stderr=subprocess.PIPE, preexec_fn=drop, timeout=60)
        result = {'status': q.returncode, 'stdout': out.read_bytes().hex(), 'stderr': q.stderr.hex()}
        out.chmod(0o600)
        inp.chmod(0o600)
        return result
    q = subprocess.run([str(exe), *args], cwd=base, env=e, input=data, capture_output=True, timeout=120)
    return {'status': q.returncode, 'stdout': q.stdout.hex(), 'stderr': q.stderr.hex()}


def g(*args, data=None):
    q = run(G, args, data=data)
    assert q['status'] == 0, (args, q)
    return bytes.fromhex(q['stdout']).decode().strip()


def check(name, args, changes=None, data=None, inherited=False):
    before = state()
    left = run(G, args, changes, data, inherited)
    middle = state()
    right = run(D, args, changes, data, inherited)
    after = state()
    ok = left == right and before == middle == after
    rows.append(dict(name=name, argv=args, environment=changes or {}, stdin=(data or b'').hex(),
                     inherited=inherited, expected=left, actual=right,
                     before=before, middle=middle, after=after, equal=ok))
    print(('PASS' if ok else 'FAIL') + ' ' + name, flush=True)
    if not ok:
        print('  expected', left, 'actual', right, 'immutable', before == middle == after, flush=True)


def commit(message, content):
    (base / 'file').write_text(content)
    g('add', 'file')
    g('commit', '-qm', message)
    return g('rev-parse', 'HEAD')


def suite():
    g('init', '-q', '-b', 'main')
    first = commit('first', 'one\ntwo\nthree\n')
    if a.family == 'upstream':
        g('config', 'remote.origin.url', 'file:///synthetic-peer.git')
        g('config', 'remote.origin.fetch', '+refs/heads/*:refs/remotes/origin/*')
        g('config', 'branch.main.remote', 'origin')
        g('config', 'branch.main.merge', 'refs/heads/main')
        g('update-ref', 'refs/remotes/origin/main', first)
        second = commit('second', 'one\ntwo\nchanged\n')
        g('checkout', '-q', '--detach', first)
        other = commit('other', 'other\ntwo\nthree\n')
        g('checkout', '-q', 'main')
        forms = [['status'], ['status', '-sb'], ['status', '--porcelain', '-b'],
                 ['status', '--porcelain=v2', '--branch'], ['status', '--porcelain=v2', '--branch', '-z'],
                 ['status', '--porcelain'], ['branch'], ['branch', '-v'], ['branch', '-vv'],
                 ['branch', '-a'], ['branch', '-r'], ['branch', '-avv'], ['branch', '-rvv']]
        for label, local, remote in [('equal', first, first), ('ahead', second, first),
                                     ('behind', first, second), ('diverged', second, other),
                                     ('gone', second, None)]:
            g('reset', '--hard', local)
            if remote:
                g('update-ref', 'refs/remotes/origin/main', remote)
            else:
                g('update-ref', '-d', 'refs/remotes/origin/main')
            for n, args in enumerate(forms):
                check('upstream-' + label + '-' + str(n) + '-' + args[0], args)
        g('config', 'branch.main.remote', '.')
        g('config', 'branch.main.merge', 'refs/heads/other')
        g('update-ref', 'refs/heads/other', first)
        check('upstream-local-status', ['status'])
        check('upstream-local-branch', ['branch', '-vv'])
        g('checkout', '-q', '--detach')
        check('upstream-detached-status', ['status', '--porcelain=v2', '--branch'])
        check('upstream-detached-branch', ['branch', '-avv'])
    elif a.family == 'config':
        home = root / 'home'
        (home / '.config/git').mkdir(parents=True)
        system = root / 'system-config'
        system.write_text('[sample]\n duplicate = system\n implicit\n')
        (home / '.config/git/config').write_text('[sample]\n duplicate = xdg\n empty =\n')
        (home / '.gitconfig').write_text('[sample]\n duplicate = home\n mixed = "a\\nb\\tend"\n')
        with (base / '.git/config').open('a') as out:
            out.write('[sample "Case"]\n Duplicate = local\n flag\n empty = ""\n')
        changes = {'HOME': str(home), 'XDG_CONFIG_HOME': '', 'GIT_CONFIG_NOSYSTEM': '0',
                   'GIT_CONFIG_SYSTEM': str(system), 'GIT_CONFIG_GLOBAL': str(home / '.gitconfig'),
                   'GIT_CONFIG_COUNT': '2', 'GIT_CONFIG_KEY_0': 'sample.duplicate',
                   'GIT_CONFIG_VALUE_0': 'runtime', 'GIT_CONFIG_KEY_1': 'sample.empty', 'GIT_CONFIG_VALUE_1': ''}
        for scope in [[], ['--local'], ['--global'], ['--system'], ['--file', str(system)]]:
            for flags in [[], ['--show-origin'], ['--show-scope'], ['--name-only'],
                          ['--show-scope', '--show-origin', '--name-only']]:
                for spelling in ['--list', '-l']:
                    args = ['config', *scope, spelling, *flags]
                    check('config-list-' + '-'.join(args[1:]), args, changes)
        changes['GIT_CONFIG_GLOBAL'] = '/dev/null'
        check('config-list-xdg-home', ['config', '--list', '--show-origin', '--show-scope'],
              dict(changes, GIT_CONFIG_GLOBAL=None))
    elif a.family == 'merge':
        g('checkout', '-qb', 'side')
        commit('side', 'one\nside\nthree\n')
        g('checkout', '-q', 'main')
        commit('main', 'one\nmain\nthree\n')
        q = run(G, ['merge', '--no-edit', 'side'])
        assert q['status'] == 1, q
        check('merge-conflict-guidance', ['status'])
        check('merge-conflict-guidance-no-hints', ['status'], {'GIT_CONFIG_COUNT': '1',
              'GIT_CONFIG_KEY_0': 'advice.statusHints', 'GIT_CONFIG_VALUE_0': 'false'})
        (base / 'file').write_text('one\nresolved\nthree\n')
        g('add', 'file')
        check('merge-resolved-guidance', ['status'])
        g('commit', '-qm', 'resolved merge')
        for flags in [[], ['--cc'], ['-c'], ['-s']]:
            check('show-merge-' + ('default' if not flags else flags[0]), ['show', *flags])
    else:
        (base / '.gitignore').write_text('ignored\n')
        check('fd-status-inherited', ['status'], inherited=True)
        check('fd-check-ignore-inherited', ['check-ignore', '-v', 'ignored'], inherited=True)
        check('fd-check-ignore-stdin-inherited', ['check-ignore', '--stdin'], data=b'ignored\n', inherited=True)


try:
    suite()
finally:
    output = R / 'target/runs' / ('everyday-' + a.family + '-' + a.tier + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'rows': rows, 'environment': env}, indent=2) + '\n')
raise SystemExit(0 if rows and all(row['equal'] for row in rows) else 1)
