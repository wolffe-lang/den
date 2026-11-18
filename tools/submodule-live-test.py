#!/usr/bin/env python3
"""vc25 live rows: public wolffe-lang superprojects over https, den against
the pinned Git at the same time, read-only, never credentials.

live-wolf-web: den and the pinned Git each clone wolf-web with
--recurse-submodules (submodules two deep, names unlike their paths); the
process bytes, and for the superproject and every repository under
.git/modules: refs, HEAD, every reachable object, the config file's bytes and
the worktree, are compared. Others push to these repositories at any time,
so the row compares what held still (tools/http-live-test.py's judge): a ref
held in a repository when the refs Git's clone took, an `ls-remote --symref`
of its remote right after Git's clone and another after den's all agree
(the superproject's also before Git's). A move of the superproject's HEAD or
its branch reruns the row once; any other moved ref is left out of the
comparison and named on a `NARROWED live-wolf-web excluded=<module>:<ref>`
line and in the row's report. A submodule's checkout is its gitlink, so a
move of a submodule's default branch is narrowed, never rerun.

live-<repo>-gitlinks, for wolf-interp, wolf-std and wolf-lsp: one clone by the
pinned Git, then submodule status, ls-tree, ls-files, cat-file and rev-parse
around the commit that last moved the release-pinned gitlink, run by
both tools in that clone and compared byte for byte (its repository is never
cloned).

live-wolf-std-ssh: through url.git@github.com:.insteadOf=https://github.com/,
only with DEN_LIVE_SSH=1 and where an ssh key for github.com answers; a named
SKIP otherwise.

--self-test: live-gitlinks-clone-problem, no network: the pinned Git clones a
repository that does not exist, and the problem text a gitlinks row would
print must carry the last line Git wrote, so a red live row names its cause.

--timed N: the measured row (not a gate): N interleaved recursive clones of
wolf-web by each tool on this machine, wall time and the child's CPU from
wait4, written to target/runs/submodule-live-timed.json.

--web-url URL and --between-clones CMD are for tests only: they aim
live-wolf-web at another superproject and run CMD (a shell command) after the
pinned Git's clone and before the row's first listing of the submodules'
remotes. tools/submodule-live-moved-test.py uses them to move a submodule
remote's refs at that point; without them the row is unchanged.

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
import tempfile
import time

GIT_SHA256 = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
WEB = 'https://github.com/wolffe-lang/wolf-web.git'
PINNED = ('wolf-interp', 'wolf-std', 'wolf-lsp')
CLONE_SECONDS = 1800

p = argparse.ArgumentParser()
p.add_argument('--tier', choices=('native', 'release'), default='native')
p.add_argument('--timed', type=int, default=0)
p.add_argument('--field', action='store_true', help='a Git other than the pinned one, for development only')
p.add_argument('--only', default='', help='run the rows whose names match this pattern')
p.add_argument('--self-test', action='store_true', help='the clone-problem row alone, with no network')
p.add_argument('--url', default='', help='--timed only: another public superproject, measured locally')
p.add_argument('--web-url', default='',
               help='test only (tools/submodule-live-moved-test.py): live-wolf-web against another superproject')
p.add_argument('--between-clones', default='',
               help='test only (tools/submodule-live-moved-test.py): a shell command live-wolf-web runs after the '
                    'pinned Git\'s clone and before its first listing of the submodules\' remotes; inert unless given')
p.add_argument('--ssh-to-https', action='store_true',
               help='--timed only: url.https://github.com/.insteadOf=git@github.com: for scp-like submodule URLs')
a = p.parse_args()
R = Path(__file__).resolve().parent.parent
live = runpy.run_path(str(R / 'tools/http-live-test.py'), run_name='http_live')
git = str(Path(os.environ['DEN_GIT']).resolve())
if not a.field:
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == GIT_SHA256, 'pinned Git digest'


def clone_problem(repo, capture):
    """The problem a gitlinks row prints when the pinned Git's clone fails:
    Git's exit status, the clone's wall time and the end of what Git wrote to
    stderr, its lines joined."""
    said = ' | '.join(line.strip() for line in capture['stderr'].splitlines() if line.strip())
    return 'pinned Git could not clone %s (exit %d after %.2f s): %s' % (
        repo, capture['exit'], capture['wall'], said[-300:] or 'nothing on stderr')


if a.self_test:
    with tempfile.TemporaryDirectory() as scratch:
        missing = Path(scratch) / 'missing.git'
        started = time.monotonic()
        q = subprocess.run([git, 'clone', '-q', missing.as_uri(), 'c'], cwd=scratch, capture_output=True,
                           env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}, stdin=subprocess.DEVNULL, timeout=120)
        capture = dict(exit=q.returncode, stderr=q.stderr.decode('utf-8', 'backslashreplace'),
                       wall=round(time.monotonic() - started, 2))
    problem = clone_problem('missing', capture)
    said = [line.strip() for line in capture['stderr'].splitlines() if line.strip()]
    ok = capture['exit'] != 0 and bool(said) and said[-1] in problem
    print(('PASS ' if ok else 'FAIL ') + 'live-gitlinks-clone-problem' +
          ('' if ok else ' %r does not carry Git\'s last line %r (exit %d)' % (problem, said[-1:], capture['exit'])),
          flush=True)
    raise SystemExit(0 if ok else 1)
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
# The clones themselves stay out of target/runs, which CI uploads as evidence:
# a cloned repository can carry test keys (wolf-std vendors TLS vectors), and
# no key goes into evidence (tools/evidence-modes.py). Only the reports do.
clones = R / 'target/live' / ('submodule-live-' + a.tier)
if clones.exists():
    shutil.rmtree(clones)
clones.mkdir(parents=True)
der, count = live['pem_roots'](pem)
(out / 'roots.der').write_bytes(der)
env = {k: v for k, v in os.environ.items() if not k.startswith(('DEN_HTTP', 'GIT_ASKPASS', 'SSH_ASKPASS'))}
env.update(GIT_TERMINAL_PROMPT='0', GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='protocol.version',
           GIT_CONFIG_VALUE_0='2', GIT_SSL_CAINFO=str(pem), DEN_TLS_ROOTS=str(out / 'roots.der'))
failed = []


def run(argv, cwd, timeout=CLONE_SECONDS, extra=None, target=None, row=None, tool=None):
    """One child, its output in files and reaped by tools/http-live-test.py's
    reap (no pipe can stall it). With a target, a network clone: watched
    for progress and run once more after a stall, as the HTTP live rows do."""
    def attempt(suffix):
        started = time.monotonic()
        with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
            child = subprocess.Popen([str(x) for x in argv], cwd=str(cwd), env={**env, **(extra or {})},
                                     stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
            status, _, timed_out, stalled, quiet = live['reap'](child, timeout, target)
            stdout.seek(0)
            stderr.seek(0)
            return dict(exit=os.waitstatus_to_exitcode(status), stdout=stdout.read().decode('utf-8', 'backslashreplace'),
                        stderr=stderr.read().decode('utf-8', 'backslashreplace'),
                        wall=round(time.monotonic() - started, 2), timed_out=timed_out, stalled=stalled, quiet=quiet)

    if target is None:
        return attempt('')
    return live['watched'](attempt, target, timeout, row, tool)


def stalled_twice(*clones):
    """The problems of clones (tool, capture) that stalled twice."""
    return [live['stall_problem'](tool, live['stall_bound'](CLONE_SECONDS)) for tool, capture in clones
            if capture['stalls'] == 2]


def git_out(cwd, *argv):
    q = subprocess.run([git, *argv], cwd=str(cwd), env=env, capture_output=True, timeout=600)
    assert q.returncode == 0, (argv, q.stderr[-300:])
    return q.stdout


def listing(url):
    """The remote's `ls-remote --symref` (hex stdout), or None."""
    q = run([git, 'ls-remote', '--symref', url], out, 120)
    return None if q['exit'] else q['stdout'].encode().hex()


