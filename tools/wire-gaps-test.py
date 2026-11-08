#!/usr/bin/env python3
"""vc24: den's everyday wire gaps, held to the pinned Git byte for byte.

Run through tools/env in the oracle container:

    tools/env python3 -I tools/wire-gaps-test.py --tier native [--family F[,F]]

Families (each row is named FAMILY-CASE-TRANSPORT, or FAMILY-CASE when it has
no transport):
  push       den#71: a short destination placed as git-push(1) places it
             (the remote's refs by gitrevisions(7)'s <refname> order, then
             the source's namespace), -u, and Git's refusals
  clone      den#72: clone with no directory (the "humanish" name), --bare,
             an existing empty or non-empty destination, the empty-repository
             warning, and the named operand refusals
  ls-remote  den#68: ls-remote's listing, filters, patterns and exit codes
  fetch      den#70: fetch REMOTE REFSPEC... for a configured remote
  memory     den#63: clone memory against history length, under a hard cap
  cost       den#63: a clone's CPU against the pinned Git's on a real
             repository (pelt's trunk at a pinned commit), git:// and runs
             in turn, at most COST_RATIO times Git's
The rev-parse rows (den#69) are tools/rev-parse-test.py's.

Transports: a plain local path, file://, git:// (the pinned git daemon, with
receive-pack enabled), ssh (a local stand-in that drops the client options and
the host and runs the remote command through /bin/sh, as the far side's shell
would) and https (the pinned OpenSSL terminator in front of the pinned
git-http-backend, http-git-test.py's fixture). Each row runs Git first, then
resets every repository it touched to the same starting bytes at the same
paths and runs den, so both see the same URLs; then it compares stdout,
stderr and exit status byte for byte, and the state each left (refs, HEAD,
FETCH_HEAD, remote and branch configuration, reachable objects, worktree).
No row is skipped or reviewed: a difference is FAIL. --field runs against a
Git that is not the pinned one (the macOS field leg); https and memory need
the Linux container and are left out there, by name.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import signal
import socket
import subprocess
import sys
import time

GIT_SHA256 = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
FAMILIES = ('push', 'clone', 'ls-remote', 'fetch', 'memory', 'cost')
# The cost row is timed and runs alone, on the release tier (tools/check-http's
# release-clone-cost step); every other family is the default.
DEFAULT_FAMILIES = ('push', 'clone', 'ls-remote', 'fetch', 'memory')
TRANSPORTS = ('local', 'file', 'git', 'ssh', 'https')
MIB = 1 << 20

SSH_STANDIN = r'''#!/bin/sh
# A local ssh stand-in: drop the client's options and the host, then run the
# remote command's words, joined by spaces, through /bin/sh as sshd would.
while [ "$#" -gt 0 ]; do
    case "$1" in
    -o | -p | -l | -i | -F | -J) shift 2 ;;
    --) shift; break ;;
    -*) shift ;;
    *) break ;;
    esac
done
shift
exec /bin/sh -c "$*"
'''

# A fresh, small parent for each measured den run: a child's peak RSS starts
# at its parent's (an exec keeps the high-water mark), so den's own peak is
# read from wait4 in a process that is only this.
LAUNCH = r'''
import os, sys, json, time
t = time.monotonic()
pid = os.fork()
if pid == 0:
    fd = os.open(os.devnull, os.O_RDWR); os.dup2(fd, 0); os.dup2(fd, 1)
    os.execvp(sys.argv[1], sys.argv[1:])
_, status, ru = os.wait4(pid, 0)
print(json.dumps(dict(exit=os.waitstatus_to_exitcode(status), wall=round(time.monotonic() - t, 2),
                      cpu=round(ru.ru_utime + ru.ru_stime, 2), maxrss_kib=ru.ru_maxrss)))
'''


class Harness:
    def __init__(self, args):
        self.root = Path(__file__).resolve().parent.parent
        self.git = str(Path(os.environ['DEN_GIT']).resolve())
        if not args.field:
            digest = hashlib.sha256(Path(self.git).read_bytes()).hexdigest()
            assert digest == GIT_SHA256, 'pinned Git digest'
        self.field = args.field
        self.den = str(self.root / 'target' / args.tier / 'den')
        if not Path(self.den).is_file():
            raise SystemExit('FAIL wire-gaps-input: build target/' + args.tier + '/den first')
        self.out = self.root / 'target/runs' / (('clone-cost-' if args.family == 'cost' else 'wire-gaps-') + args.tier)
        if self.out.exists():
            raise SystemExit('FAIL wire-gaps-fresh-output: select a fresh build directory')
        self.out.mkdir(parents=True)
        (self.out / 'bin').mkdir()
        standin = self.out / 'bin/ssh'
        standin.write_text(SSH_STANDIN)
        standin.chmod(0o755)
        self.env = dict(os.environ)
        self.env.update(PATH=str(self.out / 'bin') + ':' + self.env['PATH'], GIT_SSH_VARIANT='ssh',
                        GIT_TERMINAL_PROMPT='0', GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='protocol.version',
                        GIT_CONFIG_VALUE_0='2')
        self.srv = self.out / 'srv'
        self.srv.mkdir()
        self.failed, self.passed, self.results = [], 0, {}
        self.daemon = None
        self.https = None
        self.https_starts = 0
        self.https_errors = []
        self.extra = {}

    # -- processes ------------------------------------------------------
    def run(self, argv, cwd, extra=None, timeout=300, stdin=b''):
        result = subprocess.run(list(map(str, argv)), cwd=str(cwd), env={**self.env, **self.extra, **(extra or {})},
                                input=stdin, capture_output=True, timeout=timeout)
        return dict(exit=result.returncode, stdout=result.stdout, stderr=result.stderr)

    def git_out(self, cwd, *argv, data=None):
        result = subprocess.run([self.git, *map(str, argv)], cwd=str(cwd), env={**self.env, **self.extra},
                                input=data, capture_output=True, timeout=300)
        if result.returncode:
            raise AssertionError('pinned Git %s failed in %s: %s' % (
                argv[0], Path(cwd).name, result.stderr.decode(errors='replace').strip()[-300:]))
        return result.stdout

    # -- fixtures -------------------------------------------------------
    def commit(self, repo, name, text, message):
        path = Path(repo) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        self.git_out(repo, 'add', name)
        self.git_out(repo, 'commit', '-q', '-m', message)

    def snapshot(self, paths, label='saved'):
        """Byte copies of the repositories a row may touch, restored before
        each tool runs, so both start from the same bytes at the same paths."""
        saved = self.out / label
        shutil.rmtree(saved, ignore_errors=True)
        saved.mkdir()
        for i, path in enumerate(paths):
            if Path(path).exists():
                shutil.copytree(path, saved / str(i), symlinks=True)
        return saved

    def restore(self, saved, paths):
        for i, path in enumerate(paths):
            shutil.rmtree(path, ignore_errors=True)
            if Path(path).is_symlink() or Path(path).is_file():
                Path(path).unlink()
            if (saved / str(i)).exists():
                shutil.copytree(saved / str(i), path, symlinks=True)

    def state(self, repo, worktree=True):
        """What a row compares after a run: refs, HEAD, FETCH_HEAD, remote and
        branch configuration, reachable objects, the worktree."""
        repo = Path(repo)
        if not repo.exists():
            return dict(missing=True)
        gitdir = repo / '.git' if (repo / '.git').is_dir() else repo
        if not (gitdir / 'HEAD').is_file():
            # Not a repository: what is there, by name and content.
            return dict(files={p.relative_to(repo).as_posix(): p.read_bytes().hex()
                               for p in sorted(repo.rglob('*')) if p.is_file()})
        refs = self.git_out(repo, 'for-each-ref', '--format=%(refname) %(objectname) %(symref)')
        ids = sorted({line.split()[0] for line in
                      self.git_out(repo, 'rev-list', '--objects', '--all').splitlines()})
        digest = hashlib.sha256()
        if ids:
            digest.update(self.git_out(repo, 'cat-file', '--batch', data=b''.join(i + b'\n' for i in ids)))
        config = subprocess.run([self.git, 'config', '--local', '--get-regexp', r'^(remote|branch)\.'], cwd=str(repo),
                                env=self.env, capture_output=True, timeout=60).stdout
        files = {}
        if worktree and gitdir != repo:
            for path in sorted(repo.rglob('*')):
                relative = path.relative_to(repo).as_posix()
                if relative == '.git' or relative.startswith('.git/'):
                    continue
                if path.is_file():
                    files[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        fetch_head = gitdir / 'FETCH_HEAD'
        return dict(refs=refs.decode(), head=(gitdir / 'HEAD').read_bytes().decode(errors='replace'),
                    fetch_head=fetch_head.read_bytes().decode(errors='replace') if fetch_head.exists() else None,
                    objects=len(ids), objects_sha256=digest.hexdigest(), config=config.decode(),
                    worktree=files)

    # -- verdicts -------------------------------------------------------
    def verdict(self, name, problems, detail=None):
        self.results[name] = dict(problems=problems, **(detail or {}))
        (self.out / 'results.json').write_text(json.dumps(self.results, indent=2, sort_keys=True) + '\n')
        # 'FAIL <row> <why>': a record reads the row's name up to the first space.
        if problems:
            self.failed.append(name)
            print('FAIL ' + name + ' ' + '; '.join(problems), flush=True)
        else:
            self.passed += 1
            print('PASS ' + name, flush=True)

    def differ(self, oracle, candidate, problems):
        for field in ('exit', 'stdout', 'stderr'):
            if oracle[field] != candidate[field]:
                if field == 'exit':
                    problems.append('exit: git %d den %d' % (oracle['exit'], candidate['exit']))
                else:
                    problems.append('%s: git %r den %r' % (field, oracle[field][-400:], candidate[field][-400:]))

    def compare(self, name, steps, paths, observe, setup=None, base=None):
        """Run each tool's steps from the same starting bytes (the fixture's
        pristine snapshot when one is given, else the paths as they are);
        compare every step's process bytes and the observed state after the
        last."""
        saved = base or self.snapshot(paths)
        outcome = {}
        for tool in ('git', 'den'):
            self.restore(saved, paths)
            if setup:
                setup(tool)
            binary = self.git if tool == 'git' else self.den
            runs = []
            for argv, cwd in steps:
                runs.append(self.run([binary, *argv], cwd))
            outcome[tool] = (runs, {str(p): self.state(p) for p in observe})
        problems = []
        for i, (oracle, candidate) in enumerate(zip(outcome['git'][0], outcome['den'][0])):
            step = []
            self.differ(oracle, candidate, step)
            problems += [('step %d ' % i if len(steps) > 1 else '') + p for p in step]
        for path in outcome['git'][1]:
            theirs, ours = outcome['git'][1][path], outcome['den'][1][path]
            keys = [key for key in theirs if ours.get(key) != theirs[key]]
            if keys or set(ours) != set(theirs):
                problems.append('state of %s differs: %s' % (Path(path).name, ', '.join(keys) or 'presence'))
        self.verdict(name, problems, dict(git=[dict(exit=r['exit']) for r in outcome['git'][0]]))
        # Every row leaves its paths as it found them.
        self.restore(saved, paths)
        if base is None:
            shutil.rmtree(saved, ignore_errors=True)

    # -- transports -----------------------------------------------------
    def start_daemon(self):
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        self.daemon = subprocess.Popen([self.git, 'daemon', '--reuseaddr', '--export-all', '--enable=receive-pack',
                                        '--listen=127.0.0.1', '--port=' + str(port), '--base-path=' + str(self.srv),
                                        str(self.srv)], env=self.env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            assert self.daemon.poll() is None, 'git daemon exited at startup'
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError('git daemon startup timeout')
        self.daemon_port = port

    def start_https(self):
        fixture = runpy.run_path(str(self.root / 'tools/http-git-test.py'))
        for path, digest in fixture['OPENSSL_PINS'].items():
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, 'pinned TLS oracle digest'
        # A fixture for each family that uses https (url starts it, main stops
        # it after the family): its bridge waits at most 60 s for each next
        # request, so it must not sit idle through another family's rows.
        # Its keys live outside target/runs, which is published evidence, and
        # are removed when the fixture stops (tools/evidence-modes.py).
        self.https_starts += 1
        pki = self.root / 'target/pki' / ('%s-%d' % (self.out.name, self.https_starts))
        shutil.rmtree(pki, ignore_errors=True)
        pki.mkdir(parents=True)
        self.https_pki = pki

        def openssl(*argv):
            result = subprocess.run(['/usr/bin/openssl', *map(str, argv)], env=self.env, capture_output=True,
                                    timeout=120)
            assert result.returncode == 0, 'fixture openssl ' + str(argv[0])

        openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '2',
                '-subj', '/CN=Wire gaps fixture root', '-addext', 'basicConstraints=critical,CA:TRUE',
                '-addext', 'keyUsage=critical,keyCertSign,cRLSign', '-keyout', pki / 'ca.key', '-out', pki / 'ca.pem')
        openssl('x509', '-in', pki / 'ca.pem', '-outform', 'DER', '-out', pki / 'ca.der')
        (pki / 'leaf.cnf').write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n'
                                      'extendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost\n')
        openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=localhost',
                '-keyout', pki / 'leaf.key', '-out', pki / 'leaf.csr')
        openssl('x509', '-req', '-in', pki / 'leaf.csr', '-CA', pki / 'ca.pem', '-CAkey', pki / 'ca.key',
                '-CAcreateserial', '-days', '1', '-sha256', '-extfile', pki / 'leaf.cnf', '-out', pki / 'leaf.pem')
        # The fixture serves one repository, <root>/remote.git; a row points
        # that name at its own repository by a symbolic link.
        self.https_root = self.out / ('https-root-%d' % self.https_starts)
        self.https_root.mkdir()
        self.https = fixture['Server'](self.https_root, self.git, self.env, 'tls', pki, '', lambda data: None)
        self.extra.update(GIT_SSL_CAINFO=str(pki / 'ca.pem'), DEN_TLS_ROOTS=str(pki / 'ca.der'))

    def url(self, transport, repo):
        repo = Path(repo)
        if transport == 'local':
            return str(repo)
        if transport == 'file':
            return repo.as_uri()
        if transport == 'git':
            return 'git://127.0.0.1:%d/%s' % (self.daemon_port, repo.relative_to(self.srv).as_posix())
        if transport == 'ssh':
            return 'ssh://localhost' + str(repo)
        if self.https is None:
            self.start_https()
        link = self.https_root / 'remote.git'
        if link.is_symlink():
            link.unlink()
        link.symlink_to(repo)
        return self.https.url

    def stop_https(self):
        if self.https:
            self.https.close()
            self.https_errors += self.https.errors
            self.https = None
            shutil.rmtree(self.https_pki, ignore_errors=True)

    def stop(self):
        if self.daemon:
            self.daemon.terminate()  # This fixture's pid only.
            self.daemon.wait(timeout=30)
        self.stop_https()
        if self.https_errors:
            self.verdict('wire-gaps-https-fixture', ['fixture errors: ' + ', '.join(self.https_errors)])

    def no_private_keys(self):
        """target/runs is published evidence (tools/evidence-modes.py): after
        every fixture has stopped, this run's tree holds no private key, by
        name (*.key) or by content."""
        left = []
        for path in sorted(self.out.rglob('*')):
            if not path.is_file() or path.is_symlink():
                continue
            with open(path, 'rb') as handle:
                head = handle.read(65536)
            if path.suffix == '.key' or b'PRIVATE KEY-----' in head:
                left.append(path.relative_to(self.root).as_posix())
        self.verdict('wire-gaps-no-private-keys', ['private key left in the evidence tree: ' + p for p in left])

    def transports(self):
        return [t for t in TRANSPORTS if not (self.field and t == 'https')]


def bare(h, name, branch='main'):
    path = h.srv / name
    shutil.rmtree(path, ignore_errors=True)
    h.git_out(h.srv, 'init', '-q', '--bare', '-b', branch, str(path))
    for key, value in (('gc.auto', '0'), ('maintenance.auto', 'false')):
        h.git_out(path, 'config', key, value)
    return path


def work(h, name, branch='trunk'):
    path = h.out / name
    shutil.rmtree(path, ignore_errors=True)
    h.git_out(h.out, 'init', '-q', '-b', branch, str(path))
    return path


# -- den#71 ------------------------------------------------------------------
def family_push(h):
    for transport in h.transports():
        w = work(h, 'push-w')
        h.commit(w, 'f', 'one\n', 'one')
        h.git_out(w, 'tag', 'v1')
        h.git_out(w, 'tag', '-a', '-m', 'annotated', 'v2')
        h.commit(w, 'f', 'two\n', 'two')
        h.git_out(w, 'branch', 'side', 'HEAD~1')
        h.git_out(w, 'update-ref', 'refs/remotes/origin/rt', 'HEAD~1')
        trunk = h.git_out(w, 'rev-parse', 'trunk').decode().strip()
        tree = h.git_out(w, 'rev-parse', 'trunk^{tree}').decode().strip()
        tag = h.git_out(w, 'rev-parse', 'v2').decode().strip()
        remote = bare(h, 'push-r.git')
        h.git_out(w, 'remote', 'add', 'origin', h.url(transport, remote))
        paths = [w, remote]
        pristine = h.snapshot(paths, 'push-base')

        def row(case, *argv, prepare=None):
            def setup(tool):
                if prepare:
                    prepare()
            h.compare('push-%s-%s' % (case, transport), [(list(argv), w)], paths, [w, remote], setup, pristine)

        row('infer-heads', 'push', 'origin', 'trunk')
        row('upstream', 'push', '-u', 'origin', 'trunk')
        row('rename', 'push', 'origin', 'trunk:other')
        row('head', 'push', 'origin', 'HEAD:new')
        row('tag', 'push', 'origin', 'v1')
        row('tag-annotated', 'push', 'origin', 'v2:v2x')
        row('src-missing', 'push', 'origin', 'nosuch')
        row('src-missing-dst', 'push', 'origin', 'nosuch:dst')
        row('commit-id', 'push', 'origin', trunk + ':new')
        row('revision', 'push', 'origin', 'trunk~0:new')
        row('remote-tracking', 'push', 'origin', 'refs/remotes/origin/rt:new')
        row('tree', 'push', 'origin', tree + ':t')
        row('tag-object', 'push', 'origin', tag + ':t')

        def advice_off():
            h.git_out(w, 'config', 'advice.pushUnqualifiedRefname', 'false')
        row('advice-off', 'push', 'origin', trunk + ':new', prepare=advice_off)

        def detach():
            h.git_out(w, 'checkout', '-q', '--detach')
        row('detached', 'push', 'origin', 'HEAD:det', prepare=detach)
        row('detached-bare-head', 'push', 'origin', 'HEAD', prepare=detach)

        def ambiguous_source():
            h.git_out(w, 'branch', 'x')
            h.git_out(w, 'tag', 'x')
        row('src-ambiguous', 'push', 'origin', 'x', prepare=ambiguous_source)

        # Destinations that exist on the remote: matched there, not inferred.
        def seeded():
            h.git_out(w, 'push', '-q', 'origin', 'side:refs/heads/both', 'side:refs/tags/both',
                      'side:refs/other/q', 'side:refs/remotes/rr/zz')
        row('dst-ambiguous', 'push', 'origin', 'trunk:both', prepare=seeded)
        row('dst-remote-match', 'push', 'origin', 'trunk:other/q', prepare=seeded)
        row('dst-remote-tracking', 'push', 'origin', 'trunk:rr/zz', prepare=seeded)
        row('dst-match-commit-id', 'push', 'origin', trunk + ':other/q', prepare=seeded)
        row('dst-match-up-to-date', 'push', 'origin', 'side:other/q', prepare=seeded)
        row('mixed-one-bad', 'push', 'origin', 'trunk:refs/heads/good', 'nosuch')
        shutil.rmtree(pristine, ignore_errors=True)
        empty_remote_rows(h, transport)


def empty_remote_rows(h, transport):
    """den#71's console session: clone an empty repository (as a new hosted
    repository is), commit, push the new branch. Each tool clones and pushes;
    the commit is the pinned Git's in both clones."""
    for case, server, extra in (('unborn', 'advertise', {}), ('no-unborn', 'ignore', {})):
        remote = bare(h, 'push-empty.git', 'trunk')
        h.git_out(remote, 'config', 'lsrefs.unborn', server)
        url = h.url(transport, remote)
        clone = h.out / 'push-empty-clone'
        shutil.rmtree(clone, ignore_errors=True)
        paths = [remote, clone]
        saved = h.snapshot(paths)
        outcome = {}
        for tool in ('git', 'den'):
            h.restore(saved, paths)
            binary = h.git if tool == 'git' else h.den
            runs = [h.run([binary, 'clone', url, clone], h.out, extra)]
            if (clone / '.git').is_dir():
                h.commit(clone, 'f', 'first\n', 'first')
            runs.append(h.run([binary, 'push', 'origin', 'trunk'], clone, extra))
            runs.append(h.run([binary, 'push', '-u', 'origin', 'HEAD'], clone, extra))
            outcome[tool] = (runs, h.state(remote), h.state(clone) if clone.exists() else None)
        problems = []
        for i, (oracle, candidate) in enumerate(zip(outcome['git'][0], outcome['den'][0])):
            step = []
            h.differ(oracle, candidate, step)
            problems += [('clone ' if i == 0 else 'push %d ' % i) + p for p in step]
        for i, label in ((1, 'remote'), (2, 'clone')):
            if outcome['git'][i] != outcome['den'][i]:
                theirs, ours = outcome['git'][i] or {}, outcome['den'][i] or {}
                problems.append('%s state differs: %s' % (label, ', '.join(k for k in theirs if ours.get(k) != theirs[k])))
        h.verdict('push-empty-remote-%s-%s' % (case, transport), problems)
        shutil.rmtree(saved, ignore_errors=True)
        shutil.rmtree(clone, ignore_errors=True)


