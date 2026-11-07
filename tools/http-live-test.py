#!/usr/bin/env python3
"""Live smart-HTTP rows against github.com: read-only, never credentials.

http-live-read: den and the pinned Git clone the same small public repository
over https, each against the distribution's root bundle; process bytes and
status, refs, HEAD, reachable canonical objects, worktree and remote config
are compared, and the pinned Git checks den's clone (fsck, status).

http-live-self: den and the pinned Git clone den's own public repository
(a pack over 300 MB, over the old 140,000,000-byte wire cap, den#61) and
compare as the read row does, within the time and the peak RSS predicted in
tests/vc23-prediction.txt; the pinned Git checks den's clone.

http-live-push: with DEN_LIVE_HTTPS_URL and DEN_LIVE_HTTPS_TOKEN, den fetches
that repository with the token through a remote named only in GIT_CONFIG_*
after `den init`, pushes a fresh disposable branch, the server's own ref
advertisement (read by the pinned OpenSSL client) shows it, den deletes it and
the advertisement shows it gone. The token lives only in the environments of
the processes that use it, and the request carrying it on the OpenSSL
client's stdin; the URL is never printed or recorded, and never on a child's
argv: http-live-argv reads every descendant's /proc/<pid>/cmdline while the
row runs, with a control argv it must see. Every retained output is scanned
for the token.

Every row SKIPs by name when github.com:443 is unreachable or when no
distribution root bundle exists; the push row also without its variables. Run through tools/env in the oracle
container. PEM is decoded per RFC 7468 here; no TLS library is imported.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import runpy
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time

GIT_SHA256 = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
READ_URL = 'https://github.com/wolffe-lang/burrow.git'
SELF_URL = 'https://github.com/wolffe-lang/den.git'
# tests/vc23-prediction.txt P2: 64 MiB + W (96 MiB) + 5 x den's largest object.
SELF_RSS_KIB = (160 * 1024 * 1024 + 5 * 103002444) // 1024
SELF_SECONDS = 1800
READ_SECONDS = 300
SECRETS = ('DEN_HTTP_TOKEN', 'DEN_HTTP_USER', 'DEN_LIVE_HTTPS_URL', 'DEN_LIVE_HTTPS_TOKEN',
           'GIT_ASKPASS', 'SSH_ASKPASS', 'DEN_TLS_ROOTS', 'GIT_SSL_CAINFO', 'GIT_SSL_CAPATH')


def pem_roots(path):
    """Concatenated DER from a PEM bundle, strictly per RFC 7468 section 2."""
    text = path.read_bytes()
    begin, end = b'-----BEGIN CERTIFICATE-----', b'-----END CERTIFICATE-----'
    out, count, pos = bytearray(), 0, 0
    while True:
        start = text.find(begin, pos)
        if start < 0:
            break
        stop = text.find(end, start)
        if stop < 0:
            raise ValueError('unterminated PEM certificate')
        body = b''.join(text[start + len(begin):stop].split())
        der = base64.b64decode(body, validate=True)
        if len(der) < 2 or der[0] != 0x30:
            raise ValueError('PEM block is not a DER SEQUENCE')
        out.extend(der)
        count += 1
        pos = stop + len(end)
    if not count:
        raise ValueError('no certificates in bundle')
    return bytes(out), count


def reachable(host, port, timeout=10):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return ''
    except OSError as exc:
        return type(exc).__name__


class ArgvWatch:
    """R-vc22b-1 (a): read /proc/<pid>/cmdline of every descendant of this
    process while a row runs, and count each argv holding a secret needle (the
    fixture's URL, its path or the token). Needles are never printed. A
    synthetic control child proves the watcher sees an argv it should."""
    CONTROL = b'den-live-argv-control-' + secrets.token_hex(8).encode()

    def __init__(self, needles):
        self.needles = [needle for needle in needles if needle] + [self.CONTROL]
        self.stop = threading.Event()
        self.seen, self.hits, self.control = set(), set(), False
        self.thread = threading.Thread(target=self.loop, name='argv-watch', daemon=True)

    def descendants(self):
        me, parents = os.getpid(), {}
        for entry in os.listdir('/proc'):
            if not entry.isdigit():
                continue
            try:
                with open('/proc/' + entry + '/stat', 'rb') as handle:
                    stat = handle.read()
            except OSError:
                continue
            parents[int(entry)] = int(stat[stat.rfind(b')') + 2:].split()[1])
        out = []
        for pid in parents:
            node = pid
            for _ in range(64):
                node = parents.get(node)
                if node is None:
                    break
                if node == me:
                    out.append(pid)
                    break
        return out

    def loop(self):
        while not self.stop.is_set():
            for pid in self.descendants():
                try:
                    with open('/proc/%d/cmdline' % pid, 'rb') as handle:
                        argv = handle.read()
                except OSError:
                    continue
                if not argv:
                    continue
                self.seen.add(pid)
                for needle in self.needles:
                    if needle in argv:
                        if needle == self.CONTROL:
                            self.control = True
                        else:
                            self.hits.add(pid)
            self.stop.wait(0.005)

    def __enter__(self):
        self.thread.start()
        control = subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(0.5)',
                                    self.CONTROL.decode()], stdin=subprocess.DEVNULL)
        control.wait(timeout=30)
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    parser.add_argument('--rows', default='read,self,push')
    args = parser.parse_args()
    rows = args.rows.split(',')
    assert set(rows) <= {'read', 'self', 'push'} and rows, 'rows'
    root = Path(__file__).resolve().parent.parent
    git = str(Path(os.environ['DEN_GIT']).resolve())
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == GIT_SHA256, 'pinned Git digest'
    den = root / 'target' / args.tier / 'den'
    if not den.is_file():
        raise SystemExit('FAIL http-live-input: build target/' + args.tier + '/den first')
    names = {'read': 'http-live-read', 'self': 'http-live-self', 'push': 'http-live-push'}
    live_url = os.environ.get('DEN_LIVE_HTTPS_URL', '')
    live_token = os.environ.get('DEN_LIVE_HTTPS_TOKEN', '')
    if 'push' in rows and not (live_url and live_token):
        print('SKIP http-live-push reason=DEN_LIVE_HTTPS_URL and DEN_LIVE_HTTPS_TOKEN not both set', flush=True)
        rows = [row for row in rows if row != 'push']
        if not rows:
            return
    if 'push' in rows and not live_url.startswith('https://'):
        raise SystemExit('FAIL http-live-push: DEN_LIVE_HTTPS_URL must be an https URL (value withheld)')
    pem = Path(os.environ.get('DEN_LIVE_ROOTS_PEM', '/etc/ssl/certs/ca-certificates.crt'))
    if not pem.is_file():
        for row in rows:
            print('SKIP ' + names[row] + ' reason=no distribution root bundle', flush=True)
        return
    unreachable = reachable('github.com', 443)
    if unreachable:
        for row in rows:
            print('SKIP ' + names[row] + ' reason=no network (github.com:443 ' + unreachable + ')', flush=True)
        return
    out = root / 'target/runs' / ('http-live-' + args.tier)
    if out.exists():
        raise SystemExit('FAIL http-live-fresh-output: select a fresh build directory')
    out.mkdir(parents=True)
    der, count = pem_roots(pem)
    roots = out / 'roots.der'
    roots.write_bytes(der)
    print('ROOTS certificates=%d bytes=%d sha256=%s' % (count, len(der), hashlib.sha256(der).hexdigest()), flush=True)

    env = {key: value for key, value in os.environ.items() if key not in SECRETS}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_CONFIG_COUNT='1',
               GIT_CONFIG_KEY_0='protocol.version', GIT_CONFIG_VALUE_0='2')
    tools = {'git': dict(GIT_SSL_CAINFO=str(pem)), 'den': dict(DEN_TLS_ROOTS=str(roots))}
    captures = []
    user = os.environ.get('DEN_LIVE_HTTPS_USER', 'x-access-token')
    basic = base64.b64encode((user + ':' + live_token).encode()) if live_token else b''
    forbidden = [live_token.encode(), basic, live_token.encode().hex().encode(), basic.hex().encode()] if live_token else []

    def hidden(data):
        # The fixture is never named in a retained output, and the token never
        # reaches one: replace the URL, then refuse any trace of the token.
        if live_url:
            data = data.replace(live_url.encode(), b'<DEN_LIVE_HTTPS_URL>')
            data = data.replace(live_url.rstrip('/').removesuffix('.git').encode(), b'<DEN_LIVE_HTTPS_URL>')
        if any(secret and secret in data for secret in forbidden):
            raise SecretLeak()
        return data

    def record():
        (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')

    def run(argv, cwd, label, timeout, tool='git', extra=None):
        # Output goes to files and the child is reaped by wait4, so its own
        # rusage (max RSS, CPU) is measured and no pipe can stall it.
        index = len(captures)
        paths = out / ('%03d.stdout' % index), out / ('%03d.stderr' % index)
        started = time.monotonic()
        with open(paths[0], 'wb') as stdout, open(paths[1], 'wb') as stderr:
            child = subprocess.Popen(list(map(str, argv)), cwd=cwd, env={**env, **tools[tool], **(extra or {})},
                                     stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        terminate_at, kill_at, timed_out = started + timeout, None, False
        while True:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                break
            now = time.monotonic()
            if not timed_out and now >= terminate_at:
                timed_out, kill_at = True, now + 10
                os.kill(child.pid, signal.SIGTERM)  # This child's pid only, never a group.
            elif kill_at is not None and now >= kill_at:
                os.kill(child.pid, signal.SIGKILL)
                kill_at = None
            time.sleep(0.05)
        child.returncode = os.waitstatus_to_exitcode(status)
        elapsed = time.monotonic() - started
        outputs = [hidden(path.read_bytes()) for path in paths]
        for path, data in zip(paths, outputs):
            path.write_bytes(data)
        capture = dict(label=label, argv=[hidden(str(a).encode()).decode() for a in argv], exit=child.returncode,
                       timed_out=timed_out, elapsed=round(elapsed, 2), maxrss_kib=usage.ru_maxrss,
                       user=round(usage.ru_utime, 2), system=round(usage.ru_stime, 2),
                       stdout=outputs[0].hex(), stderr=outputs[1].hex())
        captures.append(capture)
        record()
        return capture

    def git_out(repo, *argv, data=None):
        result = subprocess.run([git, '-C', str(repo), *argv], env=env, input=data, capture_output=True, timeout=120)
        if result.returncode:
            raise AssertionError('pinned Git ' + argv[0] + ' failed in ' + repo.name + ': ' +
                                 result.stderr.decode(errors='replace').strip())
        return result.stdout

    def state(repo):
        refs = git_out(repo, 'for-each-ref', '--format=%(refname) %(objectname) %(symref)')
        ids = sorted({line.split()[0] for line in git_out(repo, 'rev-list', '--objects', '--all').splitlines()})
        # Streamed: den's own repository's objects are hundreds of megabytes.
        digest = hashlib.sha256()
        batch = subprocess.Popen([git, '-C', str(repo), 'cat-file', '--batch'], env=env,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        feeder = threading.Thread(target=lambda: (batch.stdin.write(b''.join(i + b'\n' for i in ids)),
                                                  batch.stdin.close()))
        feeder.start()
        while True:
            chunk = batch.stdout.read(1 << 20)
            if not chunk:
                break
            digest.update(chunk)
        feeder.join()
        if batch.wait(timeout=600):
            raise AssertionError('pinned Git cat-file --batch failed in ' + repo.name)
        config = subprocess.run([git, '-C', str(repo), 'config', '--local', '--get-regexp', r'^(remote|branch)\.'],
                                env=env, capture_output=True, timeout=60).stdout
        files = {}
        for path in sorted(repo.rglob('*')):
            relative = path.relative_to(repo).as_posix()
            if relative == '.git' or relative.startswith('.git/'):
                continue
            if path.is_symlink():
                files[relative] = 'link:' + os.readlink(path)
            elif path.is_file():
                files[relative] = '%o:%s' % (path.stat().st_mode & 0o777, hashlib.sha256(path.read_bytes()).hexdigest())
        return dict(refs=refs.decode(), head=(repo / '.git/HEAD').read_bytes().hex(), objects=len(ids),
                    objects_sha256=digest.hexdigest(), config=config.decode(), worktree=files)

    failed = []
    results = {}
    if 'read' in rows:
        name = names['read']
        ok, why = False, ''
        for attempt in range(2):
            before = run([git, 'ls-remote', READ_URL], out, name + '-ls-remote-before', 120)
            den_dir, git_dir = out / ('read-den-%d' % attempt), out / ('read-git-%d' % attempt)
            candidate = run([den, 'clone', '-q', READ_URL, den_dir], out, name + '-den', READ_SECONDS, 'den')
            oracle = run([git, 'clone', '-q', READ_URL, git_dir], out, name + '-git', READ_SECONDS)
            after = run([git, 'ls-remote', READ_URL], out, name + '-ls-remote-after', 120)
            if before['exit'] or after['exit'] or oracle['exit']:
                why = 'pinned Git could not read the public repository'
                break
            if before['stdout'] != after['stdout']:
                why = 'public refs moved during the row'
                continue
            fields = [field for field in ('exit', 'stdout', 'stderr') if candidate[field] != oracle[field]]
            if fields:
                why = 'process ' + '/'.join(fields) + ' differ: den exit %d stderr %r' % (
                    candidate['exit'], bytes.fromhex(candidate['stderr'])[:400])
                break
            ours, theirs = state(den_dir), state(git_dir)
            differ = [key for key in ours if ours[key] != theirs[key]]
            git_out(den_dir, 'fsck', '--full', '--no-reflogs')
            dirty = git_out(den_dir, 'status', '--porcelain')
            results[name] = dict(den=ours, git=theirs, differ=differ, status=dirty.decode(),
                                 den_elapsed=candidate['elapsed'], den_maxrss_kib=candidate['maxrss_kib'],
                                 git_elapsed=oracle['elapsed'], git_maxrss_kib=oracle['maxrss_kib'])
            if differ or dirty:
                why = 'state differs: ' + ', '.join(differ) + (' (den worktree dirty)' if dirty else '')
                break
            ok = True
            print('LIVE %s head=%s objects=%d den=%.2fs/%sKiB git=%.2fs/%sKiB' % (
                name, ours['refs'].split('\n')[0], ours['objects'], candidate['elapsed'],
                candidate['maxrss_kib'], oracle['elapsed'], oracle['maxrss_kib']), flush=True)
            break
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else ' ' + why), flush=True)
        if not ok:
            failed.append(name)

    if 'self' in rows:
        name = names['self']
        problems = []
        den_dir, git_dir = out / 'self-den', out / 'self-git'
        before = run([git, 'ls-remote', SELF_URL], out, name + '-ls-remote-before', 120)
        candidate = run([den, 'clone', '-q', SELF_URL, den_dir], out, name + '-den', SELF_SECONDS, 'den')
        oracle = run([git, 'clone', '-q', SELF_URL, git_dir], out, name + '-git', SELF_SECONDS)
        after = run([git, 'ls-remote', SELF_URL], out, name + '-ls-remote-after', 120)
        measured = dict(den_exit=candidate['exit'], den_elapsed=candidate['elapsed'],
                        den_maxrss_kib=candidate['maxrss_kib'], den_user=candidate['user'],
                        git_exit=oracle['exit'], git_elapsed=oracle['elapsed'], git_maxrss_kib=oracle['maxrss_kib'],
                        git_user=oracle['user'], bound_kib=SELF_RSS_KIB)
        if oracle['exit'] or before['exit'] or after['exit']:
            problems.append('pinned Git could not read den\'s repository')
        elif before['stdout'] != after['stdout']:
            problems.append('den\'s refs moved during the row')
        for field in ('exit', 'stdout', 'stderr'):
            if candidate[field] != oracle[field]:
                problems.append('process %s differs: den exit %d stderr %r' % (
                    field, candidate['exit'], bytes.fromhex(candidate['stderr'])[:400]))
        if candidate['timed_out']:
            problems.append('den did not finish within %d s' % SELF_SECONDS)
        if candidate['maxrss_kib'] > SELF_RSS_KIB:
            problems.append('den peak RSS %d KiB over the predicted %d' % (candidate['maxrss_kib'], SELF_RSS_KIB))
        if not problems:
            packs = sorted((git_dir / '.git/objects/pack').glob('*.pack'))
            measured['git_pack_bytes'] = [path.stat().st_size for path in packs]
            ours, theirs = state(den_dir), state(git_dir)
            differ = [key for key in ours if ours[key] != theirs[key]]
            git_out(den_dir, 'fsck', '--full', '--no-reflogs')
            dirty = git_out(den_dir, 'status', '--porcelain')
            measured.update(objects=theirs['objects'], differ=differ, status=dirty.decode()[:400])
            if differ or dirty:
                problems.append('state differs: ' + ', '.join(differ) + (' (den worktree dirty)' if dirty else ''))
        results[name] = measured
        print('LIVE ' + name + ' ' + json.dumps(measured, sort_keys=True), flush=True)
        print(('PASS ' if not problems else 'FAIL ') + name + ('' if not problems else ' ' + '; '.join(problems)),
              flush=True)
        if problems:
            failed.append(name)
        for path in (den_dir, git_dir):
            if path.exists():
                shutil.rmtree(path)

    if 'push' in rows:
        name = names['push']
        # R-vc22b-1 (a), R-vc23-3: the fixture's URL never reaches a child's
        # argv. den takes it from a remote named in GIT_CONFIG_* after `den
        # init`; Git would pass it to git-remote-https on argv
        # (gitremote-helpers(7), measured), so the pushed branch is read from
        # the server's own ref advertisement by the pinned OpenSSL client,
        # the request and its credential written on that client's stdin.
        den_auth = {'DEN_HTTP_TOKEN': live_token, 'DEN_HTTP_USER': user,
                    'GIT_CONFIG_COUNT': '3', 'GIT_CONFIG_KEY_1': 'remote.live.url', 'GIT_CONFIG_VALUE_1': live_url,
                    'GIT_CONFIG_KEY_2': 'remote.live.fetch', 'GIT_CONFIG_VALUE_2': '+refs/heads/*:refs/remotes/live/*'}
        work = out / 'push-den'
        branch = 'refs/heads/den-live-push-' + secrets.token_hex(6)
        problems, pushed = [], False
        pins = runpy.run_path(str(root / 'tools/http-git-test.py'))['OPENSSL_PINS']
        assert hashlib.sha256(Path('/usr/bin/openssl').read_bytes()).hexdigest() == pins['/usr/bin/openssl'], \
            'pinned OpenSSL digest'
        target = live_url.removeprefix('https://github.com')

        def advertisement():
            """The server's upload-pack refs (v0 discovery) through `openssl s_client`."""
            request = ('GET ' + target + '/info/refs?service=git-upload-pack HTTP/1.1\r\nHost: github.com\r\n'
                       'User-Agent: git/den-live-row\r\nAccept: */*\r\nAuthorization: Basic ' + basic.decode() +
                       '\r\nConnection: close\r\n\r\n').encode()
            result = subprocess.run(['/usr/bin/openssl', 's_client', '-quiet', '-verify_return_error',
                                     '-CAfile', str(pem), '-servername', 'github.com', '-connect', 'github.com:443'],
                                    env=env, input=request, capture_output=True, timeout=120)
            response = hidden(result.stdout)
            hidden(result.stderr)
            head, _, body = response.partition(b'\r\n\r\n')
            if not head.startswith(b'HTTP/1.1 200 '):
                raise AssertionError('server advertisement status %r' % head.split(b'\r\n')[0][:40])
            if b'transfer-encoding: chunked' in head.lower():
                joined, pos = bytearray(), 0
                while True:
                    eol = body.index(b'\r\n', pos)
                    size = int(body[pos:eol].split(b';')[0], 16)
                    if size == 0:
                        break
                    joined += body[eol + 2:eol + 2 + size]
                    pos = eol + 2 + size + 2
                body = bytes(joined)
            refs, pos = {}, 0
            while pos < len(body):
                length = int(body[pos:pos + 4], 16)
                if length < 4:
                    pos += 4
                    continue
                line = body[pos + 4:pos + length].split(b'\0')[0].rstrip(b'\n')
                pos += length
                if line.startswith(b'#'):
                    continue
                oid, _, ref = line.partition(b' ')
                refs[ref.decode()] = oid.decode()
            return refs

        def remote_ref():
            return advertisement().get(branch, '')

        fixture_path = live_url.removeprefix('https://github.com').removesuffix('.git').encode()
        watch = ArgvWatch([live_url.encode(), live_url.removesuffix('.git').encode(), fixture_path,
                           live_token.encode(), basic]).__enter__()
        init = run([den, 'init', '-q', work], out, name + '-init', 60, 'den')
        fetched = run([den, 'fetch', '-q', 'live'], work, name + '-fetch', READ_SECONDS, 'den', den_auth) \
            if init['exit'] == 0 else init
        if fetched['exit']:
            problems.append('den init or fetch exit %d: %r' % (fetched['exit'], bytes.fromhex(fetched['stderr'])[:300]))
        else:
            # The server's HEAD as the parent, when den's fetch brought it.
            head = advertisement().get('HEAD', '')
            if head and subprocess.run([git, '-C', str(work), 'cat-file', '-e', head + '^{commit}'], env=env,
                                       capture_output=True, timeout=60).returncode:
                head = ''
            blob = git_out(work, 'hash-object', '-w', '--stdin', data=secrets.token_hex(8).encode()).strip()
            tree = git_out(work, 'mktree', data=b'100644 blob ' + blob + b'\tden-live-push\n').strip().decode()
            commit = git_out(work, 'commit-tree', tree, *(['-p', head] if head else []), '-m', 'den live push row').strip().decode()
            git_out(work, 'update-ref', 'refs/heads/den-live-push', commit)
            try:
                push = run([den, 'push', '-q', 'live', 'refs/heads/den-live-push:' + branch], work, name + '-push',
                           READ_SECONDS, 'den', den_auth)
                pushed = push['exit'] == 0
                if not pushed:
                    problems.append('den push exit %d: %r' % (push['exit'], bytes.fromhex(push['stderr'])[:300]))
                elif remote_ref() != commit:
                    problems.append('the server does not advertise the pushed branch at the pushed commit')
            finally:
                if pushed:
                    delete = run([den, 'push', '-q', 'live', ':' + branch], work, name + '-delete', READ_SECONDS,
                                 'den', den_auth)
                    if delete['exit']:
                        problems.append('den delete exit %d: %r' % (delete['exit'], bytes.fromhex(delete['stderr'])[:300]))
                    elif remote_ref():
                        problems.append('the disposable branch is still on the remote')
        watch.__exit__()
        argv_problems = []
        if not watch.control:
            argv_problems.append('the watcher did not see its control argv')
        if not watch.seen:
            argv_problems.append('the watcher saw no child')
        if watch.hits:
            argv_problems.append('%d of %d children held the fixture URL or token on argv (values withheld)' % (
                len(watch.hits), len(watch.seen)))
        print('LIVE http-live-argv children=%d hits=%d control=%s' % (len(watch.seen), len(watch.hits), watch.control),
              flush=True)
        print(('PASS ' if not argv_problems else 'FAIL ') + 'http-live-argv' +
              ('' if not argv_problems else ' ' + '; '.join(argv_problems)), flush=True)
        if argv_problems:
            failed.append('http-live-argv')
        for path in out.rglob('*'):
            if path.is_file():
                hidden(path.read_bytes())
        print('PASS http-token-secrecy-live', flush=True)
        print(('PASS ' if not problems else 'FAIL ') + name + ('' if not problems else ' ' + '; '.join(problems)),
              flush=True)
        if problems:
            failed.append(name)
        if work.exists():
            shutil.rmtree(work)

    (out / 'results.json').write_text(json.dumps(results, indent=2, sort_keys=True) + '\n')
    for path in out.glob('read-*'):
        shutil.rmtree(path)
    if failed:
        raise SystemExit('FAIL http-live: ' + ', '.join(failed))
    print('http-live: ' + args.tier + ' ' + ','.join(rows) + '; zero skips', flush=True)


class SecretLeak(Exception):
    pass


if __name__ == '__main__':
    try:
        main()
    except SecretLeak:
        raise SystemExit('FAIL http-token-secrecy-live: output withheld')
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit('FAIL http-live-harness: ' + str(exc))
