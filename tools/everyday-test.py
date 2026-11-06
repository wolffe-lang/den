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
P.add_argument('--family', choices=['upstream', 'config', 'merge', 'combined', 'descriptors'], required=True)
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


def state(top=None):
    # Rows run inside one repository snapshot that repository; others the root.
    files = {}
    for f in sorted((top or root).rglob('*')):
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


def run(exe, args, changes=None, data=None, inherited=False, cwd=None):
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
    q = subprocess.run([str(exe), *args], cwd=cwd or base, env=e, input=data, capture_output=True, timeout=120)
    return {'status': q.returncode, 'stdout': q.stdout.hex(), 'stderr': q.stderr.hex()}


def g(*args, data=None):
    q = run(G, args, data=data)
    assert q['status'] == 0, (args, q)
    return bytes.fromhex(q['stdout']).decode().strip()


def check(name, args, changes=None, data=None, inherited=False, cwd=None):
    before = state(cwd)
    left = run(G, args, changes, data, inherited, cwd)
    middle = state(cwd)
    right = run(D, args, changes, data, inherited, cwd)
    after = state(cwd)
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
        merge = g('commit-tree', g('rev-parse', 'main^{tree}'), '-p', second, '-p', other,
                  data=b'ordered merge\n')
        forms = [['status'], ['status', '-sb'], ['status', '--porcelain', '-b'],
                 ['status', '--porcelain=v2', '--branch'], ['status', '--porcelain=v2', '--branch', '-z'],
                 ['status', '--porcelain'], ['branch'], ['branch', '-v'], ['branch', '-vv'],
                 ['branch', '-a'], ['branch', '-r'], ['branch', '-avv'], ['branch', '-rvv']]
        for label, local, remote in [('equal', first, first), ('ahead', second, first),
                                     ('behind', first, second), ('diverged', second, other),
                                     ('merge-full-dag', merge, second), ('gone', second, None)]:
            g('reset', '--hard', local)
            if remote:
                g('update-ref', 'refs/remotes/origin/main', remote)
            else:
                g('update-ref', '-d', 'refs/remotes/origin/main')
            for n, args in enumerate(forms):
                check('upstream-' + label + '-' + str(n) + '-' + args[0], args)
        g('update-ref', 'refs/remotes/origin/main', first)
        (base / 'file').write_text('unstaged\n')
        (base / 'added').write_text('staged\n')
        (base / 'untracked').write_text('untracked\n')
        g('add', 'added')
        check('upstream-v2-dirty', ['status', '--porcelain=v2', '--branch'])
        check('upstream-v2-dirty-nul', ['status', '--porcelain=v2', '--branch', '-z'])
        g('reset', '--hard', 'HEAD')
        (base / 'untracked').unlink()
        g('config', 'branch.main.remote', '.')
        g('config', 'branch.main.merge', 'refs/heads/other')
        g('update-ref', 'refs/heads/other', first)
        check('upstream-local-status', ['status'])
        check('upstream-local-branch', ['branch', '-vv'])
        g('checkout', '-q', '--detach')
        check('upstream-detached-status', ['status', '--porcelain=v2', '--branch'])
        check('upstream-detached-branch', ['branch', '-avv'])
        # A configured clone of a local bare peer, then push and fetch move the
        # tracking ref; every state is read by both tools from the same tree.
        def gx(cwd, *args):
            q = subprocess.run([str(G), *args], cwd=cwd, env=env, capture_output=True, timeout=120)
            assert q.returncode == 0, (args, q.stderr)
        shutil.rmtree(base)
        origin, seed = root / 'origin.git', root / 'seed'
        gx(root, 'init', '-q', '--bare', '-b', 'main', str(origin))
        gx(root, 'clone', '-q', str(origin), str(seed))
        (seed / 'file').write_text('seed\n')
        gx(seed, 'add', 'file')
        gx(seed, 'commit', '-qm', 'seed')
        gx(seed, 'push', '-q', 'origin', 'main')
        gx(root, 'clone', '-q', str(origin), str(base))
        tracked = [['status'], ['status', '-sb'], ['status', '--porcelain=v2', '--branch'],
                   ['branch', '-vv'], ['branch', '-avv']]
        def states(label):
            for n, args in enumerate(tracked):
                check('upstream-clone-' + label + '-' + str(n) + '-' + args[0], args)
        states('fresh')
        commit('local ahead', 'local\n')
        states('ahead')
        gx(base, 'push', '-q')
        states('pushed')
        gx(seed, 'pull', '-q', '--rebase')
        (seed / 'peer').write_text('peer\n')
        gx(seed, 'add', 'peer')
        gx(seed, 'commit', '-qm', 'peer moves')
        gx(seed, 'push', '-q', 'origin', 'main')
        gx(base, 'fetch', '-q')
        states('fetched-behind')
        commit('local diverges', 'diverged\n')
        states('fetched-diverged')
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
    elif a.family == 'combined':
        combined()
    else:
        (base / '.gitignore').write_text('ignored\n')
        check('fd-status-inherited', ['status'], inherited=True)
        check('fd-check-ignore-inherited', ['check-ignore', '-v', 'ignored'], inherited=True)
        check('fd-check-ignore-stdin-inherited', ['check-ignore', '--stdin'], data=b'ignored\n', inherited=True)


