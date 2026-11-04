#!/usr/bin/env python3
"""Fixture-owner compatibility/refusals; synthetic homes stay inside this repo."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import runpy
import shlex
import tempfile
from unittest import mock

R = Path(__file__).resolve().parent.parent
(R / 'target').mkdir(exist_ok=True)
module = runpy.run_path(str(R / 'tools/ssh-peer.py'))
install = module['install']
failures = []

def check(name, operation):
    try:
        operation()
    except Exception as error:
        failures.append(name)
        print('FAIL', name, type(error).__name__, str(error), flush=True)
    else:
        print('PASS', name, flush=True)

def refused(root, git, owner, fragment):
    try:
        install(root, git, '4-7', lane=owner)
    except ValueError as error:
        assert fragment in str(error), str(error)
    else:
        raise AssertionError('owner was accepted')

with tempfile.TemporaryDirectory(prefix='ssh-peer-scope-', dir=R / 'target') as folder:
    home = Path(folder) / 'home'
    git = home / 'pin/bin/git'
    git.parent.mkdir(parents=True)
    git.write_bytes(b'synthetic unit input, never executed\n')
    for service in ['git-upload-pack', 'git-receive-pack']:
        (git.parent / service).write_bytes(b'synthetic service, never executed\n')
    install.__globals__['PIN'] = hashlib.sha256(git.read_bytes()).hexdigest()
    old = home / 'lanes/vc16/fixture'
    owned = home / 'lanes/vc17/fixture'
    with mock.patch.object(Path, 'home', return_value=home), contextlib.redirect_stdout(io.StringIO()) as captured:
        def legacy():
            install(old, git, '4-7')
            assert (old / 'peer.json').read_text() == json.dumps(dict(git=str(git), slot='4-7')) + '\n'
            assert (old / 'control.py').read_bytes() == (R / 'tools/ssh-peer.py').read_bytes()
            fixed = dict(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=str(old / 'gitconfig'),
                         GIT_EXEC_PATH=str(git.parent.parent / 'libexec/git-core'),
                         GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
                         GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid',
                         GIT_AUTHOR_DATE='1700000000 +0000', GIT_COMMITTER_DATE='1700000000 +0000',
                         HOME=str(old / 'home'), TMPDIR=str(old / 'tmp'), LC_ALL='C', TZ='UTC',
                         PATH=str(git.parent) + ':/usr/bin:/bin')
            for name, service, v2 in [('upload', 'git-upload-pack', True), ('receive', 'git-receive-pack', True), ('upload-v0', 'git-upload-pack', False)]:
                assignments = dict(fixed)
                if v2:
                    assignments['GIT_PROTOCOL'] = 'version=2'
                expected = '#!/usr/bin/env bash\nset -eu\n' + ('export GIT_PROTOCOL=version=2\n' if v2 else 'unset GIT_PROTOCOL\n')
                expected += 'exec env -i ' + ' '.join(shlex.quote(k + '=' + v) for k, v in assignments.items())
                expected += ' taskset -c 4-7 ' + shlex.quote(str(git.parent / service)) + ' "$@"\n'
                assert (old / 'bin' / name).read_text() == expected
        check('ssh-peer-vc16-default-bytes', legacy)

        def explicit_legacy():
            before = {str(p.relative_to(old)): p.read_bytes() for p in old.rglob('*') if p.is_file()}
            install(old, git, '4-7', lane='vc16')
            after = {str(p.relative_to(old)): p.read_bytes() for p in old.rglob('*') if p.is_file()}
            assert before == after
        check('ssh-peer-vc16-explicit-bytes', explicit_legacy)

        def current():
            install(owned, git, '4-7', lane='vc17')
            assert json.loads((owned / 'peer.json').read_text())['lane'] == 'vc17'
            assert str(owned) in (owned / 'bin/upload').read_text()
            assert str(home / 'lanes/vc16') not in (owned / 'bin/upload').read_text()
        check('ssh-peer-owned-lane', current)
        check('ssh-peer-owner-mismatch', lambda: refused(old, git, 'vc17', 'owner mismatch'))
        check('ssh-peer-owner-escape', lambda: refused(owned, git, '../vc17', 'owner escape'))
        escape = home / 'lanes/vc17/escape'
        escape.parent.mkdir(parents=True, exist_ok=True)
        (home / 'outside').mkdir()
        escape.symlink_to(home / 'outside', target_is_directory=True)
        check('ssh-peer-symlink-escape', lambda: refused(escape, git, 'vc17', 'owner escape'))
    print(captured.getvalue(), end='', flush=True)
assert not Path(folder).exists(), 'owned fixture cleanup failed'
print('PASS ssh-peer-owned-fixture-cleanup', flush=True)
raise SystemExit(bool(failures))
