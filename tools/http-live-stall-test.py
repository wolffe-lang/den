#!/usr/bin/env python3
"""http-live-stall: the live clone rows against a remote that stops sending.

A local plain-HTTP server answers through the pinned git-http-backend, as
tools/http-git-test.py's gateway does, one thread per connection. On cue it
sends a fetch response's headers and half its body, then nothing, and holds
the connection open until the client closes it. tools/http-live-test.py's
self row runs against it with its stall bound at STALL seconds
(DEN_LIVE_STALL_SECONDS) and each clone's own bound at LIMIT seconds
(--self-seconds), in three scenarios:

  http-live-stall-none   nothing stalls: PASS http-live-self, no RETRY
                         line, no retry counted in the LIVE line.
  http-live-stall-once   each client's first fetch stalls: one RETRY line
                         per tool, PASS http-live-self, one retry each in
                         the LIVE line.
  http-live-stall-twice  each client's first two fetches stall: one RETRY
                         line per tool, then FAIL http-live-self with the
                         remote sent nothing for STALL s twice, for both.

and two in which the served repository's refs move mid-row, right after the
server has sent den's first fetch response (den clones first):

  http-live-stall-moved-branch  a branch no clone checks out appears
                         (refs/heads/unrelated, on a new commit): PASS
                         http-live-self, no RETRY line, and the row says it
                         left that ref out (a NARROWED line and the LIVE
                         line's excluded list).
  http-live-stall-moved-head  the default branch gains a commit: one RETRY
                         line naming HEAD and refs/heads/main, then PASS
                         http-live-self with nothing excluded.

The served repository is put back after each of these. Three more aim at
the host going away, as a network outage takes it: right after the server
sends the first fetch response (den's, since den clones first) it stops
listening, so each later connection is refused. The live row waits
PAUSE seconds (DEN_LIVE_UNREACHABLE_PAUSE) before it reruns:

  http-live-stall-unreachable-once  the server listens again BACK seconds
                         after it stopped, within the pause: one RETRY line
                         naming the pinned Git's reads that could not reach
                         it (its clone and the listing after), then PASS
                         http-live-self, one unreachable retry in the LIVE
                         line.
  http-live-stall-unreachable-twice  the server never listens again: the
                         same RETRY line, then FAIL http-live-self naming
                         the second attempt's failed reads, and no third.
  http-live-stall-den-refused  the server closes den's fetch without an
                         answer and serves Git's: den's clone fails while
                         every read of the pinned Git succeeds, so no
                         RETRY line, and FAIL http-live-self on the
                         process difference.

A client is told apart by its User-Agent header (den sends none). Each
scenario must reach its verdict within BOUND seconds; the row stops its own
child, the live row's process, at that bound. Loopback only, no github.com.
The live row needs a distribution root bundle, as on the network; without
one every row here SKIPs by name. Run through tools/env with the pinned Git.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import socket
import subprocess
import sys
import threading
import time

R = Path(__file__).resolve().parent.parent
GIT_SHA256 = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
STALL = 3
LIMIT = 60
BOUND = 240
HOLD = 200
BACK = 2
PAUSE = 4
SCENARIOS = (('none', 0, None, None), ('once', 1, None, None), ('twice', 2, None, None),
             ('moved-branch', 0, 'branch', None), ('moved-head', 0, 'head', None),
             ('unreachable-once', 0, None, 'once'), ('unreachable-twice', 0, None, 'twice'),
             ('den-refused', 0, None, 'den'))

http_git = runpy.run_path(str(R / 'tools/http-git-test.py'), run_name='http_git')
Server, Reader, Stopped = http_git['Server'], http_git['Reader'], http_git['Stopped']


class StallServer(Server):
    """The plain gateway with a thread per connection, stalling each client's
    first `stalls` fetch responses halfway through their bodies. With an
    outage, 'once' or 'twice', it stops listening right after it sends the
    first fetch response, and listens again BACK s later ('once') or never
    ('twice'); with 'den', it closes den's fetch requests unanswered."""

    def __init__(self, root, git, env, stalls, mover=None, outage=None):
        self.stalls = stalls
        self.outage = outage
        self.went_down = None
        self.refused_den = 0
        # mover() moves the served refs once, right after den's first fetch
        # response has been sent (den sends no User-Agent).
        self.mover = mover
        self.moved = False
        self.fetches = {}
        self.stalled = []
        self.guard = threading.Lock()
        self.workers = []
        super().__init__(root, git, env, 'plain', None, '', lambda data: None)

    def plain_loop(self):
        while not self.stop.is_set():
            try:
                peer, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                # An outage shuts the listener (accept fails at once); anything else ends the loop.
                if self.went_down is None or self.outage != 'once':
                    break
                if self.stop.wait(max(0.0, self.went_down + BACK - time.monotonic())):
                    break
                try:
                    self.listener.close()
                except OSError:
                    pass
                listener = socket.socket()
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind(('127.0.0.1', self.port))
                listener.listen(8)
                listener.settimeout(0.2)
                self.listener = listener
                continue
            worker = threading.Thread(target=self.serve, args=(peer,), name='http-live-stall-peer', daemon=True)
            self.workers.append(worker)
            worker.start()

    def serve(self, peer):
        with peer:
            reader = Reader(peer, self.stop)
            try:
                request = self.request(reader)
                method, _, headers, body = request
                reply = self.response(request)
                agent = headers.get(b'user-agent', b'').decode('ascii', 'replace') or '(none)'
                stall = False
                fetch = method == 'POST' and b'want ' in body
                if fetch:
                    with self.guard:
                        count = self.fetches[agent] = self.fetches.get(agent, 0) + 1
                    stall = count <= self.stalls
                if fetch and self.outage == 'den' and agent == '(none)':
                    with self.guard:
                        self.refused_den += 1
                    return
                if not stall:
                    peer.sendall(reply)
                    if fetch and self.outage in ('once', 'twice'):
                        with self.guard:
                            first = self.went_down is None
                            if first:
                                self.went_down = time.monotonic()
                        if first:
                            # Stop listening now, before any client can connect again: a
                            # connection is refused from here on, as when the host is gone.
                            try:
                                self.listener.shutdown(socket.SHUT_RDWR)
                            except OSError:
                                pass
                            self.listener.close()
                    if fetch and agent == '(none)' and self.mover is not None:
                        with self.guard:
                            first, self.moved = not self.moved, True
                        if first:
                            self.mover()
                    return
                head, _, content = reply.partition(b'\r\n\r\n')
                peer.sendall(head + b'\r\n\r\n' + content[:len(content) // 2])
                self.hold(peer, agent, len(content) // 2, len(content))
            except (EOFError, Stopped):
                pass
            except Exception as exc:
                if not self.stop.is_set():
                    self.errors.append(type(exc).__name__ + ': ' + str(exc))
            finally:
                reader.close()

    def hold(self, peer, agent, sent, size):
        """Send nothing more; note when the client closes the connection."""
        started = time.monotonic()
        released = None
        peer.settimeout(0.2)
        while not self.stop.is_set() and time.monotonic() - started < HOLD:
            try:
                data = peer.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                data = b''
            if not data:
                released = round(time.monotonic() - started, 1)
                break
        with self.guard:
            self.stalled.append(dict(agent=agent, sent=sent, of=size, released_after=released))

    def close(self):
        super().close()
        for worker in self.workers:
            worker.join(timeout=5)


def fixture(srv, git, env):
    """A bare repository of two commits, one carrying 2 MiB of bytes that do
    not compress, so half a fetch response stops mid-pack."""
    work = srv / 'work'

    def g(*argv, cwd=work):
        q = subprocess.run([git, *argv], cwd=cwd, env=env, capture_output=True, timeout=120)
        assert q.returncode == 0, (argv, q.stderr.decode(errors='replace')[-300:])

    g('init', '-q', '-b', 'main', str(work), cwd=srv)
    for key, value in (('gc.auto', '0'), ('maintenance.auto', 'false')):
        g('config', key, value)
    (work / 'README').write_text('stall fixture\n')
    (work / 'blob.bin').write_bytes(b''.join(hashlib.sha256(b'%d' % i).digest() for i in range(65536)))
    g('add', 'README', 'blob.bin')
    g('commit', '-q', '-m', 'one')
    (work / 'two.txt').write_text('two\n')
    g('add', 'two.txt')
    g('commit', '-q', '-m', 'two')
    g('clone', '-q', '--bare', str(work), str(srv / 'remote.git'), cwd=srv)
    for key, value in (('gc.auto', '0'), ('maintenance.auto', 'false')):
        g('config', key, value, cwd=srv / 'remote.git')
    shutil.rmtree(work)


def mover(kind, srv, git, env):
    """What moves the served refs mid-row: a new branch on a new commit
    ('branch'), or a new commit on the default branch ('head')."""
    remote = srv / 'remote.git'
    who = dict(GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
               GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid')

    def g(*argv):
        q = subprocess.run([git, '--git-dir', str(remote), *argv], env={**env, **who}, capture_output=True, timeout=60)
        assert q.returncode == 0, (argv, q.stderr.decode(errors='replace')[-300:])
        return q.stdout.decode().strip()

    def move():
        main = g('rev-parse', 'refs/heads/main')
        commit = g('commit-tree', g('rev-parse', 'refs/heads/main^{tree}'), '-p', main, '-m', 'moved mid-row: ' + kind)
        if kind == 'branch':
            g('update-ref', 'refs/heads/unrelated', commit)
        else:
            g('update-ref', 'refs/heads/main', commit, main)

    def restore(main):
        g('update-ref', 'refs/heads/main', main)
        present = subprocess.run([git, '--git-dir', str(remote), 'show-ref', '--verify', '--quiet',
                                  'refs/heads/unrelated'], env=env, timeout=60).returncode == 0
        if present:
            g('update-ref', '-d', 'refs/heads/unrelated')

    return move, restore, lambda: g('rev-parse', 'refs/heads/main')


def scenario(label, stalls, move, outage, tier, srv, git, env):
    name = 'http-live-stall-' + label
    out = R / 'target/runs' / ('http-live-stall-%s-%s' % (tier, label))
    if out.exists():
        shutil.rmtree(out)
    moving, restore, tip = mover(move, srv, git, env) if move else (None, None, None)
    main = tip() if move else None
    server = StallServer(srv, git, env, stalls, moving, outage)
    argv = [sys.executable, '-I', str(R / 'tools/http-live-test.py'), '--tier', tier, '--rows', 'self',
            '--self-url', server.url, '--self-seconds', str(LIMIT), '--output', str(out)]
    started = time.monotonic()
    bounded = True
    try:
        child = subprocess.Popen(argv, env={**env, 'DEN_LIVE_STALL_SECONDS': str(STALL),
                                            'DEN_LIVE_UNREACHABLE_PAUSE': str(PAUSE)},
                                 stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            output, _ = child.communicate(timeout=BOUND)
        except subprocess.TimeoutExpired:
            bounded = False
            child.kill()  # This row's own child only.
            output, _ = child.communicate()
    finally:
        server.close()
        if move:
            restore(main)
    elapsed = round(time.monotonic() - started, 1)
    lines = output.decode('utf-8', 'replace').splitlines()
    for line in lines:
        print('live| ' + line, flush=True)
    retries = [line for line in lines if line.startswith('RETRY ')]
    verdicts = [line for line in lines if line.startswith(('PASS http-live-self', 'FAIL http-live-self'))]
    live = [json.loads(line.split(' ', 2)[2]) for line in lines if line.startswith('LIVE http-live-self ')]
    want_retries = ['RETRY http-live-self %s no-progress-for=%ds' % (tool, STALL) for tool in ('den', 'git')] \
        if stalls else []
    if move == 'head':
        want_retries = ['RETRY http-live-self moved=HEAD,refs/heads/main']
    if outage in ('once', 'twice'):
        # The server stops right after den's fetch: Git's clone and the listing after it are refused.
        want_retries = ['RETRY http-live-self unreachable=git,ls-remote-after']
    narrowed = [line for line in lines if line.startswith('NARROWED ')]
    want_narrowed = ['NARROWED http-live-self excluded=refs/heads/unrelated'] if move == 'branch' else []
    # A row from before the narrowing prints neither field: nothing excluded, no move retried.
    excluded = live[0].get('excluded', []) if len(live) == 1 else None
    want_excluded = ['refs/heads/unrelated'] if move == 'branch' else []
    moved_retries = live[0].get('moved_retries', 0) if len(live) == 1 else None
    unreachable_retries = live[0].get('unreachable_retries', 0) if len(live) == 1 else None
    if outage == 'twice':
        want_verdicts = ['FAIL http-live-self pinned Git could not reach den\'s repository twice: '
                         'ls-remote-before,git,ls-remote-after']
    elif outage == 'den':
        # Only the verdict's start: den's own words for a closed connection follow it.
        want_verdicts = [verdict for verdict in verdicts
                         if verdict.startswith('FAIL http-live-self process exit differs: den exit ')] or \
            ['FAIL http-live-self process exit differs: den exit ...']
    elif stalls < 2:
        want_verdicts = ['PASS http-live-self']
    else:
        want_verdicts = ['FAIL http-live-self ' + '; '.join(
            '%s: the remote sent nothing for %d s twice' % (tool, STALL) for tool in ('den', 'git'))]
    passes = stalls < 2 and outage not in ('twice', 'den')
    counts = (live[0].get('den_retries'), live[0].get('git_retries')) if len(live) == 1 else None
    problems = []
    if not bounded:
        problems.append('the live row was still running after %d s' % BOUND)
    if retries != want_retries:
        problems.append('RETRY lines %r, not %r' % (retries, want_retries))
    if verdicts != want_verdicts:
        problems.append('verdict %r, not %r' % (verdicts, want_verdicts))
    if (child.returncode == 0) != passes:
        problems.append('the live row exited %d' % child.returncode)
    if counts != (min(stalls, 1), min(stalls, 1)):
        problems.append('LIVE retries den,git %r, not %r' % (counts, (min(stalls, 1), min(stalls, 1))))
    if narrowed != want_narrowed:
        problems.append('NARROWED lines %r, not %r' % (narrowed, want_narrowed))
    if excluded != want_excluded:
        problems.append('LIVE excluded %r, not %r' % (excluded, want_excluded))
    if moved_retries != (1 if move == 'head' else 0):
        problems.append('LIVE moved_retries %r, not %r' % (moved_retries, 1 if move == 'head' else 0))
    if unreachable_retries != (1 if outage in ('once', 'twice') else 0):
        problems.append('LIVE unreachable_retries %r, not %r' % (unreachable_retries,
                                                                1 if outage in ('once', 'twice') else 0))
    if (outage in ('once', 'twice')) != (server.went_down is not None):
        problems.append('the server %s' % ('never stopped listening' if outage else 'stopped listening unasked'))
    if (outage == 'den') != (server.refused_den > 0):
        problems.append('the server %s' % ('never closed den\'s fetch' if outage == 'den' else 'closed den\'s fetch'))
    if bool(move) != server.moved:
        problems.append('the served refs %s' % ('never moved' if move else 'moved unasked'))
    if len(server.stalled) != 2 * stalls:
        problems.append('the server stalled %d fetches, not %d' % (len(server.stalled), 2 * stalls))
    if server.errors:
        problems.append('server: ' + '; '.join(server.errors[:3]))
    print('STALL %s %s' % (name, json.dumps(dict(elapsed=elapsed, exit=child.returncode, fetches=server.fetches,
                                                  stalled=server.stalled, refused_den=server.refused_den,
                                                  went_down=server.went_down is not None), sort_keys=True)),
          flush=True)
    print(('PASS ' if not problems else 'FAIL ') + name + ('' if not problems else ' ' + '; '.join(problems)),
          flush=True)
    return not problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    args = parser.parse_args()
    git = str(Path(os.environ['DEN_GIT']).resolve())
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == GIT_SHA256, 'pinned Git digest'
    if not (R / 'target' / args.tier / 'den').is_file():
        raise SystemExit('FAIL http-live-stall-input: build target/' + args.tier + '/den first')
    if not Path(os.environ.get('DEN_LIVE_ROOTS_PEM', '/etc/ssl/certs/ca-certificates.crt')).is_file():
        for label, _, _, _ in SCENARIOS:
            print('SKIP http-live-stall-%s reason=no distribution root bundle (the live row needs one)' % label,
                  flush=True)
        return
    srv = R / 'target/live' / ('http-live-stall-' + args.tier)
    if srv.exists():
        shutil.rmtree(srv)
    srv.mkdir(parents=True)
    env = dict(os.environ)
    fixture(srv, git, env)
    failed = [label for label, stalls, move, outage in SCENARIOS
              if not scenario(label, stalls, move, outage, args.tier, srv, git, env)]
    shutil.rmtree(srv)
    if failed:
        raise SystemExit('FAIL http-live-stall: ' + ', '.join(failed))
    print('http-live-stall: %s %s; zero skips' % (args.tier, ','.join(label for label, _, _, _ in SCENARIOS)),
          flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        raise SystemExit('FAIL http-live-stall-harness: ' + str(exc))