def combined():
    """Merges built by the pinned Git; each shown with dense (default, --cc) and -c."""
    import runpy
    L = lambda *xs: ''.join(x + '\n' for x in xs)
    n = ['line %d' % i for i in range(1, 41)]

    def sub(lines, changes):
        out = list(lines)
        for i, v in sorted(changes.items(), reverse=True):
            if v is None:
                del out[i]
            elif isinstance(v, list):
                out[i:i + 1] = v
            else:
                out[i] = v
        return L(*out)

    def gx(repo, *args, data=None, ok=(0,)):
        q = subprocess.run([str(G), *args], cwd=repo, env=env, input=data, capture_output=True, timeout=120)
        assert q.returncode in ok, (args, q)
        return q.stdout.decode().strip()

    def put(repo, files):
        for k, v in files.items():
            path = repo / k
            if v is None:
                if path.exists():
                    path.unlink()
                continue
            mode = None
            if isinstance(v, tuple):
                v, mode = v
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(v.encode() if isinstance(v, str) else v)
            path.chmod(mode or 0o644)
        gx(repo, 'add', '-A')

    def merge(name, base_files, parents, result):
        repo = root / ('m-' + name)
        repo.mkdir()
        gx(repo, 'init', '-q', '-b', 'main')
        put(repo, base_files)
        gx(repo, 'commit', '-q', '--allow-empty', '-m', 'base')
        tips = []
        for k, files in enumerate(parents):
            gx(repo, 'checkout', '-q', '--detach', 'main')
            put(repo, files)
            gx(repo, 'commit', '-q', '--allow-empty', '-m', 'parent %d' % k)
            tips.append(gx(repo, 'rev-parse', 'HEAD'))
        gx(repo, 'checkout', '-q', 'main')
        gx(repo, 'reset', '-q', '--hard', tips[0])
        put(repo, result)
        tree = gx(repo, 'write-tree')
        argv = ['commit-tree', tree]
        for tip in tips:
            argv += ['-p', tip]
        tip = gx(repo, *argv, data=('merge ' + name + '\n').encode())
        gx(repo, 'reset', '-q', '--hard', tip)
        return repo

    def show_rows(name, repo, extra=()):
        for flags in [[], ['--cc'], ['-c'], *extra]:
            label = 'default' if not flags else '_'.join(f.lstrip('-') for f in flags)
            check('combined-' + name + '-' + label, ['show', *flags], cwd=repo)

    def two(name, base_files, left, right, result, extra=()):
        show_rows(name, merge(name, base_files, [left, right], result), extra)

    f = L(*n)
    two('clean-two-sides', {'f': f}, {'f': sub(n, {1: 'LEFT 2'})}, {'f': sub(n, {25: 'RIGHT 26'})},
        {'f': sub(n, {1: 'LEFT 2', 25: 'RIGHT 26'})})
    two('pick-and-resolve', {'f': f}, {'f': sub(n, {1: 'LEFT 2', 20: 'LEFT 21'})},
        {'f': sub(n, {1: 'RIGHT 2', 20: 'RIGHT 21'})}, {'f': sub(n, {1: 'LEFT 2', 20: 'BOTH 21'})})
    two('one-side-and-evil', {'f': f, 'g': L('g1', 'g2', 'g3')}, {'f': sub(n, {3: 'LEFT 4'})}, {},
        {'g': L('g1', 'EVIL', 'g3')})
    two('new-and-delete', {'f': f, 'gone': L('x', 'y')},
        {'f': sub(n, {0: 'L1'}), 'gone': L('x', 'y', 'left')},
        {'f': sub(n, {29: 'R30'}), 'gone': L('right', 'x', 'y')}, {'new': L('n1', 'n2'), 'gone': None})
    two('removals', {'f': f}, {'f': sub(n, {5: None, 9: 'L10'})}, {'f': sub(n, {5: None, 9: 'R10'})},
        {'f': sub(n, {5: None, 9: ['M10a', 'M10b']})})
    two('several-hunks', {'f': f}, {'f': sub(n, {2: 'L3', 15: 'L16', 33: 'L34'})},
        {'f': sub(n, {2: 'R3', 15: 'R16', 33: 'R34'})}, {'f': sub(n, {2: 'M3', 15: 'L16', 33: 'M34'})})
    two('noeol', {'f': 'a\nb\nc'}, {'f': 'a\nb\nleft'}, {'f': 'a\nb\nright'}, {'f': 'a\nb\nboth'})
    two('eol-mixed', {'f': 'a\nb\n'}, {'f': 'a\nleft'}, {'f': 'a\nb\nright\n'}, {'f': 'a\nb\nboth\n'})
    two('eol-same', {'f': 'a\nb\n'}, {'f': 'a\nb'}, {'f': 'a\nb\nr\n'}, {'f': 'a\nb\nm\n'})
    two('mode', {'f': L('a', 'b', 'c')}, {'f': L('main', 'b', 'c')}, {'f': (L('a', 'b', 'side'), 0o755)},
        {'f': (L('main', 'b', 'merged'), 0o755)})
    two('mode-only', {'f': L('a', 'b', 'c')}, {'f': L('main', 'b', 'c')}, {'f': (L('a', 'b', 'side'), 0o755)},
        {'f': (L('a', 'b', 'side'), 0o644)})
    two('added-side', {'f': L('a')}, {'f': L('a', 'left')}, {'n': L('n1', 'n2', 'n3')},
        {'n': L('n1', 'N2', 'n3')})
    two('delete-modify', {'f': L('a'), 'd': L('d1', 'd2')}, {'f': L('a', 'l'), 'd': None},
        {'d': L('d1', 'D2')}, {'f': L('a', 'l'), 'd': None})
    two('gap6', {'f': f}, {'f': sub(n, {2: 'L3', 9: 'L10'})}, {'f': sub(n, {2: 'R3', 9: 'R10'})},
        {'f': sub(n, {2: 'M3', 9: 'M10'})})
    two('gap7', {'f': f}, {'f': sub(n, {2: 'L3', 10: 'L11'})}, {'f': sub(n, {2: 'R3', 10: 'R11'})},
        {'f': sub(n, {2: 'M3', 10: 'M11'})}, extra=(['-U1'], ['-c', '-U0']))
    two('zero-insert', {'f': f}, {'f': sub(n, {15: 'L16'})}, {'f': sub(n, {15: 'R16'})},
        {'f': sub(n, {15: 'L16', 7: ['line 8', 'NEW']})}, extra=(['-c', '-U0'], ['--cc', '-U0']))
    two('zero-delete', {'f': f}, {'f': sub(n, {15: 'L16'})}, {'f': sub(n, {15: 'R16'})},
        {'f': sub(n, {15: 'L16', 7: None})}, extra=(['-c', '-U0'], ['--cc', '-U0']))
    for gap in (2, 3, 4):
        p, r = 4, 4 + gap + 1
        two('dense-gap%d' % gap, {'f': f}, {'f': sub(n, {p: 'LP', r: 'LR'})}, {'f': sub(n, {p: 'RP', r: 'RR'})},
            {'f': sub(n, {p: 'LP', r: 'MR'})}, extra=(['--cc', '-U1'], ['--cc', '-U5']))
        two('dense-gap%d-after' % gap, {'f': f}, {'f': sub(n, {r: 'LP', p: 'LR'})}, {'f': sub(n, {r: 'RP', p: 'RR'})},
            {'f': sub(n, {r: 'LP', p: 'MR'})})
    for gap in (0, 2, 3):
        two('picks-gap%d' % gap, {'f': f}, {'f': sub(n, {4: 'LA'})}, {'f': sub(n, {5 + gap: 'RB'})},
            {'f': sub(n, {4: 'LA', 5 + gap: 'RB'})}, extra=(['--cc', '-U0'],))
    two('chain', {'f': f}, {'f': sub(n, {10: 'LA', 13: 'LB', 16: 'LC'})}, {'f': sub(n, {10: 'RA', 13: 'RB', 16: 'RC'})},
        {'f': sub(n, {10: 'LA', 13: 'RB', 16: 'MC'})})
    two('lost-chunk', {'f': f}, {'f': sub(n, {5: 'LP', 9: None})}, {'f': sub(n, {5: 'RP', 9: None})},
        {'f': sub(n, {5: 'LP', 9: None, 10: None})})
    two('lost-end', {'f': L(*n[:10])}, {'f': L(*(n[:9] + ['L10']))}, {'f': L(*(n[:9] + ['R10']))}, {'f': L(*n[:8])})
    two('lost-tie', {'f': L('s', 'x', 'e')}, {'f': L('s', 'a', 'b', 'e')}, {'f': L('s', 'b', 'a', 'e')},
        {'f': L('s', 'M', 'e')})
    two('lost-many', {'f': L('s', 'x', 'e')}, {'f': L('s', 'a', 'b', 'c', 'd', 'e')},
        {'f': L('s', 'c', 'q', 'a', 'd', 'e')}, {'f': L('s', 'M', 'e')})
    two('mid-lost', {'f': f}, {'f': sub(n, {4: 'L5', 8: None, 11: 'L12'})}, {'f': sub(n, {4: 'R5', 11: 'R12'})},
        {'f': sub(n, {4: 'M5', 8: None, 11: 'M12'})})
    two('mid-pick', {'f': f}, {'f': sub(n, {4: 'L5', 8: 'L9', 11: 'L12'})}, {'f': sub(n, {4: 'R5', 8: 'R9', 11: 'R12'})},
        {'f': sub(n, {4: 'M5', 8: 'L9', 11: 'M12'})})
    two('start-lost', {'f': f}, {'f': sub(n, {5: None, 9: 'L10'})}, {'f': sub(n, {9: 'R10'})},
        {'f': sub(n, {5: None, 9: 'M10'})}, extra=(['--cc', '-U2'], ['--cc', '-U4']))
    two('end-lost', {'f': f}, {'f': sub(n, {5: 'L6', 9: None})}, {'f': sub(n, {5: 'R6'})},
        {'f': sub(n, {5: 'M6', 9: None})}, extra=(['--cc', '-U2'], ['--cc', '-U4']))
    for d in (3, 4, 5):
        two('lost-near-d%d' % d, {'f': f}, {'f': sub(n, {4: None, 4 + d: 'L'})}, {'f': sub(n, {4 + d: 'R'})},
            {'f': sub(n, {4: None, 4 + d: 'M'})}, extra=(['--cc', '-U2'],))
        two('lost-near-d%d-after' % d, {'f': f}, {'f': sub(n, {4: 'L', 4 + d: None})}, {'f': sub(n, {4: 'R'})},
            {'f': sub(n, {4: 'M', 4 + d: None})}, extra=(['--cc', '-U2'],))
    touch = n[:9] + ['A1', 'A2'] + n[9:]
    two('touch-U0', {'f': f}, {'f': sub(touch, {25: 'L'})}, {'f': L(*(n[:8] + ['Q1', 'Q2'] + n[8:]))},
        {'f': L(*touch)}, extra=(['-c', '-U0'], ['--cc', '-U0'], ['-c', '-U1']))
    e = ['line %d' % i for i in range(1, 13)]
    X = (['-c', '-U0'], ['--cc', '-U0'], ['-c', '-U1'])
    two('eof-lost-only', {'f': L(*e)}, {'f': sub(e, {2: 'L'})}, {'f': sub(e, {2: 'R'})},
        {'f': sub(e, {2: 'M', 11: None})}, extra=X)
    two('eof-flag-lost', {'f': L(*e)}, {'f': sub(e, {2: 'L'})}, {'f': sub(e, {2: 'R'})},
        {'f': sub(e, {2: 'M', 10: 'END', 11: None})}, extra=X)
    two('eof-flag-only', {'f': L(*e)}, {'f': sub(e, {2: 'L', 11: 'L12'})}, {'f': sub(e, {2: 'R', 11: 'R12'})},
        {'f': sub(e, {2: 'M', 11: 'M12'})}, extra=X)
    two('eof-p2-lost', {'f': L(*e)}, {'f': sub(e, {2: 'L'})}, {'f': L(*(e[:2] + ['R'] + e[3:] + ['T1', 'T2']))},
        {'f': sub(e, {2: 'M'})}, extra=X)
    two('eof-dropped-lost', {'f': L(*e)}, {'f': sub(e, {2: 'L', 11: None})}, {'f': sub(e, {2: 'R'})},
        {'f': sub(e, {2: 'M', 11: None})}, extra=(['--cc', '-U9'], ['--cc', '-U8'], ['-c', '-U9']))
    two('eof-mid-lost', {'f': L(*e)}, {'f': sub(e, {2: 'L'})}, {'f': sub(e, {2: 'R'})},
        {'f': sub(e, {2: 'M', 9: None})}, extra=X)
    two('eol-coalesce', {'f': L('y', 'w')}, {'f': 'y'}, {'f': L('y', 'w')}, {'f': L('b')})
    two('eol-coalesce2', {'f': L('s', 'y', 'w')}, {'f': 's\ny'}, {'f': L('s', 'y', 'q')}, {'f': L('s', 'b')})
    ind = lambda tag, k: ['  %s%d' % (tag, i) for i in range(k)]
    t = ['func_a'] + ind('a', 9) + ['  plain'] + ind('b', 19)
    two('heading-result', {'f': L(*t)}, {'f': sub(t, {25: '  L'})}, {'f': sub(t, {25: '  R'})},
        {'f': sub(t, {10: 'resfn', 25: '  M'})}, extra=(['--cc', '-U1'],))
    two('heading-boundary', {'f': L(*t)}, {'f': sub(t, {10: 'leftfn', 25: '  L'})}, {'f': sub(t, {25: '  R'})},
        {'f': sub(t, {10: 'leftfn', 25: '  M'})})
    for size in (39, 41):
        t = ['h' * size] + ind('c', 12)
        two('heading-cap%d' % size, {'f': L(*t)}, {'f': sub(t, {10: '  L'})}, {'f': sub(t, {10: '  R'})},
            {'f': sub(t, {10: '  M'})})
    t = ['h' * 38 + '    tail', '$dollar   '] + ind('c', 12)
    two('heading-trim', {'f': L(*t)}, {'f': sub(t, {6: '  L', 12: '  L'})}, {'f': sub(t, {6: '  R', 12: '  R'})},
        {'f': sub(t, {6: '  M', 12: '  M'})}, extra=(['-U1'],))
    two('heading-crlf', {'f': 'crfn\r\n' + L(*ind('e', 10))}, {'f': 'crfn\r\n' + sub(ind('e', 10), {7: 'L'})},
        {'f': 'crfn\r\n' + sub(ind('e', 10), {7: 'R'})}, {'f': 'crfn\r\n' + sub(ind('e', 10), {7: '  M'})})
    two('space path', {'s p': L('a', 'b')}, {'s p': L('l', 'b')}, {'s p': L('r', 'b')}, {'s p': L('m', 'b')})
    two('binary', {'b.bin': 'a\0b\n'}, {'b.bin': 'l\0b\n'}, {'b.bin': 'r\0b\n'}, {'b.bin': 'm\0b\n'})
    two('disjoint', {'f': L('a'), 'g': L('b')}, {'f': L('a', 'l')}, {'g': L('b', 'r')}, {'f': L('a', 'l'), 'g': L('b', 'r')})
    m = ['line %d' % i for i in range(1, 31)]
    show_rows('octopus', merge('octopus', {'f': L(*m[:10]), 'a': L('a')}, [{'b1': L('b1')}, {'b2': L('b2')}, {'b3': L('b3')}],
                          {'f': sub(m[:10], {4: 'OCTO'}), 'b1': L('b1', 'more'), 'b2': L('b2'), 'b3': L('b3')}))
    for label, versions, result in [('2v-pick-a', 'ABA', 'A'), ('2v-pick-b', 'ABA', 'B'),
                                    ('3v-pick-a', 'ABC', 'A'), ('2v-new', 'ABA', 'M')]:
        show_rows('octopus-' + label, merge('octopus-' + label, {'f': L(*m), 'g': L('g')},
             [{'f': sub(m, {2: 'P%d' % k, 20: v}), 'g': L('g', str(k))} for k, v in enumerate(versions)],
             {'f': sub(m, {2: 'NEW', 20: result}), 'g': L('g', 'M')}))
    show_rows('octopus-deleted', merge('octopus-deleted', {'f': L('a', 'b')},
         [{'f': L('a', 'b', '1')}, {'f': L('a', 'b', '2')}, {'f': L('3')}], {'f': None}))
    nonmerge = root / 'm-nonmerge'
    nonmerge.mkdir()
    gx(nonmerge, 'init', '-q', '-b', 'main')
    put(nonmerge, {'f': L('a', 'b')})
    gx(nonmerge, 'commit', '-qm', 'one')
    put(nonmerge, {'f': L('a', 'c')})
    gx(nonmerge, 'commit', '-qm', 'two')
    show_rows('nonmerge', nonmerge)
    # Seeded random merges: a small repetitive vocabulary forces removal-list
    # ties, funcname candidates, end-of-file and missing-newline edges.
    import random
    words = ['a', 'b', 'c', 'x', 'y', '{', '}', '', 'func_q', '  z', 'int k(void)', '\tw']

    def mutate(rng, lines):
        out = list(lines)
        for _ in range(rng.randint(0, 4)):
            op = rng.random()
            at = rng.randint(0, len(out))
            if op < 0.4 and out:
                at = min(at, len(out) - 1)
                out[at] = rng.choice(words)
            elif op < 0.7:
                out[at:at] = [rng.choice(words) for _ in range(rng.randint(1, 3))]
            elif out:
                del out[min(at, len(out) - 1):min(at, len(out) - 1) + rng.randint(1, 3)]
        return out

    def body(rng, lines):
        text = ''.join(x + '\n' for x in lines)
        return text[:-1] if text and rng.random() < 0.15 else text

    for seed in range(int(os.environ.get('DEN_COMBINED_SEEDS', '48'))):
        rng = random.Random(seed)
        base_lines = [rng.choice(words) for _ in range(rng.randint(0, 40))]
        count = 3 if seed % 6 == 5 else 2
        versions = [mutate(rng, base_lines) for _ in range(count)]
        pick = rng.choice(versions)
        final = mutate(rng, pick) if rng.random() < 0.8 else mutate(rng, base_lines)
        parents = [{'f': body(rng, v)} for v in versions]
        if rng.random() < 0.2:
            parents[rng.randrange(count)]['f'] = None
        repo = merge('fuzz-%d' % seed, {'f': body(rng, base_lines)}, parents, {'f': body(rng, final)})
        context = rng.choice([0, 1, 2, 3, 3, 3, 5])
        # Combined columns are the per-parent line diffs. Where den's two-tree
        # diff already aligns an equal-cost script differently (R-vc04-3), the
        # combined row is a named review row, never counted either way.
        inherited = []
        for j in range(1, count + 1):
            argv = ['diff', 'HEAD^%d' % j, 'HEAD']
            if run(G, argv, cwd=repo) != run(D, argv, cwd=repo):
                inherited.append(j)
        for flags in [['--cc', '-U%d' % context], ['-c', '-U%d' % context]]:
            name = 'combined-fuzz-%d-%s' % (seed, flags[0].lstrip('-'))
            if not inherited:
                check(name, ['show', *flags], cwd=repo)
                continue
            left, right = run(G, ['show', *flags], cwd=repo), run(D, ['show', *flags], cwd=repo)
            rows.append(dict(name=name, argv=['show', *flags], review='R-vc04-3 parents %s' % inherited,
                             expected=left, actual=right, equal=left == right))
            print('REVIEW', name, 'inherited-alignment parents=' + ','.join(map(str, inherited)),
                  'equal=' + str(left == right), flush=True)
    # The corpus's own merge fixture (tools/corpus.py: two disjoint additions).
    corpus = runpy.run_path(str(R / 'tools/corpus.py'))
    corpus['build'](root / 'corpus')
    show_rows('corpus-merge', root / 'corpus' / 'merge')
    for flags in [['-s'], ['--cc', '-s'], ['HEAD^1'], ['HEAD^2']]:
        check('combined-corpus-merge-' + '_'.join(f.lstrip('-') for f in flags), ['show', *flags],
              cwd=root / 'corpus' / 'merge')


try:
    suite()
finally:
    output = R / 'target/runs' / ('everyday-' + a.family + '-' + a.tier + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'rows': rows, 'environment': env}, indent=2) + '\n')
raise SystemExit(0 if rows and all(row['equal'] or row.get('review') for row in rows) else 1)