def took_refs(gitdir):
    """The refs a clone took, by the names its remote gives them: a remote-
    tracking branch as refs/heads/<name>, a tag as it is."""
    took = {}
    for line in git_out(gitdir, '--git-dir=' + str(gitdir), 'for-each-ref',
                        '--format=%(refname) %(objectname)').decode().splitlines():
        ref, oid = line.split(' ', 1)
        if ref.startswith('refs/remotes/origin/'):
            if ref != 'refs/remotes/origin/HEAD':
                took['refs/heads/' + ref[len('refs/remotes/origin/'):]] = oid
        elif ref.startswith('refs/tags/'):
            took[ref] = oid
    return took


def gitdirs(top):
    found = [top / '.git']
    modules = top / '.git/modules'
    for config in sorted(modules.rglob('config')) if modules.exists() else []:
        if (config.parent / 'HEAD').is_file():
            found.append(config.parent)
    return found


def repo_state(gitdir, keep=None):
    """A repository's refs, objects, HEAD and config; with keep (the remote's
    refs that held still), only its refs for those, and the objects they and
    HEAD reach."""
    refs = git_out(gitdir, '--git-dir=' + str(gitdir), 'for-each-ref', '--format=%(refname) %(objectname) %(symref)')
    if keep is None:
        listed = git_out(gitdir, '--git-dir=' + str(gitdir), 'rev-list', '--objects', '--all')
    else:
        def kept(ref):
            if ref.startswith('refs/remotes/origin/'):
                rest = ref[len('refs/remotes/origin/'):]
                return rest == 'HEAD' or 'refs/heads/' + rest in keep
            if ref.startswith(('refs/heads/', 'refs/tags/')):
                return ref in keep
            return True
        lines = [line for line in refs.decode().splitlines() if kept(line.split(' ', 1)[0])]
        refs = ''.join(line + '\n' for line in lines).encode()
        tips = ''.join(line.split(' ', 1)[0] + '\n' for line in lines) + 'HEAD\n'
        q = subprocess.run([git, '--git-dir=' + str(gitdir), 'rev-list', '--objects', '--stdin'], env=env,
                           input=tips.encode(), capture_output=True, timeout=600)
        assert q.returncode == 0, ('rev-list', q.stderr[-300:])
        listed = q.stdout
    ids = sorted({line.split()[0] for line in listed.splitlines()})
    digest = hashlib.sha256()
    if ids:
        q = subprocess.run([git, '--git-dir=' + str(gitdir), 'cat-file', '--batch'], env=env, capture_output=True,
                           input=b''.join(i + b'\n' for i in ids), timeout=600)
        digest.update(q.stdout)
    config = (gitdir / 'config').read_bytes().decode(errors='replace')
    if a.field:
        # macOS only: Git's two core lines for a case-folding file system
        # (as tools/submodule-test.py drops them in field mode).
        config = config.replace('\tignorecase = true\n\tprecomposeunicode = true\n', '')
    return dict(refs=refs.decode(), head=(gitdir / 'HEAD').read_bytes().decode(errors='replace'),
                objects=len(ids), objects_sha256=digest.hexdigest(), config=config)