# -- den#72 ------------------------------------------------------------------
NAME_SPELLINGS = [
    'git://127.0.0.1:1/x/name.git', 'git://127.0.0.1:1/name', 'git://127.0.0.1:1/', 'git://127.0.0.1:1/name.git/',
    'git://127.0.0.1:1/o/name/.git', 'git://127.0.0.1:1/o/name.git/.git/',
    'https://127.0.0.1:1/o/name.git', 'https://127.0.0.1:1/o/name', 'https://127.0.0.1:1/', 'https://127.0.0.1:1',
    'https://user:pw@127.0.0.1:1', 'https://u:p@127.0.0.1:1/x/', 'https://127.0.0.1:1/~user', 'https://127.0.0.1:1//',
    'https://127.0.0.1:1/o/name.git///', 'https://127.0.0.1:1/o/.git', 'https://127.0.0.1:1/.git',
    'https://127.0.0.1:1/o/name.bundle', 'https://127.0.0.1:1/o/name.GIT', 'https://127.0.0.1:1/a:b',
    'https://127.0.0.1:1/o/name.git.git',
    'ssh://u@nowhere.invalid:22/~/name.git', 'ssh://nowhere.invalid/o/name.git', 'ssh://u@nowhere.invalid/',
    'nowhere.invalid:o/name.git', 'nowhere.invalid:name', 'nowhere.invalid:name/.git', 'nowhere.invalid:/abs/name.git',
    'u@nowhere.invalid:name.git', 'nowhere.invalid:', 'u@nowhere.invalid:', 'nowhere.invalid:o/',
    'nowhere.invalid:.git', 'nowhere.invalid:/.git', 'nowhere.invalid:~u/name.git',
]


