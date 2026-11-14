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
SCENARIOS = (('none', 0), ('once', 1), ('twice', 2))

http_git = runpy.run_path(str(R / 'tools/http-git-test.py'), run_name='http_git')
Server, Reader, Stopped = http_git['Server'], http_git['Reader'], http_git['Stopped']


class StallServer(Server):
    """The plain gateway with a thread per connection, stalling each client's
    first `stalls` fetch responses halfway through their bodies."""

    def __init__(self, root, git, env, stalls):
        self.stalls = stalls
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
                break
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
                if method == 'POST' and b'want ' in body:
                    with self.guard:
                        count = self.fetches[agent] = self.fetches.get(agent, 0) + 1
                    stall = count <= self.stalls
                if not stall:
                    peer.sendall(reply)
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


def scenario(label, stalls, tier, srv, git, env):
    name = 'http-live-stall-' + label
    out = R / 'target/runs' / ('http-live-stall-%s-%s' % (tier, label))
    if out.exists():
        shutil.rmtree(out)
    server = StallServer(srv, git, env, stalls)
    argv = [sys.executable, '-I', str(R / 'tools/http-live-test.py'), '--tier', tier, '--rows', 'self',
            '--self-url', server.url, '--self-seconds', str(LIMIT), '--output', str(out)]
    started = time.monotonic()
    bounded = True
    try:
        child = subprocess.Popen(argv, env={**env, 'DEN_LIVE_STALL_SECONDS': str(STALL)}, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            output, _ = child.communicate(timeout=BOUND)
        except subprocess.TimeoutExpired:
            bounded = False
            child.kill()  # This row's own child only.
            output, _ = child.communicate()
    finally:
        server.close()
    elapsed = round(time.monotonic() - started, 1)
    lines = output.decode('utf-8', 'replace').splitlines()
    for line in lines:
        print('live| ' + line, flush=True)
    retries = [line for line in lines if line.startswith('RETRY ')]
    verdicts = [line for line in lines if line.startswith(('PASS http-live-self', 'FAIL http-live-self'))]
    live = [json.loads(line.split(' ', 2)[2]) for line in lines if line.startswith('LIVE http-live-self ')]
    want_retries = ['RETRY http-live-self %s no-progress-for=%ds' % (tool, STALL) for tool in ('den', 'git')] \
        if stalls else []
    if stalls < 2:
        want_verdicts = ['PASS http-live-self']
    else:
        want_verdicts = ['FAIL http-live-self ' + '; '.join(
            '%s: the remote sent nothing for %d s twice' % (tool, STALL) for tool in ('den', 'git'))]
    counts = (live[0].get('den_retries'), live[0].get('git_retries')) if len(live) == 1 else None
    problems = []
    if not bounded:
        problems.append('the live row was still running after %d s' % BOUND)
    if retries != want_retries:
        problems.append('RETRY lines %r, not %r' % (retries, want_retries))
    if verdicts != want_verdicts:
        problems.append('verdict %r, not %r' % (verdicts, want_verdicts))
    if (child.returncode == 0) != (stalls < 2):
        problems.append('the live row exited %d' % child.returncode)
    if counts != (min(stalls, 1), min(stalls, 1)):
        problems.append('LIVE retries den,git %r, not %r' % (counts, (min(stalls, 1), min(stalls, 1))))
    if len(server.stalled) != 2 * stalls:
        problems.append('the server stalled %d fetches, not %d' % (len(server.stalled), 2 * stalls))
    if server.errors:
        problems.append('server: ' + '; '.join(server.errors[:3]))
    print('STALL %s %s' % (name, json.dumps(dict(elapsed=elapsed, exit=child.returncode, fetches=server.fetches,
                                                  stalled=server.stalled), sort_keys=True)), flush=True)
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
        for label, _ in SCENARIOS:
            print('SKIP http-live-stall-%s reason=no distribution root bundle (the live row needs one)' % label,
                  flush=True)
        return
    srv = R / 'target/live' / ('http-live-stall-' + args.tier)
    if srv.exists():
        shutil.rmtree(srv)
    srv.mkdir(parents=True)
    env = dict(os.environ)
    fixture(srv, git, env)
    failed = [label for label, stalls in SCENARIOS if not scenario(label, stalls, args.tier, srv, git, env)]
    shutil.rmtree(srv)
    if failed:
        raise SystemExit('FAIL http-live-stall: ' + ', '.join(failed))
    print('http-live-stall: %s none,once,twice; zero skips' % args.tier, flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        raise SystemExit('FAIL http-live-stall-harness: ' + str(exc))
