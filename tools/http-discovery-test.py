#!/usr/bin/env python3
"""den clone against hostile and refusing smart-HTTP discovery and RPC peers.

Each row serves one scripted loopback peer and runs `den clone -q`. A refusal
must be den's named diagnostic, byte for byte, with exit 2, and a failed
clone must leave no destination: the pinned Git removes the directory a
failed clone created (measured black-box, R-vc22-6). An existing
destination is refused before any request and left untouched. No HTTP
implementation source is consumed; no credential is supplied.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading


def pkt(text):
    data = text.encode() if isinstance(text, str) else text
    return b'%04x' % (len(data) + 4) + data


V2 = (pkt('version 2\n') + pkt('agent=git/2.56.0-Linux\n') + pkt('ls-refs=unborn\n') +
      pkt('fetch=shallow wait-for-done\n') + pkt('server-option\n') + pkt('object-format=sha1\n') + b'0000')
OID = '1111111111111111111111111111111111111111'
V0 = (pkt('# service=git-upload-pack\n') + b'0000' +
      pkt((OID + ' HEAD').encode() + b'\0multi_ack side-band-64k agent=git/2.56.0\n') + b'0000')


def http(status, body=b'', content_type=None, extra=''):
    head = 'HTTP/1.1 %s\r\nContent-Length: %d\r\n' % (status, len(body))
    if content_type:
        head += 'Content-Type: %s\r\n' % content_type
    return (head + extra + '\r\n').encode() + body


ADVERT = 'application/x-git-upload-pack-advertisement'
RESULT = 'application/x-git-upload-pack-result'
DISCOVER = '/repo/info/refs?service=git-upload-pack'
ROWS = [
    # name, discovery response, RPC response (None: no RPC expected), expected refusal
    ('http-discovery-not-found', http('404 Not Found'), None, 'HTTP repository not found'),
    ('http-discovery-gone', http('410 Gone'), None, 'HTTP repository not found'),
    ('http-discovery-forbidden', http('403 Forbidden'), None, 'HTTP forbidden'),
    ('http-discovery-unauthorized', http('401 Unauthorized', extra='WWW-Authenticate: Basic realm="fixture"\r\n'),
     None, 'HTTP authentication required'),
    ('http-discovery-server-error', http('500 Internal Server Error'), None, 'HTTP status 500'),
    ('http-discovery-unavailable', http('503 Service Unavailable'), None, 'HTTP status 503'),
    ('http-discovery-dumb', http('200 OK', (OID + '\trefs/heads/main\n').encode(), 'text/plain'), None,
     'dumb HTTP protocol'),
    ('http-discovery-v0', http('200 OK', V0, ADVERT), None, 'remote does not advertise protocol v2'),
    ('http-discovery-wrong-banner', http('200 OK', pkt('# service=git-receive-pack\n') + b'0000' + V2, ADVERT), None,
     'HTTP wrong service advertisement'),
    ('http-rpc-redirect', http('200 OK', V2, ADVERT),
     http('302 Found', extra='Location: /elsewhere/git-upload-pack\r\n'), 'HTTP RPC redirect'),
    ('http-rpc-content-type', http('200 OK', V2, ADVERT), http('200 OK', b'0000', 'text/plain'),
     'HTTP RPC content type'),
]


def main():
    den = str(Path(sys.argv[1]).resolve())
    output = Path(sys.argv[2]).resolve()
    if output.exists():
        raise SystemExit('FAIL http-discovery-fresh-output: select a fresh output directory')
    output.mkdir(parents=True)
    env = {key: value for key, value in os.environ.items()
           if key not in ('DEN_HTTP_TOKEN', 'DEN_HTTP_USER', 'DEN_TLS_ROOTS')}
    results, failed = [], []

    def clone(destination, port):
        return subprocess.run([den, 'clone', '-q', 'http://127.0.0.1:%d/repo' % port, str(destination)],
                              env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=60)

    for name, discovery, rpc, refusal in ROWS:
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(4)
        listener.settimeout(0.2)
        port = listener.getsockname()[1]
        stop, seen, errors = threading.Event(), [], []

        def serve(listener=listener, discovery=discovery, rpc=rpc, stop=stop, seen=seen, errors=errors):
            try:
                while not stop.is_set():
                    try:
                        connection = listener.accept()[0]
                    except socket.timeout:
                        continue
                    with connection:
                        connection.settimeout(10)
                        while True:
                            data = b''
                            while b'\r\n\r\n' not in data:
                                piece = connection.recv(1)
                                if not piece:
                                    break
                                data += piece
                                if len(data) > 65536:
                                    raise RuntimeError('request limit')
                            if not data:
                                break
                            head, _, rest = data.partition(b'\r\n\r\n')
                            line = head.split(b'\r\n')[0].decode('ascii')
                            length = 0
                            for field in head.split(b'\r\n')[1:]:
                                key, _, value = field.partition(b':')
                                if key.strip().lower() == b'content-length':
                                    length = int(value.strip())
                            while len(rest) < length:
                                piece = connection.recv(65536)
                                if not piece:
                                    raise RuntimeError('request body truncated')
                                rest += piece
                            seen.append(line)
                            if line == 'GET %s HTTP/1.1' % DISCOVER:
                                connection.sendall(discovery)
                            elif line == 'POST /repo/git-upload-pack HTTP/1.1' and rpc is not None:
                                connection.sendall(rpc)
                            else:
                                connection.sendall(http('400 Bad Request'))
                                errors.append('unexpected request ' + line)
            except Exception as exc:
                errors.append(type(exc).__name__)

        thread = threading.Thread(target=serve)
        thread.start()
        destination = output / name
        try:
            result = clone(destination, port)
        finally:
            stop.set()
            thread.join(timeout=15)
            listener.close()
        expected = ('den: wire: Unsupported(%s)\n' % refusal).encode()
        problems = []
        if thread.is_alive():
            problems.append('peer did not stop')
        if errors:
            problems.append('peer: ' + ', '.join(errors))
        if result.returncode != 2:
            problems.append('exit %d, want 2' % result.returncode)
        if result.stderr != expected:
            problems.append('stderr %r, want %r' % (result.stderr[:300], expected))
        if result.stdout:
            problems.append('stdout not empty')
        if not seen or seen[0] != 'GET %s HTTP/1.1' % DISCOVER:
            problems.append('discovery request not seen first')
        if (rpc is not None) != (len(seen) > 1):
            problems.append('requests %r' % seen)
        if destination.exists():
            problems.append('partial clone left')
            shutil.rmtree(destination)
        results.append(dict(row=name, exit=result.returncode, stdout=result.stdout.hex(), stderr=result.stderr.hex(),
                            requests=seen, problems=problems))
        (output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
        print(('PASS ' if not problems else 'FAIL ') + name + ('' if not problems else ': ' + '; '.join(problems)),
              flush=True)
        if problems:
            failed.append(name)

    # An existing destination is refused before any request and left as found.
    existing = output / 'existing'
    existing.mkdir()
    (existing / 'keep').write_bytes(b'mine\n')
    result = subprocess.run([den, 'clone', '-q', 'http://127.0.0.1:9/repo', str(existing)], env=env,
                            stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
    kept = sorted(p.name for p in existing.iterdir()) == ['keep'] and (existing / 'keep').read_bytes() == b'mine\n'
    ok = result.returncode != 0 and kept
    print(('PASS ' if ok else 'FAIL ') + 'clone-existing-destination-untouched' +
          ('' if ok else ': exit %d, kept %s' % (result.returncode, kept)), flush=True)
    if not ok:
        failed.append('clone-existing-destination-untouched')

    # The cleanup belongs to clone, not to HTTP: a failed file:// clone too.
    missing = output / 'no-such-repository.git'
    destination = output / 'file-clone'
    result = subprocess.run([den, 'clone', '-q', missing.as_uri(), str(destination)], env=env,
                            stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
    ok = result.returncode != 0 and not destination.exists()
    print(('PASS ' if ok else 'FAIL ') + 'clone-file-failure-cleanup' +
          ('' if ok else ': exit %d, destination %s' % (result.returncode, destination.exists())), flush=True)
    if not ok:
        failed.append('clone-file-failure-cleanup')
    if failed:
        raise SystemExit('failed rows: ' + ', '.join(failed))
    print('http-discovery: %d refusal rows and 2 clone rows; zero skips' % len(ROWS), flush=True)


if __name__ == '__main__':
    main()