def family_clone(h):
    # The name alone: Git derives the directory before it connects, and so
    # must den; these URLs connect nowhere, so only the first line, a failing
    # exit and an untouched directory are compared.
    # An ssh that connects nowhere, for both tools.
    nowhere = h.out / 'bin-nowhere'
    nowhere.mkdir()
    (nowhere / 'ssh').write_text('#!/bin/sh\necho "ssh: connect to host nowhere.invalid: unreachable" >&2\nexit 255\n')
    (nowhere / 'ssh').chmod(0o755)
    for i, spelling in enumerate(NAME_SPELLINGS):
        if h.field and spelling.startswith('https'):
            continue
        cwd = h.out / 'clone-names'
        problems, seen = [], {}
        for tool in ('git', 'den'):
            shutil.rmtree(cwd, ignore_errors=True)
            cwd.mkdir()
            ran = h.run([h.git if tool == 'git' else h.den, 'clone', spelling], cwd,
                        extra=dict(PATH=str(nowhere) + ':' + h.env['PATH']), timeout=60)
            seen[tool] = (ran['stderr'].split(b'\n')[0], ran['exit'] != 0, sorted(os.listdir(cwd)))
        if seen['git'] != seen['den']:
            problems.append('git %r den %r' % (seen['git'], seen['den']))
        h.verdict('clone-name-%02d' % i, problems, dict(spelling=spelling))
    for transport in h.transports():
        source = work(h, 'clone-src', 'main')
        h.commit(source, 'README', 'one\n', 'one')
        h.git_out(source, 'tag', '-a', '-m', 'annotated', 'v1')
        h.commit(source, 'sub/f', 'two\n', 'two')
        remote = h.srv / 'name.git'
        shutil.rmtree(remote, ignore_errors=True)
        h.git_out(h.srv, 'clone', '-q', '--bare', str(source), str(remote))
        cwd = h.out / 'clone-cwd'
        shutil.rmtree(cwd, ignore_errors=True)
        cwd.mkdir()
        url = h.url(transport, remote)
        # The https fixture serves its one repository as /remote.git.
        name = 'remote' if transport == 'https' else 'name'
        empty_name = 'remote' if transport == 'https' else 'empty'
        spellings = [('plain', url)]
        if transport in ('local', 'file'):
            # The same repository named five ways: with and without .git, a
            # trailing slash, and a non-bare repository's trailing /.git.
            plain = h.out / 'srvplain' / 'name'
            shutil.rmtree(plain.parent, ignore_errors=True)
            plain.parent.mkdir()
            h.git_out(plain.parent, 'clone', '-q', str(source), str(plain))
            def spell(path):
                return path if transport == 'local' else 'file://' + path
            spellings += [('no-suffix', spell(str(remote)[:-4])), ('slash', spell(str(remote) + '/')),
                          ('worktree', spell(str(plain))), ('dot-git', spell(str(plain) + '/.git')),
                          ('dot-git-slash', spell(str(plain) + '/.git/'))]
        for label, spelling in spellings:
            for flags, suffix in (([], ''), (['--bare'], '-bare')):
                h.compare('clone-%s%s-%s' % (label, suffix, transport), [(['clone', *flags, spelling], cwd)],
                          [cwd], [cwd / (name + '.git' if flags else name)])
        h.compare('clone-quiet-%s' % transport, [(['clone', '-q', url], cwd)], [cwd], [cwd / name])
        (cwd / name).mkdir()
        h.compare('clone-into-empty-dir-%s' % transport, [(['clone', url], cwd)], [cwd], [cwd / name])
        (cwd / name / 'keep').write_text('x\n')
        h.compare('clone-into-nonempty-dir-%s' % transport, [(['clone', url], cwd)], [cwd], [cwd / name])
        shutil.rmtree(cwd / name)
        (cwd / name).write_text('a file\n')
        h.compare('clone-onto-file-%s' % transport, [(['clone', url], cwd)], [cwd], [])
        (cwd / name).unlink()
        h.compare('clone-two-operands-%s' % transport, [(['clone', url, 'named'], cwd)], [cwd], [cwd / 'named'])
        empty = bare(h, 'empty.git', 'trunk')
        h.compare('clone-empty-%s' % transport, [(['clone', h.url(transport, empty)], cwd)], [cwd],
                  [cwd / empty_name])
        h.compare('clone-empty-bare-%s' % transport, [(['clone', '--bare', h.url(transport, empty)], cwd)], [cwd],
                  [cwd / (empty_name + '.git')])
        if transport == 'git':
            # A failure after the destination exists: an existing empty
            # directory is left empty, as Git leaves it.
            (cwd / 'kept').mkdir()
            h.compare('clone-failed-into-empty-dir-git',
                      [(['clone', 'git://127.0.0.1:%d/missing.git' % h.daemon_port, 'kept'], cwd)], [cwd], [])
            seen = sorted(os.listdir(cwd))
            if seen != ['kept'] or os.listdir(cwd / 'kept'):
                h.verdict('clone-failed-into-empty-dir-kept', ['left %r' % seen])
            else:
                h.verdict('clone-failed-into-empty-dir-kept', [])
            shutil.rmtree(cwd / 'kept')
    # Operand errors: named refusals (git prints its usage block instead).
    cwd = h.out / 'clone-cwd'
    for case, argv, text in (('none', [], b'den: wire: Unsupported(clone requires a repository)\n'),
                             ('three', ['a', 'b', 'c'],
                              b'den: wire: Unsupported(clone takes a repository and at most one directory)\n')):
        ran = h.run([h.den, 'clone', *argv], cwd)
        problems = []
        if ran['exit'] != 2 or ran['stderr'] != text or ran['stdout']:
            problems.append('den exit %d stderr %r' % (ran['exit'], ran['stderr']))
        oracle = h.run([h.git, 'clone', *argv], cwd)
        if oracle['exit'] != 129:
            problems.append('pinned Git exit %d, want 129 (a usage error)' % oracle['exit'])
        h.verdict('clone-operands-%s' % case, problems)
    # A missing source: a local path is refused before a name is guessed; a
    # file:// URL after it, by the service.
    for case, spelling in (('missing-local', str(h.srv / 'missing.git')), ('missing-relative', 'missing'),
                           ('missing-file', (h.srv / 'missing.git').as_uri())):
        h.compare('clone-%s' % case, [(['clone', spelling], cwd)], [cwd], [])
    nameless = h.run([h.den, 'clone', 'file:///'], cwd)
    oracle = h.run([h.git, 'clone', 'file:///'], cwd)
    problems = []
    h.differ(oracle, nameless, problems)
    h.verdict('clone-no-name', problems)


