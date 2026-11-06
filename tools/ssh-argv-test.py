#!/usr/bin/env python3
"""den's ssh remote command against the pinned Git's, through a recording ssh.

A fake `ssh` records its argv (NUL-separated) and exits 128; no network and no
peer. For a plain program word (letters, digits and ._/+-), den's remote
command, the words after the host joined as ssh joins them, must equal the
pinned Git's, measured live with the same recorder through GIT_SSH. An
override that is not plain is a literal executable and stays quoted. For every
case, `sh -c` gives the far side the same argv for den's command as for the
fully quoted form, so a POSIX shell sees no difference. Black box only.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

den = str(Path(sys.argv[1]).resolve())
out = Path(sys.argv[2]).resolve()
if out.exists():
    raise SystemExit('FAIL ssh-argv-fresh-output: select a fresh output directory')
(out / 'bin').mkdir(parents=True)
(out / 'far').mkdir()
(out / 'opt' / 'my git').mkdir(parents=True)
git = shutil.which('git')
assert git and os.path.realpath(git) == os.path.realpath(os.environ['DEN_GIT']), 'pinned Git first on PATH'
fake = out / 'bin' / 'ssh'
fake.write_text('#!/bin/sh\nprintf \'%s\\0\' "$@" > "$FAKE_SSH_LOG"\nexit 128\n')
fake.chmod(0o755)
# Far-side recorders: each service program records the argv a shell gave it.
recorder = '#!/bin/sh\nprintf \'%s\\0\' "$0" "$@" > "$FAR_LOG"\n'
plain_upload = out / 'opt' / 'git-upload-pack'
spaced_upload = out / 'opt' / 'my git' / 'git-upload-pack'
plain_receive = out / 'opt' / 'git-receive-pack'
for path in [out / 'far' / 'git-upload-pack', out / 'far' / 'git-receive-pack', plain_upload, spaced_upload, plain_receive]:
    path.write_text(recorder)
    path.chmod(0o755)
URL = "ssh://example.invalid/srv/a b'c.git"
base = {key: value for key, value in os.environ.items()
        if key not in ('DEN_UPLOAD_PACK', 'DEN_RECEIVE_PACK', 'GIT_SSH', 'GIT_SSH_COMMAND', 'GIT_SSH_VARIANT')}
captures = []


def words(argv, tool):
    if tool == 'den':
        assert '--' in argv, 'den passes -- before the host'
        argv = argv[argv.index('--') + 1:]
    else:
        argv = [a for a in argv if a not in ('-o', 'SendEnv=GIT_PROTOCOL')]
    assert argv and argv[0] == 'example.invalid', argv
    return argv[1:]


def record(tool, name, argv, cwd):
    log = out / ('%s-%s.argv' % (tool, name))
    env = {**base, 'FAKE_SSH_LOG': str(log)}
    if tool == 'den':
        env['PATH'] = str(out / 'bin') + os.pathsep + base['PATH']
    else:
        env.update(GIT_SSH=str(fake), GIT_SSH_VARIANT='ssh')
    result = subprocess.run(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
    recorded = [a.decode() for a in log.read_bytes().split(b'\0')[:-1]] if log.exists() else []
    captures.append(dict(tool=tool, case=name, argv=argv, exit=result.returncode, ssh_argv=recorded,
                         stdout=result.stdout.hex(), stderr=result.stderr.hex()))
    (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')
    if not recorded:
        raise AssertionError('%s %s never ran ssh: %r' % (tool, name, result.stderr[:300]))
    return ' '.join(words(recorded, tool))


def quote(text):
    return "'" + text.replace("'", "'\\''") + "'"


def far_side(command):
    log = out / 'far.argv'
    if log.exists():
        log.unlink()
    env = {**base, 'FAR_LOG': str(log), 'PATH': str(out / 'far') + os.pathsep + '/usr/bin:/bin'}
    subprocess.run(['/bin/sh', '-c', command], env=env, check=True, timeout=30)
    return [a.decode() for a in log.read_bytes().split(b'\0')[:-1]]


repo = out / 'repo'
subprocess.run([git, 'init', '-q', '-b', 'main', str(repo)], env=base, check=True)
subprocess.run([git, '-C', str(repo), 'commit', '-q', '--allow-empty', '-m', 'ssh argv row'], env=base, check=True)
cases = [
    # name, den argv, git argv, cwd, program, expected to equal Git's command
    ('clone-plain', [den, 'clone', '-q', URL, str(out / 'den-c1')],
     [git, '-c', 'protocol.version=2', 'clone', '-q', URL, str(out / 'git-c1')], out, 'git-upload-pack', True),
    ('clone-override-plain', [den, 'clone', '-q', '--upload-pack=' + str(plain_upload), URL, str(out / 'den-c2')],
     [git, '-c', 'protocol.version=2', 'clone', '-q', '--upload-pack=' + str(plain_upload), URL, str(out / 'git-c2')],
     out, str(plain_upload), True),
    ('clone-override-space', [den, 'clone', '-q', '--upload-pack=' + str(spaced_upload), URL, str(out / 'den-c3')],
     [git, '-c', 'protocol.version=2', 'clone', '-q', '--upload-pack=' + str(spaced_upload), URL, str(out / 'git-c3')],
     out, str(spaced_upload), False),
    ('push-plain', [den, 'push', '-q', URL, 'refs/heads/main:refs/heads/main'],
     [git, 'push', '-q', URL, 'refs/heads/main:refs/heads/main'], repo, 'git-receive-pack', True),
    ('push-override-plain', [den, 'push', '-q', '--receive-pack=' + str(plain_receive), URL, 'refs/heads/main:refs/heads/main'],
     [git, 'push', '-q', '--receive-pack=' + str(plain_receive), URL, 'refs/heads/main:refs/heads/main'],
     repo, str(plain_receive), True),
]
failed = []
for name, den_argv, git_argv, cwd, program, same in cases:
    problems = []
    try:
        ours = record('den', name, den_argv, cwd)
        theirs = record('git', name, git_argv, cwd)
        quoted = quote(program) + ' ' + quote('/srv/a b\'c.git')
        if same and ours != theirs:
            problems.append('den %r, git %r' % (ours, theirs))
        if not same and ours != quoted:
            problems.append('den %r, want the quoted literal %r (git sends %r)' % (ours, quoted, theirs))
        if far_side(ours) != far_side(quoted):
            problems.append('a shell gives the far side a different argv')
        if far_side(ours)[1:] != ['/srv/a b\'c.git']:
            problems.append('far side argv %r' % far_side(ours))
        if name.startswith('clone') and Path(den_argv[-1]).exists():
            problems.append('partial clone left')
    except (AssertionError, OSError, subprocess.SubprocessError) as exc:
        problems.append(type(exc).__name__ + ': ' + str(exc))
    print(('PASS ' if not problems else 'FAIL ') + 'ssh-cli-' + name + ('' if not problems else ': ' + '; '.join(problems)),
          flush=True)
    if problems:
        failed.append(name)
if failed:
    raise SystemExit('failed ssh argv rows: ' + ', '.join(failed))
print('ssh-argv: %d cases against the pinned Git and a POSIX shell; zero skips' % len(cases), flush=True)
