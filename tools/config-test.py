"""Independent documented config expectations; no Git or oracle invocation.

Run after tools/build and the config unit program, inside the lane container.
Every fixture is newly created under target; no caller config is inherited.
This is not differential evidence. The orchestrator measures Git parity.
"""
import argparse
import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--tier', choices=['native', 'release'], required=True)
args = parser.parse_args()
DEN = ROOT / 'target' / args.tier / 'den'

with tempfile.TemporaryDirectory(prefix=f'config-{args.tier}-', dir=ROOT / 'target') as tmp:
    root = pathlib.Path(tmp)
    home = root / 'home'
    xdg = root / 'xdg'
    repo = root / 'repo'
    outside = root / 'outside'
    gd = repo / '.git'
    for path in (home, xdg / 'git', gd / 'objects', outside):
        path.mkdir(parents=True)
    (gd / 'HEAD').write_bytes(b'ref: refs/heads/main\n')
    global_file = root / 'global'
    system_file = root / 'system'
    system_file.write_bytes(b'[test]\npriority=system\nsystem=present\n')
    global_file.write_bytes(b'[test]\npriority=global\nglobal=present\n')
    (home / '.gitconfig').write_bytes(b'[test]\npriority=home\nhome=present\n')
    (xdg / 'git/config').write_bytes(b'[test]\npriority=xdg\nxdg=present\n')
    base_config = b'[core]\nrepositoryformatversion=0\n[test]\npriority=repo\n'
    (gd / 'config').write_bytes(base_config)
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(xdg), LC_ALL='C',
               GIT_CONFIG_GLOBAL=str(global_file), GIT_CONFIG_SYSTEM=str(system_file),
               GIT_CONFIG_NOSYSTEM='1')
    rows = []

    def snapshot():
        return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mode,
                                         p.stat().st_mtime_ns)
                for p in root.rglob('*') if p.is_file()}

    def run(command, *, expected=0, stdout=b'', cwd=repo, changes=None, error=None):
        e = dict(env)
        for key, value in (changes or {}).items():
            if value is None:
                e.pop(key, None)
            else:
                e[key] = value
        before = snapshot()
        result = subprocess.run([str(DEN), *command], cwd=cwd, env=e,
                                capture_output=True, timeout=20)
        assert result.returncode == expected, (command, result.returncode, result.stdout, result.stderr)
        assert result.stdout == stdout, (command, result.stdout, stdout)
        assert b'trap' not in result.stderr.lower(), (command, result.stderr)
        if error is None:
            assert result.stderr == b'', (command, result.stderr)
        else:
            assert error in result.stderr, (command, result.stderr, error)
        assert snapshot() == before, ('config command wrote fixture files', command)
        rows.append(command)
        return result

    def get(key, value=None, **kwargs):
        if value is None:
            return run(['config', '--get', key], expected=1, **kwargs)
        return run(['config', '--get', key], stdout=value + b'\n', **kwargs)

    get('TEST.Priority', b'repo')
    get('test.priority', b'global', cwd=outside)
    get('test.global', b'present')
    get('test.system')
    get('test.missing')
    get('test.priority', b'env-last', changes={
        'GIT_CONFIG_COUNT': '2', 'GIT_CONFIG_KEY_0': 'TEST.Priority',
        'GIT_CONFIG_VALUE_0': 'env-first', 'GIT_CONFIG_KEY_1': 'test.priority',
        'GIT_CONFIG_VALUE_1': 'env-last'})
    get('test.raw', b'"literal" #;\\n\nsecond', changes={
        'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'test.raw',
        'GIT_CONFIG_VALUE_0': '"literal" #;\\n\nsecond'})
    get('test.empty', b'', changes={
        'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'test.empty', 'GIT_CONFIG_VALUE_0': ''})
    get('test.priority', b'repo', changes={'GIT_CONFIG_COUNT': ''})
    get('test.priority', b'repo', changes={'GIT_CONFIG_COUNT': '0'})
    get('test.system', b'present', changes={'GIT_CONFIG_NOSYSTEM': 'false'})
    get('test.system', b'present', changes={'GIT_CONFIG_NOSYSTEM': None})
    get('test.system', changes={'GIT_CONFIG_NOSYSTEM': 'true'})
    get('test.priority', b'home', cwd=outside, changes={'GIT_CONFIG_GLOBAL': None})
    get('test.xdg', b'present', changes={'GIT_CONFIG_GLOBAL': None})
    get('test.home', b'present', changes={'GIT_CONFIG_GLOBAL': None})
    get('test.global', changes={'GIT_CONFIG_GLOBAL': ''})
    get('test.home', changes={'GIT_CONFIG_GLOBAL': ''})
    get('test.global', changes={'GIT_CONFIG_GLOBAL': str(root / 'missing')})

    config = base_config + b'''
[user]
name = "  Test #; Person  "
email = test@example.invalid
[core]
fileMode
symlinks = false
excludesFile = ~/exclude
[init]
defaultBranch = work
[commit]
cleanup = scissors
[status]
renames = copies
showUntrackedFiles = all
[index]
version = 2
[remote "Origin.With.Dots"]
url = "https://host/#;x"
[Remote.OLD]
url = old
[test]
empty =
joined = one\\
  two
escaped = "a\\nb\\tc\\b\\"\\\\z"
'''
    (gd / 'config').write_bytes(config)
    for key, value in [
        ('user.name', b'  Test #; Person  '), ('USER.EMAIL', b'test@example.invalid'),
        ('core.filemode', b''), ('core.symlinks', b'false'),
        ('core.excludesFile', b'~/exclude'), ('init.defaultBranch', b'work'),
        ('commit.cleanup', b'scissors'), ('status.renames', b'copies'),
        ('status.showUntrackedFiles', b'all'), ('index.version', b'2'),
        ('remote.Origin.With.Dots.url', b'https://host/#;x'),
        ('REMOTE.old.URL', b'old'), ('test.empty', b''),
        ('test.joined', b'one  two'), ('test.escaped', b'a\nb\tc\x08"\\z'),
    ]:
        get(key, value)
    get('remote.origin.With.Dots.url')
    # Duplicate implicit vs explicit assignments keep raw --get semantics.
    (gd / 'config').write_bytes(base_config + b'[core]\nfilemode=true\nfilemode\n')
    get('core.filemode', b'')
    (gd / 'config').write_bytes(base_config + b'[core]\nfilemode\nfilemode=true\n')
    get('core.filemode', b'true')

    for text in [b'[include]\npath=never-opened\n',
                 b'[includeIf "gitdir:nonmatching/"]\npath=never-opened\n']:
        (gd / 'config').write_bytes(base_config + text)
        run(['config', '--get', 'test.priority'], expected=2,
            error=b'config includeIf' if b'includeIf' in text else b'config include')
    (gd / 'config').write_bytes(base_config)
    for key in ['include.path', 'includeIf.gitdir:never/.path']:
        run(['config', '--get', 'test.priority'], expected=2, error=b'config include', changes={
            'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': key, 'GIT_CONFIG_VALUE_0': 'never'})

    for text, line in [
        (b'[bad', 1), (b'[a]\nk=\\q\n', 2),
        (b'[a]\nk="unterminated\n', 2), (b'[a]\nk=\x00\n', 2),
        (b'key=value\n', 1),
        # Continuation advances the physical line reported by the parser.
        (b'[a]\nk=one\\\n  \\q\n', 3),
    ]:
        (gd / 'config').write_bytes(text)
        result = run(['config', '--get', 'test.priority'], expected=128,
                     error=b'bad config line')
        assert result.stderr == f'fatal: bad config line {line} in file .git/config\n'.encode()
    (gd / 'config').write_bytes(b'[a]\nk=\xff\n')
    run(['config', '--get', 'test.priority'], expected=128, error=b'invalid')
    # Diagnostics work at the other existing plumbing process edges too.
    (gd / 'config').write_bytes(b'[core]\nrepositoryformatversion=0\n[a]\nk=\\q\n')
    result = run(['write-tree'], expected=128, error=b'bad config line')
    assert result.stderr == b'fatal: bad config line 4 in file .git/config\n'
    (gd / 'config').write_bytes(base_config)
    for variable, changes in [
        ('key GIT_CONFIG_KEY_0', {'GIT_CONFIG_COUNT': '1'}),
        ('value GIT_CONFIG_VALUE_0', {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'test.priority'}),
    ]:
        result = run(['config', '--get', 'test.priority'], expected=128,
                     error=b'unable to parse command-line config', changes=changes)
        assert result.stderr == (f'error: missing config {variable}\n'
                                 'fatal: unable to parse command-line config\n').encode()
    for changes in [
        {'GIT_CONFIG_COUNT': '-1'}, {'GIT_CONFIG_COUNT': 'words'},
        {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': '', 'GIT_CONFIG_VALUE_0': 'x'},
        {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'bad', 'GIT_CONFIG_VALUE_0': 'x'},
        {'GIT_CONFIG_NOSYSTEM': 'not-a-boolean'},
    ]:
        run(['config', '--get', 'test.priority'], expected=128, error=b'invalid', changes=changes)
    run(['config', '--get', 'test.priority'], expected=128, error=b'limit',
        changes={'GIT_CONFIG_COUNT': '999999999999999999999999999999'})
    result = run(['config', '--get', 'bad'], expected=1, error=b'key does not contain a section')
    assert result.stderr == b'error: key does not contain a section: bad\n'
    for key in ['.key', 'user.', 'user.1key', 'user.bad_key']:
        run(['config', '--get', key], expected=1, error=b'invalid config key')
    for command in [['config'], ['config', 'user.name', 'write'], ['config', '--set', 'user.name', 'write'],
                    ['config', '--get'], ['config', '--get', 'test.priority', 'extra']]:
        run(command, expected=2, error=b'only --get')

    # Existing M1 init consumes the same scalar API; command scope wins globally.
    created = root / 'created'
    e = dict(env, GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='init.defaultBranch',
             GIT_CONFIG_VALUE_0='from-env')
    result = subprocess.run([str(DEN), 'init', '-q', str(created)], cwd=outside,
                            env=e, capture_output=True, timeout=20)
    assert (result.returncode, result.stdout, result.stderr) == (0, b'', b''), result
    assert (created / '.git/HEAD').read_bytes() == b'ref: refs/heads/from-env\n'
    print(f'PASS config {args.tier}: {len(rows)} read-only CLI rows and init scalar-API integration')