# -- den#68 ------------------------------------------------------------------
def family_ls_remote(h):
    source = work(h, 'ls-src', 'main')
    h.commit(source, 'f', 'one\n', 'one')
    h.git_out(source, 'branch', 'topic')
    h.git_out(source, 'branch', 'feature/x')
    h.git_out(source, 'tag', 'v1')
    h.git_out(source, 'tag', '-a', '-m', 'annotated', 'v2')
    h.git_out(source, 'tag', '-a', '-m', 'nested', 'v2.1', 'v2')
    h.commit(source, 'f', 'two\n', 'two')
    remote = h.srv / 'ls.git'
    shutil.rmtree(remote, ignore_errors=True)
    h.git_out(h.srv, 'clone', '-q', '--bare', str(source), str(remote))
    h.git_out(remote, 'update-ref', 'refs/pull/1/head', 'HEAD~1')
    h.git_out(remote, 'update-ref', 'refs/notes/commits', 'HEAD')
    empty = bare(h, 'ls-empty.git', 'trunk')
    outside = h.out / 'ls-outside'
    outside.mkdir(exist_ok=True)
    # git(1) GIT_CEILING_DIRECTORIES keeps the outside directory outside the
    # checkout this harness runs in, for both tools.
    h.extra['GIT_CEILING_DIRECTORIES'] = str(h.out)
    for transport in h.transports():
        w = work(h, 'ls-w', 'main')
        url = h.url(transport, remote)
        h.git_out(w, 'remote', 'add', 'origin', url)
        paths = [w]

        def row(case, *argv, cwd=None):
            h.compare('ls-remote-%s-%s' % (case, transport), [(['ls-remote', *argv], cwd or w)], paths, [])

        for case, argv in (('default', []), ('quiet-default', ['-q']), ('named', ['origin']),
                           ('heads', ['--heads', 'origin']), ('branches', ['--branches', 'origin']),
                           ('b', ['-b', 'origin']), ('tags', ['--tags', 'origin']), ('t', ['-t', 'origin']),
                           ('heads-tags', ['--heads', '--tags', 'origin']), ('refs', ['--refs', 'origin']),
                           ('symref', ['--symref', 'origin']), ('symref-head', ['--symref', 'origin', 'HEAD']),
                           ('pattern-branch', ['origin', 'main']), ('pattern-tag', ['origin', 'v2']),
                           ('pattern-glob', ['origin', 'v*']), ('pattern-nested', ['origin', 'feature/*']),
                           ('pattern-tail', ['origin', 'x']), ('pattern-partial', ['origin', 'heads/topic']),
                           ('pattern-full', ['origin', 'refs/heads/topic']), ('pattern-two', ['origin', 'topic', 'main']),
                           ('pattern-none', ['origin', 'nosuch']), ('pattern-inner', ['origin', 'eature/x']),
                           ('pattern-cross', ['origin', 'f*']), ('pattern-head', ['origin', 'HEAD']),
                           ('tags-pattern', ['--tags', 'origin', 'v2']), ('heads-head', ['--heads', 'origin', 'HEAD']),
                           ('refs-head', ['--refs', 'origin', 'HEAD']),
                           ('exit-code-miss', ['--exit-code', 'origin', 'nosuch']),
                           ('exit-code-hit', ['--exit-code', 'origin', 'main']),
                           ('quiet-named', ['--quiet', 'origin', 'main']), ('url', [url])):
            row(case, *argv)
        h.compare('ls-remote-outside-url-%s' % transport, [(['ls-remote', url, 'main'], outside)], [], [])
        empty_url = h.url(transport, empty)
        for case, argv in (('empty', [empty_url]), ('empty-symref', ['--symref', empty_url]),
                           ('empty-exit-code', ['--exit-code', empty_url])):
            h.compare('ls-remote-%s-%s' % (case, transport), [(['ls-remote', *argv], outside)], [], [])
    h.compare('ls-remote-outside-none', [(['ls-remote'], outside)], [], [])
    for case, target in (('missing-local', str(h.srv / 'missing.git')),
                         ('missing-file', (h.srv / 'missing.git').as_uri()), ('missing-name', 'nosuchremote')):
        h.compare('ls-remote-%s' % case, [(['ls-remote', target], outside)], [], [])


