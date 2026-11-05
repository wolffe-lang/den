#!/usr/bin/env python3
"""TLS exchange rows against the pinned OpenSSL binary, never library source."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import socket
import subprocess

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
    print('PASS http-openssl-identity', flush=True)
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=True)

    def openssl(*argv):
        subprocess.run(['/usr/bin/openssl', *map(str, argv)], check=True, capture_output=True)

    # Locally generated, disposable fixture keys; never live credentials.
    for name in ['ca', 'wrong-ca']:
        openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '2',
                '-subj', '/CN=HTTP test root ' + name, '-addext', 'basicConstraints=critical,CA:TRUE',
                '-addext', 'keyUsage=critical,keyCertSign,cRLSign',
                '-keyout', root / (name + '.key'), '-out', root / (name + '.pem'))
        openssl('x509', '-in', root / (name + '.pem'), '-outform', 'DER', '-out', root / (name + '.der'))
    extensions = root / 'leaf-extensions.cnf'
    extensions.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n'
                          'extendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost\n')
    openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=localhost',
            '-keyout', root / 'leaf.key', '-out', root / 'leaf.csr')
    openssl('x509', '-req', '-in', root / 'leaf.csr', '-CA', root / 'ca.pem',
            '-CAkey', root / 'ca.key', '-CAcreateserial', '-days', '1', '-sha256',
            '-extfile', extensions, '-out', root / 'leaf.pem')
    (root / 'probe').write_bytes(b'HTTP/1.1 200 OK\r\nContent-Length: 3\r\nConnection: close\r\n\r\nTLS')
    results = []
    failures = []
    for name, roots, expected in [('http-tls-trusted', 'ca.der', None),
                                   ('http-tls-unknown-root', 'wrong-ca.der', b'issuer_mismatch'),
                                   ('http-tls-unframed', 'ca.der', b'wolf-std#133')]:
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        # -HTTP serves the complete framed response file. Only the dedicated
        # wolf-std#133 refusal row uses -www's close-delimited response.
        with (root / (name + '-server.log')).open('wb') as log:
            server = subprocess.Popen(['/usr/bin/openssl', 's_server', '-accept', str(port),
                                       '-cert', str(root / 'leaf.pem'), '-key', str(root / 'leaf.key'),
                                       '-tls1_3', '-ciphersuites', 'TLS_CHACHA20_POLY1305_SHA256',
                                       '-www' if name == 'http-tls-unframed' else '-HTTP', '-naccept', '1'],
                                      cwd=root, stdout=subprocess.PIPE, stderr=log)
            try:
                ready = selectors.DefaultSelector()
                ready.register(server.stdout, selectors.EVENT_READ)
                greeting = b''
                while b'ACCEPT' not in greeting:
                    if not ready.select(timeout=10):
                        raise RuntimeError('OpenSSL startup timeout')
                    chunk = os.read(server.stdout.fileno(), 4096)
                    if not chunk:
                        raise RuntimeError('OpenSSL exited before ACCEPT')
                    greeting += chunk
                env = {**os.environ, 'DEN_TEST_HTTP_URL': f'https://localhost:{port}',
                       'DEN_TLS_ROOTS': str(root / roots), 'DEN_TEST_HTTP_COUNT': '1'}
                result = subprocess.run([args.client], env=env, capture_output=True, timeout=60)
                ok = result.returncode == 0 and result.stdout.startswith(b'status=200 bytes=') if expected is None else (
                    result.returncode != 0 and expected in result.stderr)
                results.append(dict(row=name, exit=result.returncode, stdout=result.stdout.hex(), stderr=result.stderr.hex()))
                print(('PASS ' if ok else 'FAIL ') + name, flush=True)
                if not ok:
                    failures.append(name)
            finally:
                if server.poll() is None:
                    server.terminate()
                server.wait(timeout=10)
                server.stdout.close()
        (root / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    if failures:
        raise SystemExit('failed rows: ' + ', '.join(failures))


if __name__ == '__main__':
    main()
