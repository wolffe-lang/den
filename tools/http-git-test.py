#!/usr/bin/env python3
"""Git smart-HTTP interoperability using documented CGI and HTTP framing only.

Run through tools/env inside the oracle container. TLS uses the pinned OpenSSL
s_server executable as a byte-stream terminator, never Python's ssl module.
All repositories, certificate keys and sockets are disposable local fixtures.
No token, Authorization value, request header dump or effective environment is
written to a capture. Failed parity remains FAIL, never an implicit review.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import selectors
import shutil
import socket
import subprocess
import threading
import time
from urllib.parse import unquote, urlsplit

GIT_SHA256 = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
OPENSSL_PINS = {
    '/usr/bin/openssl': 'b4f547c0f16272d1cc7f870330a6f2c243710c335e7a99c734ff7a0c6fdb2503',
    '/usr/lib/x86_64-linux-gnu/libssl.so.3': 'a40e7b67489bbd257e432c700ff8f6a1ad796425b5eccecdc2930127fdd86624',
    '/usr/lib/x86_64-linux-gnu/libcrypto.so.3': '6866ed711dab8927e1bf82bf1cd30e828bdfc34f3cc1e83b1c9eb01ce6c37d9a',
}


class Stopped(Exception):
    pass


class SecretLeak(Exception):
    pass


class Reader:
    """Bounded raw socket/pipe input; no HTTP library or implementation source."""
    def __init__(self, source, stop):
        self.source = source
        self.stop = stop
        self.buffer = bytearray()
        self.selector = selectors.DefaultSelector()
        self.selector.register(source, selectors.EVENT_READ)

    def close(self):
        self.selector.close()

    def more(self, deadline):
        while True:
            if self.stop.is_set():
                raise Stopped()
            if time.monotonic() >= deadline:
                raise RuntimeError('fixture input timeout')
            if self.selector.select(timeout=0.2):
                data = os.read(self.source.fileno(), 65536)
                if not data:
                    raise EOFError()
                self.buffer.extend(data)
                return

    def line(self, deadline, cap=8192):
        while True:
            pos = self.buffer.find(b'\r\n')
            if pos >= 0:
                if pos > cap:
                    raise RuntimeError('fixture line limit')
                line = bytes(self.buffer[:pos])
                del self.buffer[:pos + 2]
                return line
            if len(self.buffer) > cap:
                raise RuntimeError('fixture line limit')
            self.more(deadline)

    def exact(self, count, deadline):
        if count < 0 or count > 16 * 1024 * 1024:
            raise RuntimeError('fixture body limit')
        while len(self.buffer) < count:
            self.more(deadline)
        data = bytes(self.buffer[:count])
        del self.buffer[:count]
        return data


def stop_process(process):
    if process.poll() is None:
        process.terminate()  # Only this fixture's PID, never a process group.
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


class Server:
    """Sequential CGI gateway; Connection: close avoids HTTP session assumptions.

    OpenSSL's quiet server transports decrypted requests through stdout and
    response bytes through stdin across successive TLS connections. The bridge
    consumes complete request framing before invoking git-http-backend.
    """
    def __init__(self, root, git, env, mode, pki, token, safe):
        self.root = root
        self.git = git
        self.env = env
        self.mode = mode
        self.token = token
        self.safe = safe
        self.stop = threading.Event()
        self.errors = []
        self.requests = []
        self.backend_results = []
        self.process = None
        self.listener = None
        self.thread = None
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            self.port = reservation.getsockname()[1]
        self.url = ('https://localhost:' if mode == 'tls' else 'http://127.0.0.1:') + str(self.port) + '/remote.git'
        if mode == 'tls':
            self.process = subprocess.Popen([
                '/usr/bin/openssl', 's_server', '-quiet', '-ign_eof', '-naccept', '10000',
                '-accept', str(self.port), '-cert', str(pki / 'leaf.pem'), '-key', str(pki / 'leaf.key'),
                '-tls1_3', '-groups', 'X25519', '-ciphersuites', 'TLS_CHACHA20_POLY1305_SHA256',
                '-num_tickets', '0',
            ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            # A TCP-only probe completes no TLS request and carries no credentials.
            # Its accept slot is deliberate; s_server is configured for many slots.
            for _ in range(200):
                if self.process.poll() is not None:
                    raise RuntimeError('TLS fixture exited during startup')
                try:
                    with socket.create_connection(('127.0.0.1', self.port), timeout=0.1):
                        break
                except OSError:
                    time.sleep(0.025)
            else:
                stop_process(self.process)
                raise RuntimeError('TLS fixture startup timeout')
            self.thread = threading.Thread(target=self.tls_loop, name='http-git-tls-bridge')
        else:
            self.listener = socket.socket()
            self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.listener.bind(('127.0.0.1', self.port))
            self.listener.listen(8)
            self.listener.settimeout(0.2)
            self.thread = threading.Thread(target=self.plain_loop, name='http-git-plain-bridge')
        self.thread.start()

    def request(self, reader):
        deadline = time.monotonic() + 60
        start = reader.line(deadline)
        fields = start.split(b' ')
        if len(fields) != 3 or fields[0] not in (b'GET', b'POST') or fields[2] not in (b'HTTP/1.0', b'HTTP/1.1'):
            raise RuntimeError('fixture request line')
        headers = {}
        size = len(start) + 2
        while True:
            line = reader.line(deadline)
            size += len(line) + 2
            if size > 65536:
                raise RuntimeError('fixture header limit')
            if not line:
                break
            name, separator, value = line.partition(b':')
            if not separator or not name or name.strip() != name:
                raise RuntimeError('fixture header syntax')
            key = name.lower()
            if key in headers:
                raise RuntimeError('fixture duplicate header')
            headers[key] = value.strip()
        body = b''
        if b'transfer-encoding' in headers:
            if b'content-length' in headers or headers[b'transfer-encoding'].lower() != b'chunked':
                raise RuntimeError('fixture request framing')
            parts = []
            total = 0
            while True:
                count_text = reader.line(deadline).split(b';', 1)[0]
                if not count_text or any(c not in b'0123456789abcdefABCDEF' for c in count_text):
                    raise RuntimeError('fixture chunk size')
                count = int(count_text, 16)
                if count == 0:
                    while reader.line(deadline):
                        pass
                    break
                total += count
                if total > 16 * 1024 * 1024:
                    raise RuntimeError('fixture request body limit')
                parts.append(reader.exact(count, deadline))
                if reader.exact(2, deadline) != b'\r\n':
                    raise RuntimeError('fixture chunk terminator')
            body = b''.join(parts)
        elif b'content-length' in headers:
            value = headers[b'content-length']
            if not value.isdigit():
                raise RuntimeError('fixture Content-Length')
            body = reader.exact(int(value), deadline)
        return fields[0].decode('ascii'), fields[1].decode('ascii'), headers, body

    def response(self, request):
        method, target, headers, body = request
        parsed = urlsplit(target)
        path = unquote(parsed.path)
        if parsed.scheme or parsed.netloc or not path.startswith('/remote.git/') or '..' in path.split('/'):
            raise RuntimeError('fixture path outside owned repository')
        # Metadata only: Authorization and other raw field values are never retained.
        self.requests.append(dict(method=method, path=parsed.path, query=parsed.query,
                                  protocol=headers.get(b'git-protocol', b'').decode('ascii'),
                                  bytes=len(body), body_sha256=hashlib.sha256(body).hexdigest(),
                                  want=b'want ' in body, have=b'have ' in body,
                                  command_ls_refs=b'command=ls-refs' in body,
                                  command_fetch=b'command=fetch' in body))
        if self.token:
            expected = b'Basic ' + base64.b64encode(b'x-access-token:' + self.token.encode('ascii'))
            if headers.get(b'authorization') != expected:
                return b'HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Basic realm="fixture"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n'
        environment = dict(self.env)
        environment.update(GIT_PROJECT_ROOT=str(self.root), GIT_HTTP_EXPORT_ALL='1',
                           REQUEST_METHOD=method, PATH_INFO=path, QUERY_STRING=parsed.query,
                           CONTENT_TYPE=headers.get(b'content-type', b'').decode('ascii'),
                           CONTENT_LENGTH=str(len(body)), REMOTE_ADDR='127.0.0.1',
                           REMOTE_USER='fixture', HTTP_GIT_PROTOCOL=headers.get(b'git-protocol', b'').decode('ascii'))
        result = subprocess.run([self.git, 'http-backend'], env=environment, input=body,
                                capture_output=True, timeout=45)
        self.safe(result.stdout)
        self.safe(result.stderr)
        self.backend_results.append(dict(exit=result.returncode, stderr=result.stderr.hex()))
        if result.returncode:
            raise RuntimeError('git-http-backend failed')
        raw_headers, marker, content = result.stdout.partition(b'\r\n\r\n')
        if not marker:
            raw_headers, marker, content = result.stdout.partition(b'\n\n')
        if not marker:
            raise RuntimeError('CGI response lacks header delimiter')
        status = b'200 OK'
        selected = []
        for field in raw_headers.replace(b'\r\n', b'\n').split(b'\n'):
            key, separator, value = field.partition(b':')
            if not separator:
                raise RuntimeError('CGI response field syntax')
            if key.lower() == b'status':
                status = value.strip()
            elif key.lower() not in (b'content-length', b'transfer-encoding', b'connection'):
                selected.append(field)
        selected += [b'Content-Length: ' + str(len(content)).encode(), b'Connection: close']
        return b'HTTP/1.1 ' + status + b'\r\n' + b'\r\n'.join(selected) + b'\r\n\r\n' + content

    def plain_loop(self):
        try:
            while not self.stop.is_set():
                try:
                    peer, _ = self.listener.accept()
                except socket.timeout:
                    continue
                with peer:
                    reader = Reader(peer, self.stop)
                    try:
                        reply = self.response(self.request(reader))
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
        try:
            while not self.stop.is_set():
                reply = self.response(self.request(reader))
                self.process.stdin.write(reply)
                self.process.stdin.flush()
        except Stopped:
            pass
        except Exception as exc:
            if not self.stop.is_set():
                self.errors.append(type(exc).__name__ + ': ' + str(exc))
        finally:
            reader.close()

    def close(self):
        self.stop.set()
        if self.listener:
            self.listener.close()
        if self.thread:
            self.thread.join(timeout=3)
        if self.process:
            stop_process(self.process)
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=3)
            stderr = self.process.stderr.read()
            self.safe(stderr)
            self.backend_results.append(dict(terminator_exit=self.process.returncode, stderr=stderr.hex()))
            for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
                try:
                    pipe.close()
                except BrokenPipeError:
                    pass
        if self.thread and self.thread.is_alive():
            raise RuntimeError('fixture thread did not stop')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    parser.add_argument('--transport', choices=('plain', 'tls'), default='tls')
    parser.add_argument('--auth', action='store_true', help='ephemeral Basic credentials; never recorded')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    git = str(Path(os.environ['DEN_GIT']).resolve())
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == GIT_SHA256, 'pinned Git digest'
    den = root / 'target' / args.tier / 'den'
    if not den.is_file():
        raise SystemExit('FAIL http-git-input: build target/' + args.tier + '/den first')
    out = root / 'target/runs' / ('http-git-' + args.transport + '-' + args.tier + ('-auth' if args.auth else ''))
    if out.exists():
        raise SystemExit('FAIL http-git-fresh-output: select a fresh build directory')
    out.mkdir(parents=True)
    token = secrets.token_hex(24) if args.auth else ''
    forbidden = []
    if token:
        encoded = base64.b64encode(b'x-access-token:' + token.encode())
        forbidden = [token.encode(), encoded, token.encode().hex().encode(), encoded.hex().encode()]

    def safe(data):
        if any(secret in data for secret in forbidden):
            raise SecretLeak('secret appeared in captured output (bytes withheld)')

    def write_json(path, value):
        data = (json.dumps(value, indent=2) + '\n').encode()
        safe(data)
        path.write_bytes(data)

    # Only the pinned test environment, not an inherited live credential, reaches
    # fixture subprocesses. Client authentication is added separately below.
    allowed = ('PATH', 'HOME', 'XDG_CONFIG_HOME', 'TMPDIR', 'LC_ALL', 'TZ',
               'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL', 'GIT_AUTHOR_DATE', 'GIT_COMMITTER_DATE',
               'GIT_EDITOR', 'PAGER', 'GIT_TERMINAL_PROMPT', 'GIT_OPTIONAL_LOCKS')
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env.update(GIT_EXEC_PATH=str(Path(git).parent.parent / 'libexec/git-core'),
               PATH=str(Path(git).parent) + ':/usr/bin:/bin', GIT_CONFIG_NOSYSTEM='1', GIT_TERMINAL_PROMPT='0',
               GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
               GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid',
               GIT_AUTHOR_DATE='1700000000 +0000', GIT_COMMITTER_DATE='1700000000 +0000',
               LC_ALL='C', TZ='UTC0')
    captures = []
    rows = []

    def run(argv, cwd=None, data=b'', check=True, extra=None, label='setup'):
        result = subprocess.run(list(map(str, argv)), cwd=cwd, env={**env, **(extra or {})},
                                input=data, capture_output=True, timeout=90)
        safe(data)
        safe(result.stdout)
        safe(result.stderr)
        capture = dict(label=label, argv=list(map(str, argv)), cwd=str(cwd), stdin=data.hex(),
                       stdout=result.stdout.hex(), stderr=result.stderr.hex(), exit=result.returncode)
        captures.append(capture)
        write_json(out / 'captures.json', captures)
        if check and result.returncode:
            raise AssertionError('fixture command failed; see nonsecret capture ' + str(len(captures) - 1))
        return result

    # The fixture's keys stay out of target/runs, which CI uploads as evidence,
    # and are removed when the row ends.
    pki = root / 'target/pki' / out.name
    if args.transport == 'tls':
        for path, digest in OPENSSL_PINS.items():
            for _ in range(2):
                assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, 'pinned TLS oracle digest'
        if pki.exists():
            shutil.rmtree(pki)
        pki.mkdir(parents=True)
        openssl = lambda *argv: run(['/usr/bin/openssl', *argv])
        openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '2',
                '-subj', '/CN=Smart HTTP fixture root', '-addext', 'basicConstraints=critical,CA:TRUE',
                '-addext', 'keyUsage=critical,keyCertSign,cRLSign', '-keyout', pki/'ca.key', '-out', pki/'ca.pem')
        openssl('x509', '-in', pki/'ca.pem', '-outform', 'DER', '-out', pki/'ca.der')
        extension = pki/'leaf.cnf'
        extension.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n'
                             'extendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost\n')
        openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=localhost',
                '-keyout', pki/'leaf.key', '-out', pki/'leaf.csr')
        openssl('x509', '-req', '-in', pki/'leaf.csr', '-CA', pki/'ca.pem', '-CAkey', pki/'ca.key',
                '-CAcreateserial', '-days', '1', '-sha256', '-extfile', extension, '-out', pki/'leaf.pem')

    remote = out/'remote.git'
    template = out/'template.git'
    seed = out/'seed'
    work = out/'work'
    run([git, 'init', '-q', '--bare', remote])
    run([git, 'symbolic-ref', 'HEAD', 'refs/heads/main'], remote)
    for key, value in [('http.receivepack', 'true'), ('gc.auto', '0'), ('maintenance.auto', 'false')]:
        run([git, 'config', key, value], remote)

    def commit_at(repo, text, message, parent=None):
        blob = run([git, 'hash-object', '-w', '--stdin'], repo, text).stdout.strip()
        tree = run([git, 'mktree'], repo, b'100644 blob ' + blob + b'\tfile\n').stdout.strip().decode()
        argv = [git, 'commit-tree', tree, '-m', message]
        if parent:
            argv += ['-p', parent]
        return run(argv, repo).stdout.strip().decode()

    first = commit_at(remote, b'first\n', 'base')
    second = commit_at(remote, b'first\nsecond\n', 'forward', first)
    for reference in ('refs/heads/main', 'refs/heads/topic'):
        run([git, 'update-ref', reference, first], remote)
    run([git, 'tag', '-a', 'v1', '-m', 'fixture tag', first], remote)
    shutil.copytree(remote, template)
    # Seed preparation is a separate pinned-Git operation, not a den assertion.
    run([git, 'clone', '-q', remote.as_uri(), seed])
    third = commit_at(seed, b'client-only\n', 'client change', first)
    # Do not copy the remote's unreachable second commit into this seed:
    # incremental fetch must actually send want/have and import its objects.

    def reset(destination, source=None):
        if destination.exists():
            assert destination in (remote, work)
            shutil.rmtree(destination)
        if source:
            shutil.copytree(source, destination)

    def state(repo, bare=False):
        run([git, 'fsck', '--full', '--no-reflogs'], repo)
        refs = run([git, 'for-each-ref', '--format=%(refname) %(objectname)'], repo).stdout.decode().splitlines()
        listing = run([git, 'cat-file', '--batch-all-objects', '--batch-check=%(objectname) %(objecttype)'], repo).stdout.splitlines()
        objects = {}
        for entry in listing:
            name, kind = entry.decode().split(' ')
            body = run([git, 'cat-file', kind, name], repo).stdout
            objects[name] = dict(kind=kind, body=body.hex())
        gitdir = repo if bare else repo/'.git'
        files = {}
        complete = {}
        for path in sorted(repo.rglob('*')):
            relative = path.relative_to(repo).as_posix()
            if path.is_symlink():
                value = dict(link=os.readlink(path))
            elif path.is_file():
                data = path.read_bytes()
                safe(data)
                value = dict(mode=path.stat().st_mode & 0o777, bytes=data.hex())
            else:
                continue
            complete[relative] = value
            if not bare and relative != '.git' and not relative.startswith('.git/'):
                files[relative] = value
        return dict(refs=refs, objects=objects, head=(gitdir/'HEAD').read_bytes().hex(), worktree=files,
                    complete_files=complete)

    def comparable(value):
        # Full raw files are retained; loose compression/pack bytes and physical
        # index stat fields are not claimed byte-identical by this transport row.
        return {key: value[key] for key in ('refs', 'objects', 'head', 'worktree')}

    server = Server(out, git, env, args.transport, pki, token, safe)
    try:
        run([git, 'remote', 'set-url', 'origin', server.url], seed)
        clients = {}
        for name in ('git', 'den'):
            extra = {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'protocol.version', 'GIT_CONFIG_VALUE_0': '2'}
            if args.transport == 'tls':
                extra.update(GIT_SSL_CAINFO=str(pki/'ca.pem'), DEN_TLS_ROOTS=str(pki/'ca.der'))
            if token:
                if name == 'git':
                    extra.update(GIT_CONFIG_COUNT='2', GIT_CONFIG_KEY_1='http.extraHeader',
                                 GIT_CONFIG_VALUE_1='Authorization: Basic ' + base64.b64encode(b'x-access-token:' + token.encode()).decode())
                else:
                    extra.update(DEN_HTTP_USER='x-access-token', DEN_HTTP_TOKEN=token)
            clients[name] = extra
        cases = [
            ('http-clone', 'clone'), ('http-clone-bare', 'bare'), ('http-fetch', 'fetch'),
            ('http-push', 'push'), ('http-push-rejected', 'reject'),
            ('http-lease-match', 'lease-match'), ('http-lease-stale', 'lease-stale'),
            ('http-push-atomic', 'atomic'),
        ]
        failed = []
        for label, kind in cases:
            outcomes = []
            for tool_name, tool in [('git', git), ('den', str(den))]:
                reset(remote, template)
                reset(work, None if kind in ('clone', 'bare') else seed)
                if kind in ('clone', 'bare'):
                    argv = ['clone', '-q'] + (['--bare'] if kind == 'bare' else []) + [server.url, str(work)]
                    cwd = out
                elif kind == 'fetch':
                    run([git, 'update-ref', 'refs/heads/main', second], remote)
                    argv, cwd = ['fetch', '-q'], work
                elif kind == 'reject':
                    run([git, 'config', 'receive.denyDeletes', 'true'], remote)
                    argv, cwd = ['push', '-q', 'origin', ':refs/heads/topic'], work
                else:
                    run([git, 'update-ref', 'refs/heads/main', third], work)
                    argv, cwd = ['push', '-q'], work
                    if kind.startswith('lease-'):
                        run([git, 'update-ref', 'refs/heads/main', second], remote)
                        expected = second if kind == 'lease-match' else first
                        argv += ['--force-with-lease=refs/heads/main:' + expected]
                    if kind == 'atomic':
                        argv += ['--atomic']
                    argv += ['origin', 'refs/heads/main:refs/heads/main']
                    if kind == 'atomic':
                        argv += ['refs/heads/main:refs/heads/atomic-other']
                before = state(remote, True)
                request_start = len(server.requests)
                result = run([tool, *argv], cwd, check=False, extra=clients[tool_name], label=label + '-' + tool_name)
                if server.errors:
                    raise AssertionError('fixture server error: ' + ', '.join(server.errors))
                after = state(remote, True)
                local = state(work, kind == 'bare') if work.exists() and (work/'HEAD' if kind == 'bare' else work/'.git/HEAD').exists() else None
                outcomes.append(dict(tool=tool_name, exit=result.returncode, stdout=result.stdout.hex(), stderr=result.stderr.hex(),
                                     before=before, remote=after, local=local,
                                     requests=server.requests[request_start:]))
            oracle, candidate = outcomes
            expected_failure = kind in ('reject', 'lease-stale')
            ok = (oracle['exit'] != 0 if expected_failure else oracle['exit'] == 0)
            ok = ok and all(candidate[field] == oracle[field] for field in ('exit', 'stdout', 'stderr'))
            ok = ok and comparable(candidate['remote']) == comparable(oracle['remote'])
            ok = ok and candidate['local'] is not None and oracle['local'] is not None
            if candidate['local'] is not None and oracle['local'] is not None:
                ok = ok and comparable(candidate['local']) == comparable(oracle['local'])
            if expected_failure:
                ok = ok and comparable(candidate['before']) == comparable(candidate['remote'])
            if kind in ('clone', 'bare', 'fetch'):
                upload = [request for request in candidate['requests']
                          if request['query'] == 'service=git-upload-pack' or request['path'].endswith('/git-upload-pack')]
                ok = ok and bool(upload) and all(request['protocol'] == 'version=2' for request in upload)
                ok = ok and any(request['command_ls_refs'] for request in upload)
            if kind == 'fetch':
                ok = ok and any(row['command_fetch'] and row['want'] and row['have'] for row in candidate['requests'])
            row = dict(name=label, comparison='exact process bytes/status, refs, canonical objects and worktree',
                       passed=ok, outcomes=outcomes)
            rows.append(row)
            write_json(out/'rows.json', rows)
            print(('PASS ' if ok else 'FAIL ') + label, flush=True)
            if not ok:
                failed.append(label)
        if failed:
            raise AssertionError('non-parity rows: ' + ', '.join(failed))
    finally:
        server.close()
        shutil.rmtree(pki, ignore_errors=True)
        write_json(out/'server.json', dict(requests=server.requests, backend=server.backend_results, errors=server.errors))
    if token:
        for path in out.rglob('*'):
            if path.is_file():
                safe(path.read_bytes())
        print('PASS http-token-secrecy', flush=True)
    print('http-git: ' + args.transport + ' ' + args.tier + '; zero skips', flush=True)


if __name__ == '__main__':
    try:
        main()
    except SecretLeak:
        raise SystemExit('FAIL http-token-secrecy: output withheld')
    except (AssertionError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        raise SystemExit('FAIL http-git-harness: ' + str(exc))