# -- den#70 ------------------------------------------------------------------
def family_fetch(h):
    for transport in h.transports():
        up = work(h, 'fetch-up', 'main')
        h.commit(up, 'f', 'one\n', 'one')
        h.git_out(up, 'branch', 'topic')
        h.git_out(up, 'tag', 'v1')
        h.git_out(up, 'tag', '-a', '-m', 'annotated', 'v2')
        h.commit(up, 'f', 'two\n', 'two')
        h.git_out(up, 'checkout', '-q', 'topic')
        h.commit(up, 't', 't1\n', 't1')
        h.git_out(up, 'checkout', '-q', 'main')
        remote = h.srv / 'fetch.git'
        shutil.rmtree(remote, ignore_errors=True)
        h.git_out(h.srv, 'clone', '-q', '--bare', str(up), str(remote))
        w = h.out / 'fetch-w'
        shutil.rmtree(w, ignore_errors=True)
        h.git_out(h.out, 'clone', '-q', h.url(transport, remote), str(w))
        h.git_out(w, 'checkout', '-q', '-b', 'local')
        # The remote moves on: topic gains a commit and a tag on it.
        h.git_out(up, 'checkout', '-q', 'topic')
        h.commit(up, 't', 't2\n', 't2')
        h.git_out(up, 'checkout', '-q', 'main')
        h.git_out(up, 'tag', 'v3', 'topic')
        h.git_out(up, 'push', '-q', '--force', str(remote), 'topic', 'v3')
        h.url(transport, remote)
        main = h.git_out(w, 'rev-parse', 'main').decode().strip()
        paths = [w]
        pristine = h.snapshot(paths, 'fetch-base')

        def row(case, *argv, prepare=None):
            def setup(tool):
                if prepare:
                    prepare()
            h.compare('fetch-%s-%s' % (case, transport), [(['fetch', *argv], w)], paths, [w], setup, pristine)

        row('full', 'origin', 'refs/heads/topic:refs/scratch/topic')
        row('short-src', 'origin', 'topic:refs/scratch/t2')
        row('short-dst', 'origin', 'topic:newlocal')
        row('no-dst', 'origin', 'topic')
        row('no-dst-tag', 'origin', 'v1')
        row('two', 'origin', 'main', 'topic')
        row('tag-keyword', 'origin', 'tag', 'v3')
        row('tag-same', 'origin', 'refs/tags/v2:refs/tags/v2')
        row('glob', 'origin', 'refs/heads/*:refs/mirror/*')
        row('glob-negative', 'origin', 'refs/heads/*:refs/mirror/*', '^refs/heads/topic')
        row('quiet', '-q', 'origin', 'topic:refs/q/t')
        row('missing-full', 'origin', 'refs/heads/nope:refs/x')
        row('missing-short', 'origin', 'nope')
        row('checked-out', 'origin', 'main:local')

        def seed_behind():
            h.git_out(w, 'update-ref', 'refs/scratch/topic', main)
        row('non-fast-forward', 'origin', 'refs/heads/topic:refs/scratch/topic', prepare=seed_behind)
        row('forced', 'origin', '+refs/heads/topic:refs/scratch/topic', prepare=seed_behind)
        row('force-option', '-f', 'origin', 'refs/heads/topic:refs/scratch/topic', prepare=seed_behind)

        def seed_ahead():
            h.git_out(w, 'update-ref', 'refs/scratch/topic', 'origin/topic~0')
        row('fast-forward', 'origin', 'refs/heads/topic:refs/scratch/topic', prepare=seed_ahead)

        def clobber():
            h.git_out(w, 'tag', '-f', 'v1', main)
        row('tag-clobber', 'origin', 'refs/tags/v1:refs/tags/v1', prepare=clobber)
        row('tag-clobber-forced', 'origin', '+refs/tags/v1:refs/tags/v1', prepare=clobber)
        shutil.rmtree(pristine, ignore_errors=True)


