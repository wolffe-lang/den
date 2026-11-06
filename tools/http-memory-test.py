#!/usr/bin/env python3
"""Peak memory of one large HTTP body, plain and over TLS, by framing.

The client probe receives one 32,000,000-byte body from a loopback raw peer
(Content-Length, chunked) and from the pinned OpenSSL s_server (-HTTP,
Content-Length). Its peak RSS, read from wait4, must stay within
RATIO x the body: a read's temporaries (socket reads, TLS records, decrypted
payloads) die with the read, and only the body itself is kept. Run inside
the oracle container. No HTTP/TLS implementation source is consumed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time

BODY = 32000000
RATIO = 8
PINS = {
    '/usr/bin/openssl': 'b4f547c0f16272d1cc7f870330a6f2c243710c335e7a99c734ff7a0c6fdb2503',
    '/usr/lib/x86_64-linux-gnu/libssl.so.3': 'a40e7b67489bbd257e432c700ff8f6a1ad796425b5eccecdc2930127fdd86624',
    '/usr/lib/x86_64-linux-gnu/libcrypto.so.3': '6866ed711dab8927e1bf82bf1cd30e828bdfc34f3cc1e83b1c9eb01ce6c37d9a',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--client', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    for path, digest in PINS.items():
        for _ in range(2):
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, path
    evidence = Path(args.output).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    # The fixture PKI and the served body stay out of target/runs, which CI
    # uploads as evidence; they live under target/pki and are removed at the end.
    pki = evidence.parent.parent / 'pki' / evidence.name
    if pki.exists():
        shutil.rmtree(pki)
    pki.mkdir(parents=True)

    def openssl(*argv):
        subprocess.run(['/usr/bin/openssl', *map(str, argv)], check=True, capture_output=True)

    # Disposable local fixture keys; never live credentials.
    openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '2', '-subj', '/CN=HTTP memory root',
            '-addext', 'basicConstraints=critical,CA:TRUE', '-addext', 'keyUsage=critical,keyCertSign,cRLSign',
            '-keyout', pki / 'ca.key', '-out', pki / 'ca.pem')
    openssl('x509', '-in', pki / 'ca.pem', '-outform', 'DER', '-out', pki / 'ca.der')
    (pki / 'leaf.cnf').write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n'
                                   'extendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost\n')
    openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=localhost',
            '-keyout', pki / 'leaf.key', '-out', pki / 'leaf.csr')
    openssl('x509', '-req', '-in', pki / 'leaf.csr', '-CA', pki / 'ca.pem', '-CAkey', pki / 'ca.key',
            '-CAcreateserial', '-days', '1', '-sha256', '-extfile', pki / 'leaf.cnf', '-out', pki / 'leaf.pem')
    piece = b'x' * 16384
    results, failures = [], []

    for name in ['http-memory-length', 'http-memory-chunked', 'http-memory-tls']:
        env = {**os.environ, 'DEN_TEST_HTTP_COUNT': '1'}
        server = thread = None
        errors = []
        if name == 'http-memory-tls':
            (pki / 'probe').write_bytes(b'HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n' % BODY +
                                         b'x' * BODY)
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                port = reservation.getsockname()[1]
            server = subprocess.Popen(['/usr/bin/openssl', 's_server', '-accept', str(port),
                                       '-cert', str(pki / 'leaf.pem'), '-key', str(pki / 'leaf.key'), '-tls1_3',
                                       '-ciphersuites', 'TLS_CHACHA20_POLY1305_SHA256', '-HTTP', '-naccept', '1'],
                                      cwd=pki, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            greeting, deadline = b'', time.monotonic() + 10
            while b'ACCEPT' not in greeting:
                if time.monotonic() > deadline:
                    raise RuntimeError('OpenSSL startup timeout')
                greeting += os.read(server.stdout.fileno(), 4096)
            env.update(DEN_TEST_HTTP_URL='https://localhost:%d' % port, DEN_TLS_ROOTS=str(pki / 'ca.der'))
        else:
            listener = socket.socket()
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            listener.settimeout(30)
            port = listener.getsockname()[1]

            def serve(listener=listener, chunked=name.endswith('chunked')):
                try:
                    with listener, listener.accept()[0] as peer:
                        peer.settimeout(30)
                        request = b''
                        while not request.endswith(b'\r\n\r\n'):
                            part = peer.recv(1)
                            if not part:
                                raise RuntimeError('request ended before headers')
                            request += part
                        framing = b'Transfer-Encoding: chunked' if chunked else b'Content-Length: %d' % BODY
                        peer.sendall(b'HTTP/1.1 200 OK\r\n' + framing + b'\r\n\r\n')
                        left = BODY
                        while left:
                            size = min(left, len(piece))
                            peer.sendall((b'%x\r\n' % size + piece[:size] + b'\r\n') if chunked else piece[:size])
                            left -= size
                        if chunked:
                            peer.sendall(b'0\r\n\r\n')
                except Exception as exc:
                    errors.append(type(exc).__name__)

            thread = threading.Thread(target=serve)
            thread.start()
            env['DEN_TEST_HTTP_URL'] = 'http://127.0.0.1:%d' % port
        started = time.monotonic()
        with (evidence / (name + '.stdout')).open('wb') as stdout, (evidence / (name + '.stderr')).open('wb') as stderr:
            child = subprocess.Popen([args.client], env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        _, status, usage = os.wait4(child.pid, 0)
        child.returncode = os.waitstatus_to_exitcode(status)
        elapsed = time.monotonic() - started
        if server is not None:
            if server.poll() is None:
                server.terminate()
            server.wait(timeout=10)
            server.stdout.close()
        if thread is not None:
            thread.join(timeout=30)
        head = (evidence / (name + '.stdout')).read_bytes()[:64]
        ratio = usage.ru_maxrss * 1024 / BODY
        ok = (child.returncode == 0 and not errors and head.startswith(b'status=200 bytes=%d round=0\n' % BODY)
              and ratio <= RATIO)
        results.append(dict(row=name, exit=child.returncode, body=BODY, maxrss_kib=usage.ru_maxrss,
                            ratio=round(ratio, 2), elapsed=round(elapsed, 2), errors=errors))
        (evidence / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
        print('%s %s: maxrss=%d KiB ratio=%.2f (bound %d) exit=%d' % (
            'PASS' if ok else 'FAIL', name, usage.ru_maxrss, ratio, RATIO, child.returncode), flush=True)
        if not ok:
            failures.append(name)
        for leftover in (evidence / (name + '.stdout'), pki / 'probe'):
            if leftover.exists():
                leftover.unlink()
    shutil.rmtree(pki)
    if failures:
        raise SystemExit('failed rows: ' + ', '.join(failures))


if __name__ == '__main__':
    main()