def tree_state(top, keeps=None):
    """The worktree and every repository's repo_state; keeps maps a
    repository's path under top to the refs held in it (absent: all)."""
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
        rel = gitdir.relative_to(top).as_posix()
        state[rel] = repo_state(gitdir, (keeps or {}).get(rel))
    return state


def verdict(name, problems, detail=None):
    (out / (name + '.json')).write_text(json.dumps(dict(problems=problems, **(detail or {})), indent=1) + '\n')
    print(('PASS ' if not problems else 'FAIL ') + name + ('' if not problems else ' ' + '; '.join(problems)),
          flush=True)
    if problems:
        failed.append(name)


def remotes_of(top, web=WEB):
    """The superproject's URL and every submodule's, as the clone took them."""
    urls = [web]
    for gitdir in gitdirs(top)[1:]:
        q = subprocess.run([git, '--git-dir=' + str(gitdir), 'config', 'remote.origin.url'], env=env,
                           capture_output=True, timeout=60)
        if q.returncode == 0:
            urls.append(q.stdout.decode().strip())
    return urls


def web_row():
    name = 'live-wolf-web'
    web = a.web_url or WEB
    problems = []
    for attempt in range(2):
        problems = []
        work = clones / ('web-%d' % attempt)
        work.mkdir()
        before = listing(web)
        oracle = run([git, 'clone', '-q', '--recurse-submodules', web, 'git'], work, target=work / 'git', row=name,
                     tool='git')
        stalled = stalled_twice(('git', oracle))
        if stalled:
            problems.extend(stalled)
            break
        if oracle['exit']:
            problems.append('pinned Git could not clone wolf-web: ' + oracle['stderr'][-300:])
            break
        urls = remotes_of(work / 'git', web)
        top = work / 'git'
        # Each repository Git's clone made: its path, its remote and what it took.
        repos = []
        for gitdir in gitdirs(top):
            rel = gitdir.relative_to(top).as_posix()
            if rel == '.git':
                url = web
            else:
                q = subprocess.run([git, '--git-dir=' + str(gitdir), 'config', 'remote.origin.url'], env=env,
                                   capture_output=True, timeout=60)
                url = q.stdout.decode().strip()
            repos.append((rel, url, took_refs(gitdir)))
        if a.between_clones:
            # Test only: the local witness moves a submodule remote's refs here.
            subprocess.run(a.between_clones, shell=True, check=True, env=env, timeout=120)
        middle = {rel: listing(url) for rel, url, _ in repos if rel != '.git'}
        candidate = run([den, 'clone', '-q', '--recurse-submodules', web, 'den'], work, target=work / 'den',
                        row=name, tool='den')
        print('LIVE %s attempt=%d retries=den:%d,git:%d quiet=den:%.1fs,git:%.1fs wall=den:%.2fs,git:%.2fs' % (
            name, attempt, candidate['retries'], oracle['retries'], candidate['quiet'], oracle['quiet'],
            candidate['wall'], oracle['wall']), flush=True)
        stalled = stalled_twice(('den', candidate))
        if stalled:
            problems.extend(stalled)
            break
        after = listing(web)
        ends = {rel: listing(url) for rel, url, _ in repos if rel != '.git'}
        if before is None or after is None or None in middle.values() or None in ends.values():
            problems.append('pinned Git could not list a remote of wolf-web')
            break
        # What held, repository by repository: the superproject's refs from
        # before Git's clone to after den's, and each submodule's from what
        # Git's clone took to after den's. Only the superproject's HEAD and
        # its branch decide the checkouts; a submodule's is its gitlink.
        keeps, moved, critical = {}, [], []
        for rel, url, took in repos:
            if rel == '.git':
                (first, head_before), (last, head_after) = live['ref_table'](before), live['ref_table'](after)
                head_moved = first.get('HEAD') != last.get('HEAD') or head_before != head_after
                first = {k: v for k, v in first.items() if k != 'HEAD'}
                last = {k: v for k, v in last.items() if k != 'HEAD'}
                gone = live['drift'](first, took, last)
                critical += (['HEAD'] if head_moved else []) + [r for r in gone if r in {head_before, head_after}]
                gone = [r for r in gone if r not in {head_before, head_after}]
                label = ''
            else:
                mid = {k: v for k, v in live['ref_table'](middle[rel])[0].items() if k != 'HEAD'}
                end = {k: v for k, v in live['ref_table'](ends[rel])[0].items() if k != 'HEAD'}
                gone = live['drift'](took, mid, end)
                first, last = mid, end
                label = rel[len('.git/modules/'):] + ':'
            if gone:
                keeps[rel] = set(first) - set(gone)
                moved += [label + r for r in gone]
        action = live['judge'](name, sorted(moved), sorted(critical), attempt)
        if action == 'retry':
            shutil.rmtree(work)
            continue
        if action == 'fail':
            problems.append('refs moved during the row: ' + ','.join(sorted(critical) or sorted(moved)))
            break
        for field in ('exit', 'stdout', 'stderr'):
            if oracle[field] != candidate[field]:
                problems.append('process %s differs: den exit %d stderr %r' % (field, candidate['exit'],
                                                                                 candidate['stderr'][-400:]))
        if not problems:
            theirs, ours = tree_state(work / 'git', keeps), tree_state(work / 'den', keeps)
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
        detail = dict(urls=urls, git_wall=oracle['wall'], den_wall=candidate['wall'],
                      git_retries=oracle['retries'], den_retries=candidate['retries'],
                      moved_retries=attempt, excluded=sorted(moved))
        verdict(name, problems, detail)
        return
    verdict(name, problems)