# -- den#63 ------------------------------------------------------------------
def write_long(handle, commits):
    """One small file rewritten a commit, in ten directories: four objects a
    commit, a history that grows without its blobs growing."""
    when = 1700000000
    for c in range(commits):
        message = b'commit %d\n' % c
        handle.write(b'commit refs/heads/main\ncommitter Den Tester <den@example.invalid> %d +0000\ndata %d\n%s'
                     % (when + c, len(message), message))
        data = (b'%d %s\n' % (c, hashlib.sha256(b'%d' % c).hexdigest().encode())) * 4
        name = 'd%d/f%d.txt' % (c % 10, (c // 10) % 10)
        handle.write(('M 100644 inline %s\n' % name).encode() + b'data %d\n' % len(data) + data + b'\n\n')


def write_issue(handle, commits, binaries):
    """den#63's fixture: burrow's tools/measure-den generator (organisation
    code, by value): 200 text files in 10 directories, each commit appending
    2 KiB to four of them, plus incompressible 256 KiB files in the first."""
    def stream():
        n = 0
        while True:
            yield hashlib.sha256(b'burrow-measure-den' + n.to_bytes(8, 'big')).digest()
            n += 1

    def chunk(gen):
        words, total = [], 0
        while total < 2048:
            word = next(gen).hex()[:12]
            words.append(word)
            total += len(word) + 1
        return (' '.join(words) + '\n').encode()

    gen = stream()
    files = {'d%02d/f%02d.txt' % (d, f): chunk(gen) for d in range(10) for f in range(20)}
    blobs = {'bin/b%02d.bin' % i: b''.join(next(gen) for _ in range(256 * 1024 // 32)) for i in range(binaries)}
    names = sorted(files)
    for c in range(commits):
        changed = {}
        if c == 0:
            changed.update(files)
            changed.update(blobs)
        else:
            for k in range(4):
                name = names[(c * 7 + k * 53) % len(names)]
                files[name] = files[name] + chunk(gen)
                changed[name] = files[name]
        message = b'commit %d\n' % c
        handle.write(b'commit refs/heads/main\ncommitter Den Tester <den@example.invalid> %d +0000\ndata %d\n%s'
                     % (1700000000 + c * 60, len(message), message))
        for name in sorted(changed):
            handle.write(('M 100644 inline %s\n' % name).encode() + b'data %d\n' % len(changed[name]) +
                         changed[name] + b'\n')
        handle.write(b'\n')


# tests/vc24-prediction.txt P6 d: 64 MiB plus 1.5 KiB an object with a
# checkout, 1 KiB an object bare; address space the bound plus 128 MiB.
def memory_bound(objects, bare_clone):
    return 64 * MIB + objects * (1024 if bare_clone else 1536)


def family_memory(h):
    floor = launched(h, [h.den, '--version'], 1 << 30)['maxrss_kib']
    for name, writer in (('long-20000', lambda f: write_long(f, 20000)),
                         ('issue-300-40', lambda f: write_issue(f, 300, 40))):
        repo = h.srv / (name + '.git')
        shutil.rmtree(repo, ignore_errors=True)
        h.git_out(h.srv, 'init', '-q', '--bare', '-b', 'main', str(repo))
        stream = h.out / 'stream'
        with open(stream, 'wb') as handle:
            writer(handle)
        with open(stream, 'rb') as handle:
            result = subprocess.run([h.git, '--git-dir', str(repo), 'fast-import', '--quiet'], stdin=handle,
                                    env=h.env, capture_output=True, timeout=1200)
        assert result.returncode == 0, 'fixture fast-import'
        stream.unlink()
        h.git_out(repo, '-c', 'pack.threads=2', 'repack', '-a', '-d', '-q')
        counts = dict(line.split(': ') for line in h.git_out(repo, 'count-objects', '-v').decode().splitlines())
        objects = int(counts['in-pack'])
        for bare_clone in (False, True):
            label = 'memory-%s%s' % (name, '-bare' if bare_clone else '')
            bound = memory_bound(objects, bare_clone)
            flags = ['--bare'] if bare_clone else []
            ours, theirs = h.out / 'mem-den', h.out / 'mem-git'
            for path in (ours, theirs):
                shutil.rmtree(path, ignore_errors=True)
            measured = launched(h, ['prlimit', '--as=%d' % (bound + 128 * MIB), '--', h.den, 'clone', '-q', *flags,
                                    repo.as_uri(), str(ours)], 1 << 40)
            problems = []
            if measured['exit'] != 0:
                problems.append('den clone under a %d-byte address-space cap: exit %d %r' % (
                    bound + 128 * MIB, measured['exit'], measured['stderr'][-200:]))
            if measured['maxrss_kib'] * 1024 > bound:
                problems.append('peak RSS %d KiB over the bound %d KiB' % (measured['maxrss_kib'], bound // 1024))
            h.git_out(h.out, 'clone', '-q', *flags, repo.as_uri(), str(theirs))
            if measured['exit'] == 0:
                try:
                    h.git_out(ours, 'fsck', '--full', '--no-reflogs')
                    a, b = h.state(theirs), h.state(ours)
                    keys = [key for key in a if a[key] != b.get(key)]
                    if keys:
                        problems.append('clone differs from the pinned Git\'s: ' + ', '.join(keys))
                except AssertionError as exc:
                    problems.append(str(exc))
            h.verdict(label, problems, dict(objects=objects, bound_kib=bound // 1024, floor_kib=floor, **measured))
            print('MEMORY %s %s' % (label, json.dumps(dict(objects=objects, bound_kib=bound // 1024, floor_kib=floor,
                                                            **{k: v for k, v in measured.items() if k != 'stderr'}))),
                  flush=True)
            for path in (ours, theirs):
                shutil.rmtree(path, ignore_errors=True)
        shutil.rmtree(repo, ignore_errors=True)


# -- den#63, a clone's CPU ----------------------------------------------------
# pelt (https://github.com/wolffe-lang/pelt) at trunk PELT_TRUNK: 12,038
# objects, 9,685 files. The fixture is a bundle of that trunk, pinned by its
# digest, from DEN_PELT_BUNDLE or the archive directory; without one, the
# pinned Git fetches that commit from github.com. Either way the served
# repository is repacked by the pinned Git on one thread, so both clients
# receive the same pack on every host.
PELT_URL = 'https://github.com/wolffe-lang/pelt.git'
PELT_BUNDLE = 'pelt-b80d657.bundle'
PELT_SHA256 = '11f95d10a5ea987fcd466726d2a9e43aaaaba5162fcee0c2f6a356fed7484c3e'
PELT_TRUNK = 'b80d6570a4611d7977e4cf489c192849b32a6a7f'
PELT_OBJECTS = 12038
PELT_FILES = 9685
# tests/vc24-prediction.txt P10: den's clone CPU (user plus system, its own
# and its children's) at most this many times the pinned Git's, the minimum
# of COST_RUNS runs each, run in turn.
COST_RATIO = 10
COST_RUNS = 3


def pelt_fixture(h, repo):
    """The served pelt repository at repo, or the reason there is none."""
    shutil.rmtree(repo, ignore_errors=True)
    named = os.environ.get('DEN_PELT_BUNDLE') or os.path.join(os.environ.get('DEN_ARCHIVE_DIR', ''), PELT_BUNDLE)
    bundle = Path(named)
    if bundle.is_file():
        if hashlib.sha256(bundle.read_bytes()).hexdigest() != PELT_SHA256:
            return 'fixture %s digest differs from the pinned one' % bundle
        h.git_out(h.srv, 'clone', '-q', '--bare', str(bundle), str(repo))
    else:
        h.git_out(h.srv, 'init', '-q', '--bare', '-b', 'trunk', str(repo))
        fetched = subprocess.run([h.git, '-C', str(repo), 'fetch', '-q', PELT_URL, PELT_TRUNK + ':refs/heads/trunk'],
                                 env=h.env, capture_output=True, timeout=600)
        if fetched.returncode:
            return 'no %s (sha256 %s) in DEN_PELT_BUNDLE or DEN_ARCHIVE_DIR, and fetching %s failed: %s' % (
                PELT_BUNDLE, PELT_SHA256, PELT_URL, fetched.stderr.decode(errors='replace').strip()[-200:])
    for key, value in (('gc.auto', '0'), ('maintenance.auto', 'false'), ('repack.writeBitmaps', 'false')):
        h.git_out(repo, 'config', key, value)
    h.git_out(repo, '-c', 'pack.threads=1', 'repack', '-a', '-d', '-f', '-q')
    trunk = h.git_out(repo, 'rev-parse', 'refs/heads/trunk').decode().strip()
    objects = len(h.git_out(repo, 'rev-list', '--objects', '--all').splitlines())
    files = len(h.git_out(repo, 'ls-tree', '-r', '--name-only', 'refs/heads/trunk').splitlines())
    if (trunk, objects, files) != (PELT_TRUNK, PELT_OBJECTS, PELT_FILES):
        return 'fixture shape: trunk %s, %d objects, %d files' % (trunk, objects, files)
    return None


def family_cost(h):
    name = 'clone-cost-pelt'
    repo = h.srv / 'pelt.git'
    problem = pelt_fixture(h, repo)
    if problem:
        h.verdict(name, [problem])
        return
    url = h.url('git', repo)
    ours, theirs = h.out / 'cost-den', h.out / 'cost-git'
    runs = dict(git=[], den=[])
    problems = []
    for turn in range(COST_RUNS):
        for tool, path in (('git', theirs), ('den', ours)):
            shutil.rmtree(path, ignore_errors=True)
            binary = h.git if tool == 'git' else h.den
            measured = launched(h, [binary, 'clone', '-q', url, str(path)], 1 << 40)
            runs[tool].append({k: v for k, v in measured.items() if k != 'stderr'})
            if measured['exit'] != 0:
                problems.append('%s clone run %d: exit %d %r' % (tool, turn, measured['exit'], measured['stderr']))
            if turn < COST_RUNS - 1:
                shutil.rmtree(path, ignore_errors=True)
    if not problems:
        a, b = h.state(theirs), h.state(ours)
        keys = [key for key in a if a[key] != b.get(key)]
        if keys:
            problems.append('clone differs from the pinned Git\'s: ' + ', '.join(keys))
    git_cpu = min(run['cpu'] for run in runs['git'])
    den_cpu = min(run['cpu'] for run in runs['den'])
    ratio = round(den_cpu / git_cpu, 1) if git_cpu > 0 else None
    if ratio is None or ratio > COST_RATIO:
        problems.append('den clone CPU %.2f s is %s times the pinned Git\'s %.2f s, over %d' % (
            den_cpu, ratio, git_cpu, COST_RATIO))
    detail = dict(objects=PELT_OBJECTS, files=PELT_FILES, git_cpu=git_cpu, den_cpu=den_cpu, ratio=ratio,
                  ratio_cap=COST_RATIO, runs=runs)
    h.verdict(name, problems, detail)
    print('COST %s %s' % (name, json.dumps(detail)), flush=True)
    for path in (ours, theirs, repo):
        shutil.rmtree(path, ignore_errors=True)


def launched(h, argv, cap):
    result = subprocess.run([sys.executable, '-I', '-S', '-c', LAUNCH, *map(str, argv)], env=h.env,
                            capture_output=True, stdin=subprocess.DEVNULL, timeout=1800)
    row = json.loads(result.stdout.decode().strip().splitlines()[-1])
    row['stderr'] = result.stderr[-300:].decode(errors='replace')
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    parser.add_argument('--family', default=','.join(DEFAULT_FAMILIES))
    parser.add_argument('--field', action='store_true', help='a Git other than the pinned one (macOS field leg)')
    args = parser.parse_args()
    families = args.family.split(',')
    assert families and set(families) <= set(FAMILIES), 'families'
    if args.field and 'memory' in families:
        raise SystemExit('FAIL wire-gaps-field: the memory rows need prlimit and the Linux container')
    if 'cost' in families and (families != ['cost'] or args.tier != 'release'):
        raise SystemExit('FAIL clone-cost-alone: the cost row runs by itself on the release tier')
    h = Harness(args)
    try:
        h.start_daemon()
        for family in families:
            {'push': family_push, 'clone': family_clone, 'ls-remote': family_ls_remote,
             'fetch': family_fetch, 'memory': family_memory, 'cost': family_cost}[family](h)
            h.stop_https()
    finally:
        h.stop()
    h.no_private_keys()
    left = ' (https and memory not run: field leg)' if args.field else ''
    if h.failed:
        raise SystemExit('FAIL wire-gaps: %d of %d rows: %s' % (len(h.failed), len(h.failed) + h.passed,
                                                                ', '.join(h.failed)))
    print('wire-gaps: %s %s; %d rows; zero skips%s' % (args.tier, ','.join(families), h.passed, left), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit('FAIL wire-gaps-harness: ' + str(exc))
