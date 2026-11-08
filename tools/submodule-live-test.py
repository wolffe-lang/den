#!/usr/bin/env python3
"""vc25 live rows: public wolffe-lang superprojects over https, den against
the pinned Git at the same time, read-only, never credentials.

live-wolf-web: den and the pinned Git each clone wolf-web with
--recurse-submodules (submodules two deep, names unlike their paths); the
process bytes, and for the superproject and every repository under
.git/modules: refs, HEAD, every reachable object, the config file's bytes and
the worktree, are compared. The guard holds what the clones take: if any
branch or tag of the superproject or a submodule's remote moves while the row
runs, it is retried once, then fails by name.

live-<repo>-gitlinks, for wolf-interp, wolf-std and wolf-lsp: one clone by the
pinned Git, then submodule status, ls-tree, log, show and diff of the commit
that last moved the release-pinned gitlink, run by both tools in that clone
and compared byte for byte (the submodule's commits are not present: its
repository is never cloned).

live-wolf-std-ssh: through url.git@github.com:.insteadOf=https://github.com/,
only where an ssh key for github.com answers; a named SKIP otherwise.

--timed N: the measured row (not a gate): N interleaved recursive clones of
wolf-web by each tool on this machine, wall time and the child's CPU from
wait4, written to target/runs/submodule-live-timed.json.

Every row SKIPs by name when github.com:443 is unreachable or when no
distribution root bundle exists. Run through tools/env.
Sources: git-clone(1), git-submodule(1), git-ls-remote(1) of Git v2.56.0.
No Git source.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import statistics
import subprocess
import sys
import time

GIT_SHA256 = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
WEB = 'https://github.com/wolffe-lang/wolf-web.git'
PINNED = ('wolf-interp', 'wolf-std', 'wolf-lsp')
CLONE_SECONDS = 1800

p = argparse.ArgumentParser()
p.add_argument('--tier', choices=('native', 'release'), default='native')
p.add_argument('--timed', type=int, default=0)
p.add_argument('--field', action='store_true', help='a Git other than the pinned one, for development only')
p.add_argument('--url', default='', help='--timed only: another public superproject, measured locally')
p.add_argument('--ssh-to-https', action='store_true',
               help='--timed only: url.https://github.com/.insteadOf=git@github.com: for scp-like submodule URLs')
a = p.parse_args()
R = Path(__file__).resolve().parent.parent
live = runpy.run_path(str(R / 'tools/http-live-test.py'), run_name='http_live')
git = str(Path(os.environ['DEN_GIT']).resolve())
if not a.field:
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == GIT_SHA256, 'pinned Git digest'
den = R / 'target' / a.tier / 'den'
if not den.is_file():
    raise SystemExit('FAIL submodule-live-input: build target/' + a.tier + '/den first')
names = ['live-wolf-web'] + ['live-%s-gitlinks' % r for r in PINNED] + ['live-wolf-std-ssh']
if a.timed:
    names = ['live-timed-wolf-web']
pem = Path(os.environ.get('DEN_LIVE_ROOTS_PEM', '/etc/ssl/certs/ca-certificates.crt'))
if not pem.is_file():
    for name in names:
        print('SKIP %s reason=no distribution root bundle' % name, flush=True)
    raise SystemExit(0)
unreachable = live['reachable']('github.com', 443)
if unreachable:
    for name in names:
        print('SKIP %s reason=no network (github.com:443 %s)' % (name, unreachable), flush=True)
    raise SystemExit(0)
out = R / 'target/runs' / ('submodule-live-' + a.tier)
if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)
der, count = live['pem_roots'](pem)
(out / 'roots.der').write_bytes(der)
env = {k: v for k, v in os.environ.items() if not k.startswith(('DEN_HTTP', 'GIT_ASKPASS', 'SSH_ASKPASS'))}
env.update(GIT_TERMINAL_PROMPT='0', GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='protocol.version',
           GIT_CONFIG_VALUE_0='2', GIT_SSL_CAINFO=str(pem), DEN_TLS_ROOTS=str(out / 'roots.der'))
failed = []


def run(argv, cwd, timeout=CLONE_SECONDS, extra=None):
    started = time.monotonic()
    child = subprocess.Popen([str(x) for x in argv], cwd=str(cwd), env={**env, **(extra or {})},
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = child.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        child.kill()  # this row's own child only
        stdout, stderr = child.communicate()
    return dict(exit=child.returncode, stdout=stdout.decode('utf-8', 'backslashreplace'),
                stderr=stderr.decode('utf-8', 'backslashreplace'), wall=round(time.monotonic() - started, 2))


def git_out(cwd, *argv):
    q = subprocess.run([git, *argv], cwd=str(cwd), env=env, capture_output=True, timeout=600)
    assert q.returncode == 0, (argv, q.stderr[-300:])
    return q.stdout


def cloned_refs(url):
    q = run([git, 'ls-remote', url], out, 120)
    if q['exit']:
        return None
    return live['cloned'](q['stdout'].encode().hex())


def gitdirs(top):
    found = [top / '.git']
    modules = top / '.git/modules'
    for config in sorted(modules.rglob('config')) if modules.exists() else []:
        if (config.parent / 'HEAD').is_file():
            found.append(config.parent)
    return found


def repo_state(gitdir):
    refs = git_out(gitdir, '--git-dir=' + str(gitdir), 'for-each-ref', '--format=%(refname) %(objectname) %(symref)')
    ids = sorted({line.split()[0] for line in git_out(gitdir, '--git-dir=' + str(gitdir), 'rev-list', '--objects',
                                                       '--all').splitlines()})
    digest = hashlib.sha256()
    if ids:
        q = subprocess.run([git, '--git-dir=' + str(gitdir), 'cat-file', '--batch'], env=env, capture_output=True,
                           input=b''.join(i + b'\n' for i in ids), timeout=600)
        digest.update(q.stdout)
    return dict(refs=refs.decode(), head=(gitdir / 'HEAD').read_bytes().decode(errors='replace'),
                objects=len(ids), objects_sha256=digest.hexdigest(),
                config=(gitdir / 'config').read_bytes().decode(errors='replace'))


def tree_state(top):
    files = {}
    for path in sorted(top.rglob('*')):
        rel = path.relative_to(top).as_posix()
        if rel == '.git' or rel.startswith('.git/') or '/.git/' in rel:
            continue
        if path.is_symlink():
            files[rel] = 'link:' + os.readlink(path)
        elif path.is_file():
            files[rel] = '%o:%s' % (path.stat().st_mode & 0o777, hashlib.sha256(path.read_bytes()).hexdigest())
    state = dict(worktree=files)
    for gitdir in gitdirs(top):
        state[gitdir.relative_to(top).as_posix()] = repo_state(gitdir)
    return state


def verdict(name, problems, detail=None):
    (out / (name + '.json')).write_text(json.dumps(dict(problems=problems, **(detail or {})), indent=1) + '\n')
    print(('PASS ' if not problems else 'FAIL ') + name + ('' if not problems else ' ' + '; '.join(problems)),
          flush=True)
    if problems:
        failed.append(name)


def remotes_of(top):
    """The superproject's URL and every submodule's, as the clone took them."""
    urls = [WEB]
    for gitdir in gitdirs(top)[1:]:
        q = subprocess.run([git, '--git-dir=' + str(gitdir), 'config', 'remote.origin.url'], env=env,
                           capture_output=True, timeout=60)
        if q.returncode == 0:
            urls.append(q.stdout.decode().strip())
    return urls


def web_row():
    name = 'live-wolf-web'
    problems = []
    for attempt in range(2):
        problems = []
        work = out / ('web-%d' % attempt)
        work.mkdir()
        before = cloned_refs(WEB)
        oracle = run([git, 'clone', '-q', '--recurse-submodules', WEB, 'git'], work)
        if oracle['exit']:
            problems.append('pinned Git could not clone wolf-web: ' + oracle['stderr'][-300:])
            break
        urls = remotes_of(work / 'git')
        middle = [cloned_refs(url) for url in urls[1:]]
        candidate = run([den, 'clone', '-q', '--recurse-submodules', WEB, 'den'], work)
        after = cloned_refs(WEB)
        # What both clones took, held from before Git's to after den's (the
        # submodules' remotes from Git's clone on).
        moved = before is None or after is None or before != after or middle != [cloned_refs(u) for u in urls[1:]]
        for field in ('exit', 'stdout', 'stderr'):
            if oracle[field] != candidate[field]:
                problems.append('process %s differs: den exit %d stderr %r' % (field, candidate['exit'],
                                                                                 candidate['stderr'][-400:]))
        if not problems:
            theirs, ours = tree_state(work / 'git'), tree_state(work / 'den')
            differ = sorted(k for k in theirs.keys() | ours.keys() if theirs.get(k) != ours.get(k))
            if differ:
                fields = []
                for k in differ:
                    if k == 'worktree':
                        fields.append('worktree')
                    else:
                        t, o = theirs.get(k) or {}, ours.get(k) or {}
                        fields.append(k + ':' + ','.join(f for f in t if t.get(f) != o.get(f)))
                problems.append('state differs: ' + '; '.join(fields))
        detail = dict(urls=urls, git_wall=oracle['wall'], den_wall=candidate['wall'])
        if moved and problems:
            print('LIVE %s refs moved during attempt %d; retried' % (name, attempt), flush=True)
            shutil.rmtree(work)
            continue
        verdict(name, problems, detail)
        return
    verdict(name, problems + ['refs moved during the row'])


def pinned_rows():
    for repo in PINNED:
        name = 'live-%s-gitlinks' % repo
        url = 'https://github.com/wolffe-lang/%s.git' % repo
        work = out / repo
        work.mkdir()
        q = run([git, 'clone', '-q', url, 'c'], work)
        if q['exit']:
            verdict(name, ['pinned Git could not clone %s' % repo])
            continue
        c = work / 'c'
        moved = git_out(c, 'log', '-1', '--format=%H', '--', 'upstream').decode().strip()
        problems = []
        commands = [['submodule', 'status'], ['ls-tree', 'HEAD', 'upstream'], ['ls-files', '-s', 'upstream'],
                    ['log', '--oneline', '-3', '--', 'upstream'], ['show', '--submodule=log', moved, '--', 'upstream'],
                    ['show', '--stat', moved], ['diff', moved + '~1', moved, '--', 'upstream'],
                    ['diff', '--submodule=log', moved + '~1', moved], ['status', '--porcelain']]
        for argv in commands:
            oracle = run([git, *argv], c, 300)
            candidate = run([den, *argv], c, 300)
            for field in ('exit', 'stdout', 'stderr'):
                if oracle[field] != candidate[field]:
                    problems.append('%s: %s differs (den exit %d, %r)' % (' '.join(argv[:2]), field, candidate['exit'],
                                                                          candidate[field][-200:]))
        verdict(name, problems, dict(moved=moved, commands=commands))


def ssh_row():
    name = 'live-wolf-std-ssh'
    q = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-T', 'git@github.com'],
                       env=env, capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    if b'successfully authenticated' not in q.stderr:
        print('SKIP %s reason=no ssh key for github.com answers' % name, flush=True)
        return
    rewrite = dict(GIT_CONFIG_COUNT='2', GIT_CONFIG_KEY_1='url.git@github.com:.insteadOf',
                   GIT_CONFIG_VALUE_1='https://github.com/')
    work = out / 'ssh'
    work.mkdir()
    oracle = run([git, 'clone', '-q', 'https://github.com/wolffe-lang/wolf-std.git', 'git'], work, extra=rewrite)
    candidate = run([den, 'clone', '-q', 'https://github.com/wolffe-lang/wolf-std.git', 'den'], work, extra=rewrite)
    problems = [f + ' differs' for f in ('exit', 'stdout', 'stderr') if oracle[f] != candidate[f]]
    if not problems and tree_state(work / 'git') != tree_state(work / 'den'):
        problems.append('state differs')
    verdict(name, problems)


LAUNCH = r'''
import os, sys, json, time
t = time.monotonic()
pid = os.fork()
if pid == 0:
    fd = os.open(os.devnull, os.O_RDWR); os.dup2(fd, 0); os.dup2(fd, 1); os.dup2(fd, 2)
    os.execvp(sys.argv[1], sys.argv[1:])
_, status, ru = os.wait4(pid, 0)
print(json.dumps(dict(exit=os.waitstatus_to_exitcode(status), wall=round(time.monotonic() - t, 2),
                      cpu=round(ru.ru_utime + ru.ru_stime, 2), maxrss_kib=ru.ru_maxrss)))
'''


def timed():
    """Interleaved recursive clones of wolf-web (or --url); the ratio and its
    spread are recorded, not gated."""
    url = a.url or WEB
    if a.ssh_to_https:
        env.update(GIT_CONFIG_COUNT='2', GIT_CONFIG_KEY_1='url.https://github.com/.insteadOf',
                   GIT_CONFIG_VALUE_1='git@github.com:')
    runs = []
    for i in range(a.timed):
        for tool, exe in (('git', git), ('den', str(den))):
            work = out / ('timed-%s-%d' % (tool, i))
            work.mkdir()
            q = subprocess.run([sys.executable, '-I', '-S', '-c', LAUNCH, exe, 'clone', '-q', '--recurse-submodules',
                                url, 'c'], cwd=str(work), env=env, capture_output=True, timeout=7200)
            row = json.loads(q.stdout.decode().strip().splitlines()[-1])
            row.update(tool=tool, run=i)
            runs.append(row)
            print('LIVE-TIMED ' + json.dumps(row, sort_keys=True), flush=True)
            shutil.rmtree(work)
    ok = all(r['exit'] == 0 for r in runs)
    summary = dict(runs=runs)
    if ok:
        for key in ('wall', 'cpu'):
            g = [r[key] for r in runs if r['tool'] == 'git']
            d = [r[key] for r in runs if r['tool'] == 'den']
            ratios = sorted(x / y for x, y in zip(d, g) if y)
            summary[key] = dict(git_median=statistics.median(g), den_median=statistics.median(d),
                                ratio_median=round(statistics.median(d) / statistics.median(g), 2),
                                ratio_min=round(ratios[0], 2), ratio_max=round(ratios[-1], 2))
    summary['url_is_wolf_web'] = url == WEB
    (R / 'target/runs/submodule-live-timed.json').write_text(json.dumps(summary, indent=1) + '\n')
    print('LIVE-TIMED-SUMMARY ' + json.dumps({k: v for k, v in summary.items() if k != 'runs'}, sort_keys=True),
          flush=True)
    verdict('live-timed-wolf-web', [] if ok else ['a clone failed'])


if a.timed:
    timed()
else:
    web_row()
    pinned_rows()
    ssh_row()
if failed:
    raise SystemExit('FAIL submodule-live: ' + ', '.join(failed))
print('submodule-live: %s %d rows' % (a.tier, len(names)), flush=True)
