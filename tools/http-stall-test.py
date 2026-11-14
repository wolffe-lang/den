#!/usr/bin/env python3
"""den#118: fetches from a remote that stalls mid-pack, over plain HTTP and TLS.

The remote is the stall server of the http-live-stall rows (vc32's, on the
gate-hardening branch), carried here and given the gateway's TLS mode: the
tools/http-git-test.py gateway answers every request through the pinned
git-http-backend, and on a fetch it sends the response's headers and its body
up to the pkt-line boundary nearest half (or, for before-pack, up to the end
of the packfile section's first line, before any pack data), then by cue:

  silent     nothing more;
  keepalive  an empty band-1 packet every second (the keepalive git-config(1)
             documents for uploadpack.keepAlive);
  progress   a band-2 progress packet every second.

TLS runs through the gateway's TLS mode: the pinned OpenSSL s_server is the
terminator, with the gateway's own disposable fixture PKI.

Rows (each runs den; the pinned Git has no stall bound and waits until it is
stopped, so it is run only where it finishes: the control):
  http-stall-<transport>-none          no stall: den's clone ends as Git's
                                       does (exit, refs, HEAD).
  http-stall-<transport>-<cue>         DEN_STALL_SECONDS=5: den ends between 5
                                       and 30 s, exit 128, with the named line
                                       last; no destination directory is left.
  http-stall-tls-before-pack           keepalives before any pack data,
                                       DEN_STALL_SECONDS=5: den waits four
                                       times the bound (20 s) before it ends.
  http-stall-tls-keepalive-default     DEN_STALL_SECONDS unset: den ends
                                       between 30 and 60 s with the 30-second
                                       line.
  http-stall-submodule-tls-keepalive   submodule update --init against the
                                       stalling remote, DEN_STALL_SECONDS=5:
                                       both clone attempts end with the named
                                       line, the update aborts (exit 1), and
                                       no module git directory is left.
A den run still going at 90 s is stopped by the row (its own child only), and
the row fails. Loopback only. Run through tools/env with the pinned Git.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import signal
import subprocess
import sys
import threading
import time

R = Path(__file__).resolve().parent.parent
GIT_SHA256 = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
BOUND = 5
STOP = 90
http_git = runpy.run_path(str(R / 'tools/http-git-test.py'), run_name='http_git')
Server, Reader, Stopped = http_git['Server'], http_git['Reader'], http_git['Stopped']
OPENSSL_PINS = http_git['OPENSSL_PINS']
BEATS = {'keepalive': b'0005\x01', 'progress': b'0016\x02Counting objects\r'}
LINE = {
    'silent': 'fatal: the remote sent nothing for DEN_STALL_SECONDS seconds',
    'keepalive': 'fatal: the remote sent no pack data within DEN_STALL_SECONDS',
    'progress': 'fatal: the remote sent no pack data within DEN_STALL_SECONDS',
    'before-pack': 'fatal: the remote sent no pack data within DEN_STALL_SECONDS',
    'default': 'fatal: the remote sent no pack data for 30 seconds',
}


def cut_point(content, cue):
    """The pkt-line boundary a stalled response stops at."""
    pos = 0
    first = True
    while pos < len(content):
        size = int(content[pos:pos + 4], 16)
        size = 4 if size < 4 else size
        if cue == 'before-pack' and first:
            return pos + size
        if cue != 'before-pack' and pos >= len(content) // 2:
            return pos
        pos += size
        first = False
    return pos


class StallGateway(Server):
    """The gateway, a fetch response cut and held by cue until the row stops it."""

    def __init__(self, root, git, env, mode, pki, cue):
        self.cue = cue
        self.stalled = []
        super().__init__(root, git, env, mode, pki, '', lambda data: None)

    def stall(self, send, reply):
        head, _, content = reply.partition(b'\r\n\r\n')
        cut = cut_point(content, self.cue)
        send(head + b'\r\n\r\n' + content[:cut])
        beat = BEATS.get('keepalive' if self.cue == 'before-pack' else self.cue)
        beats, budget = 0, len(content) - cut
        started = time.monotonic()
        while not self.stop.is_set() and time.monotonic() - started < STOP + 30:
            time.sleep(1.0 if beat else 0.2)
            if beat and not self.stop.is_set() and (beats + 1) * len(beat) <= budget:
                try:
                    send(beat)
                except OSError:
                    break
                beats += 1
        self.stalled.append(dict(sent=cut, of=len(content), beats=beats))

    def fetch(self, request):
        method, _, _, body = request
        return method == 'POST' and b'command=fetch' in body and self.cue != 'none'

    def plain_loop(self):
        try:
            while not self.stop.is_set():
                try:
                    peer, _ = self.listener.accept()
                except OSError:
                    continue
                with peer:
                    reader = Reader(peer, self.stop)
                    try:
                        request = self.request(reader)
                        reply = self.response(request)
                        if self.fetch(request):
                            self.stall(peer.sendall, reply)
                        else:
                            peer.sendall(reply)
                    except EOFError:
                        pass
                    finally:
                        reader.close()
        except (Stopped, OSError) as exc:
            if not self.stop.is_set():
                self.errors.append(type(exc).__name__)
        except Exception as exc:
            self.errors.append(type(exc).__name__ + ': ' + str(exc))

    def tls_loop(self):
        reader = Reader(self.process.stdout, self.stop)

        def send(data):
            self.process.stdin.write(data)
            self.process.stdin.flush()
        try:
            while not self.stop.is_set():
                request = self.request(reader)
                reply = self.response(request)
                if self.fetch(request):
                    self.stall(send, reply)
                else:
                    send(reply)
        except Stopped:
            pass
        except Exception as exc:
            if not self.stop.is_set():
                self.errors.append(type(exc).__name__ + ': ' + str(exc))
        finally:
            reader.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    args = parser.parse_args()
    git = str(Path(os.environ['DEN_GIT']).resolve())
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == GIT_SHA256, 'pinned Git digest'
    den = R / 'target' / args.tier / 'den'
    if not den.is_file():
        raise SystemExit('FAIL http-stall-input: build target/' + args.tier + '/den first')
    out = R / 'target/runs' / ('http-stall-' + args.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    env = dict(os.environ)
    env.pop('DEN_STALL_SECONDS', None)

    def run(argv, cwd=None):
        q = subprocess.run([str(a) for a in argv], cwd=cwd, env=env, capture_output=True, timeout=120)
        assert q.returncode == 0, (argv, q.stderr.decode(errors='replace')[-300:])
        return q.stdout.decode().strip()

    # The served repository: two commits, one of 2 MiB that does not compress,
    # so half a fetch response stops mid-pack (the http-live-stall fixture).
    srv = out / 'srv'
    work = srv / 'work'
    run([git, 'init', '-q', '-b', 'main', work])
    (work / 'README').write_text('stall fixture\n')
    (work / 'blob.bin').write_bytes(b''.join(hashlib.sha256(b'%d' % i).digest() for i in range(65536)))
    run([git, 'add', 'README', 'blob.bin'], work)
    run([git, 'commit', '-q', '-m', 'one'], work)
    (work / 'two.txt').write_text('two\n')
    run([git, 'add', 'two.txt'], work)
    run([git, 'commit', '-q', '-m', 'two'], work)
    run([git, 'clone', '-q', '--bare', work, srv / 'remote.git'])
    shutil.rmtree(work)
    tip = run([git, '--git-dir', srv / 'remote.git', 'rev-parse', 'HEAD'])

    # The gateway's fixture PKI (tools/http-git-test.py's commands); the keys
    # stay out of target/runs and are removed when the row ends.
    pki = R / 'target/pki' / out.name
    for path, digest in OPENSSL_PINS.items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, 'pinned TLS oracle digest'
    if pki.exists():
        shutil.rmtree(pki)
    pki.mkdir(parents=True)
    openssl = lambda *argv: run(['/usr/bin/openssl', *argv])
    openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '2',
            '-subj', '/CN=Smart HTTP fixture root', '-addext', 'basicConstraints=critical,CA:TRUE',
            '-addext', 'keyUsage=critical,keyCertSign,cRLSign', '-keyout', pki / 'ca.key', '-out', pki / 'ca.pem')
    openssl('x509', '-in', pki / 'ca.pem', '-outform', 'DER', '-out', pki / 'ca.der')
    (pki / 'leaf.cnf').write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n'
                                  'extendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost\n')
    openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=localhost',
            '-keyout', pki / 'leaf.key', '-out', pki / 'leaf.csr')
    openssl('x509', '-req', '-in', pki / 'leaf.csr', '-CA', pki / 'ca.pem', '-CAkey', pki / 'ca.key',
            '-CAcreateserial', '-days', '1', '-sha256', '-extfile', pki / 'leaf.cnf', '-out', pki / 'leaf.pem')
    tls = dict(GIT_SSL_CAINFO=str(pki / 'ca.pem'), DEN_TLS_ROOTS=str(pki / 'ca.der'))

    def tool(name, argv, cwd, extra):
        """One run, bounded at STOP seconds (its own child stopped, a failure)."""
        index = len(list(out.glob('*.stderr')))
        paths = out / ('%02d.stdout' % index), out / ('%02d.stderr' % index)
        started = time.monotonic()
        with open(paths[0], 'wb') as o, open(paths[1], 'wb') as e:
            child = subprocess.Popen([str(a) for a in argv], cwd=cwd, env={**env, **tls, **extra},
                                     stdin=subprocess.DEVNULL, stdout=o, stderr=e)
        stopped = False
        while True:
            pid, status, _ = os.wait4(child.pid, os.WNOHANG)
            if pid:
                break
            if not stopped and time.monotonic() - started > STOP:
                os.kill(child.pid, signal.SIGKILL)  # This row's own child only.
                stopped = True
            time.sleep(0.05)
        return dict(name=name, exit=os.waitstatus_to_exitcode(status), stopped=stopped,
                    elapsed=round(time.monotonic() - started, 2),
                    stderr=paths[1].read_bytes().decode('utf-8', 'replace'))

    failures = []

    def verdict(row, problems, evidence):
        print(('PASS ' if not problems else 'FAIL ') + row + ('' if not problems else ' ' + '; '.join(problems)) +
              ' ' + json.dumps(evidence, sort_keys=True), flush=True)
        if problems:
            failures.append(row)

    for transport in ('plain', 'tls'):
        # Control: no stall; den's clone ends as Git's does.
        server = StallGateway(srv, git, env, transport, pki, 'none')
        try:
            runs = {}
            for name, exe in (('git', git), ('den', den)):
                where = out / ('none-%s-%s' % (transport, name))
                where.mkdir()
                runs[name] = tool(name, [exe, 'clone', server.url, 'dest'], where, {})
                runs[name]['refs'] = subprocess.run(
                    [git, '-C', str(where / 'dest'), 'for-each-ref', '--format=%(refname) %(objectname)'],
                    env=env, capture_output=True, text=True).stdout
        finally:
            server.close()
        problems = []
        for key in ('exit', 'refs'):
            if runs['git'][key] != runs['den'][key]:
                problems.append('%s: git %r, den %r' % (key, runs['git'][key], runs['den'][key]))
        if runs['den']['exit'] != 0 or tip not in runs['den']['refs']:
            problems.append('den did not clone the tip')
        verdict('http-stall-%s-none' % transport, problems,
                dict(git=runs['git']['exit'], den=runs['den']['exit'], den_elapsed=runs['den']['elapsed']))

        cues = ['silent', 'keepalive', 'progress'] + (['before-pack', 'default'] if transport == 'tls' else [])
        for cue in cues:
            row = 'http-stall-%s-%s' % (transport, 'keepalive-default' if cue == 'default' else cue)
            server = StallGateway(srv, git, env, transport, pki, 'keepalive' if cue == 'default' else cue)
            where = out / ('%s-%s' % (transport, cue))
            where.mkdir()
            extra = {} if cue == 'default' else {'DEN_STALL_SECONDS': str(BOUND)}
            try:
                r = tool('den', [den, 'clone', server.url, 'dest'], where, extra)
            finally:
                server.close()
            low, high = {'default': (30, 60), 'before-pack': (4 * BOUND, 4 * BOUND + 25)}.get(cue, (BOUND, BOUND + 25))
            lines = r['stderr'].strip().splitlines()
            problems = []
            if r['stopped']:
                problems.append('den was still waiting at %d s' % STOP)
            if r['exit'] != 128:
                problems.append('exit %d, not 128' % r['exit'])
            if not lines or lines[-1] != LINE[cue]:
                problems.append('last line %r, not %r' % (lines[-1] if lines else '', LINE[cue]))
            if not low <= r['elapsed'] <= high:
                problems.append('ended at %.1f s, outside %d-%d s' % (r['elapsed'], low, high))
            if (where / 'dest').exists():
                problems.append('the destination was left behind')
            verdict(row, problems, dict(exit=r['exit'], elapsed=r['elapsed'], stalled=server.stalled,
                                        last=lines[-1] if lines else ''))

    # A submodule update against the stalling remote.
    server = StallGateway(srv, git, env, 'tls', pki, 'keepalive')
    sup = out / 'super'
    try:
        run([git, 'init', '-q', '-b', 'main', sup])
        (sup / '.gitmodules').write_text('[submodule "mod"]\n\tpath = mod\n\turl = %s\n' % server.url)
        run([git, 'add', '.gitmodules'], sup)
        run([git, 'update-index', '--add', '--cacheinfo', '160000,%s,mod' % tip], sup)
        run([git, 'commit', '-q', '-m', 'one submodule'], sup)
        r = tool('den', [den, 'submodule', 'update', '--init'], sup, {'DEN_STALL_SECONDS': str(BOUND)})
    finally:
        server.close()
    named = r['stderr'].splitlines().count(LINE['keepalive'])
    problems = []
    if r['stopped']:
        problems.append('den was still waiting at %d s' % STOP)
    if r['exit'] != 1:
        problems.append('exit %d, not 1' % r['exit'])
    if named != 2:
        problems.append('the named line %d times, not twice (one a clone attempt)' % named)
    if (sup / '.git/modules/mod').exists():
        problems.append('the module git directory was left behind')
    verdict('http-stall-submodule-tls-keepalive', problems,
            dict(exit=r['exit'], elapsed=r['elapsed'], named=named, stalled=server.stalled))

    shutil.rmtree(pki, ignore_errors=True)
    if failures:
        raise SystemExit('FAIL http-stall: ' + ', '.join(failures))
    print('http-stall: %s; zero skips' % args.tier, flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        raise SystemExit('FAIL http-stall-harness: ' + str(exc))