def pinned_rows():
    for repo in PINNED:
        name = 'live-%s-gitlinks' % repo
        url = 'https://github.com/wolffe-lang/%s.git' % repo
        work = clones / repo
        work.mkdir()
        q = run([git, 'clone', '-q', url, 'c'], work, target=work / 'c', row=name, tool='git')
        print('LIVE %s retries=git:%d quiet=git:%.1fs wall=git:%.2fs' % (name, q['retries'], q['quiet'], q['wall']),
              flush=True)
        stalled = stalled_twice(('git', q))
        if stalled:
            verdict(name, stalled)
            continue
        if q['exit']:
            verdict(name, [clone_problem(repo, q)])
            continue
        c = work / 'c'
        moved = git_out(c, 'log', '-1', '--format=%H', '--', 'upstream').decode().strip()
        problems = []
        # Path-limited history, and diff and status in a repository with
        # attributes, are den limits for every repository; the moved gitlink
        # is read here by the commands that need neither.
        commands = [['submodule', 'status'], ['submodule', 'status', '--cached'], ['ls-tree', 'HEAD', 'upstream'],
                    ['ls-tree', moved, 'upstream'], ['ls-tree', moved + '~1', 'upstream'], ['ls-files', '-s', 'upstream'],
                    ['cat-file', '-p', moved + '^{tree}'], ['rev-parse', moved + ':upstream']]
        for argv in commands:
            oracle = run([git, *argv], c, 300)
            candidate = run([den, *argv], c, 300)
            for field in ('exit', 'stdout', 'stderr'):
                if oracle[field] != candidate[field]:
                    problems.append('%s: %s differs (den exit %d, %r)' % (' '.join(argv[:2]), field, candidate['exit'],
                                                                          str(candidate[field])[-200:]))
        verdict(name, problems, dict(moved=moved, commands=commands))


def ssh_row():
    name = 'live-wolf-std-ssh'
    # Opt-in: the row would use the machine's own ssh key.
    if os.environ.get('DEN_LIVE_SSH') != '1':
        print('SKIP %s reason=DEN_LIVE_SSH not set (the row uses this machine\'s ssh key)' % name, flush=True)
        return
    q = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-T', 'git@github.com'],
                       env=env, capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
    if b'successfully authenticated' not in q.stderr:
        print('SKIP %s reason=no ssh key for github.com answers' % name, flush=True)
        return
    rewrite = dict(GIT_CONFIG_COUNT='2', GIT_CONFIG_KEY_1='url.git@github.com:.insteadOf',
                   GIT_CONFIG_VALUE_1='https://github.com/')
    url = 'https://github.com/wolffe-lang/wolf-std.git'
    for attempt in range(2):
        work = clones / ('ssh-%d' % attempt)
        work.mkdir()
        # The same guard as the other clone rows: compare what held still.
        before = listing(url)
        oracle = run([git, 'clone', '-q', url, 'git'], work, extra=rewrite, target=work / 'git', row=name, tool='git')
        candidate = run([den, 'clone', '-q', url, 'den'], work, extra=rewrite, target=work / 'den', row=name,
                        tool='den')
        after = listing(url)
        stalled = stalled_twice(('den', candidate), ('git', oracle))
        if stalled:
            verdict(name, stalled)
            return
        if before is None or after is None:
            verdict(name, ['pinned Git could not list wolf-std'])
            return
        kept, moved, critical = live['held'](before, after)
        action = live['judge'](name, moved, critical, attempt)
        if action == 'retry':
            continue
        if action == 'fail':
            verdict(name, ['refs moved during the row: ' + ','.join(critical or moved)])
            return
        keeps = {'.git': set(kept)} if moved else None
        problems = [f + ' differs' for f in ('exit', 'stdout', 'stderr') if oracle[f] != candidate[f]]
        if not problems and tree_state(work / 'git', keeps) != tree_state(work / 'den', keeps):
            problems.append('state differs')
        verdict(name, problems, dict(moved_retries=attempt, excluded=moved))
        return


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
            work = clones / ('timed-%s-%d' % (tool, i))
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


def selected(name):
    return not a.only or __import__('re').search(a.only, name)


if a.timed:
    timed()
else:
    if selected('live-wolf-web'):
        web_row()
    if any(selected('live-%s-gitlinks' % r) for r in PINNED):
        pinned_rows()
    if selected('live-wolf-std-ssh'):
        ssh_row()
if failed:
    raise SystemExit('FAIL submodule-live: ' + ', '.join(failed))
print('submodule-live: %s %d rows' % (a.tier, len(names)), flush=True)
