#!/usr/bin/env python3
"""TLS exchange rows against the pinned OpenSSL binary, never library source."""
import argparse
import base64
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
        result = subprocess.run(['/usr/bin/openssl', *map(str, argv)], capture_output=True)
        if result.returncode:
            raise SystemExit('FAIL http-tls-fixture: openssl %s exit %d: %s' % (
                argv[0], result.returncode, result.stderr.decode(errors='replace').strip()[-400:]))

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
    wrong_extensions = root / 'wrong-name.cnf'
    wrong_extensions.write_text(extensions.read_text().replace('DNS:localhost', 'DNS:wrong.localhost'))
    for leaf, days, ext in [('expired.pem', '-1', extensions), ('wrong-name.pem', '1', wrong_extensions)]:
        openssl('x509', '-req', '-in', root / 'leaf.csr', '-CA', root / 'ca.pem',
                '-CAkey', root / 'ca.key', '-CAcreateserial', '-days', days, '-sha256',
                '-extfile', ext, '-out', root / leaf)
    openssl('x509', '-in', root / 'leaf.pem', '-outform', 'DER', '-out', root / 'leaf.der')
    broken = bytearray((root / 'leaf.der').read_bytes()); broken[-1] ^= 1
    encoded = base64.b64encode(broken)
    (root / 'bad-signature.pem').write_bytes(b'-----BEGIN CERTIFICATE-----\n' +
        b'\n'.join(encoded[i:i+64] for i in range(0, len(encoded), 64)) + b'\n-----END CERTIFICATE-----\n')
    # The broader chain: an intermediate, a non-CA issuer, a clientAuth-only
    # leaf, a leaf not yet valid (UTCTime 2040, issued by `openssl ca`), and
    # ECDSA P-256/P-384 leaves under the RSA root, each signed by OpenSSL.
    ca_extensions = root / 'ca-extensions.cnf'
    ca_extensions.write_text('basicConstraints=critical,CA:TRUE\nkeyUsage=critical,keyCertSign,cRLSign\n')
    not_ca_extensions = root / 'not-ca-extensions.cnf'
    not_ca_extensions.write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,keyCertSign,cRLSign\n')
    client_extensions = root / 'client-extensions.cnf'
    client_extensions.write_text(extensions.read_text().replace('serverAuth', 'clientAuth'))
    for name, ext in [('intermediate', ca_extensions), ('not-ca', not_ca_extensions)]:
        openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=HTTP test issuer ' + name,
                '-keyout', root / (name + '.key'), '-out', root / (name + '.csr'))
        openssl('x509', '-req', '-in', root / (name + '.csr'), '-CA', root / 'ca.pem', '-CAkey', root / 'ca.key',
                '-CAcreateserial', '-days', '2', '-sha256', '-extfile', ext, '-out', root / (name + '.pem'))
        openssl('x509', '-req', '-in', root / 'leaf.csr', '-CA', root / (name + '.pem'), '-CAkey', root / (name + '.key'),
                '-CAcreateserial', '-days', '1', '-sha256', '-extfile', extensions, '-out', root / ('leaf-' + name + '.pem'))
    openssl('x509', '-req', '-in', root / 'leaf.csr', '-CA', root / 'ca.pem', '-CAkey', root / 'ca.key',
            '-CAcreateserial', '-days', '1', '-sha256', '-extfile', client_extensions, '-out', root / 'client-auth.pem')
    (root / 'issued').mkdir(exist_ok=True)
    (root / 'index.txt').write_text('')
    (root / 'serial').write_text('1000\n')
    (root / 'ca.cnf').write_text('[ca]\ndefault_ca = fixture\n[fixture]\ndatabase = %s\nnew_certs_dir = %s\n'
                                 'serial = %s\ndefault_md = sha256\npolicy = anything\n'
                                 '[anything]\ncommonName = supplied\n' % (root / 'index.txt', root / 'issued', root / 'serial'))
    openssl('ca', '-batch', '-notext', '-config', root / 'ca.cnf', '-cert', root / 'ca.pem', '-keyfile', root / 'ca.key',
            '-in', root / 'leaf.csr', '-startdate', '400101000000Z', '-enddate', '401231000000Z',
            '-extfile', extensions, '-out', root / 'not-yet-valid.pem')
    for curve in ['P-256', 'P-384']:
        stem = curve.lower().replace('-', '')
        openssl('req', '-new', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:' + curve, '-nodes', '-subj', '/CN=localhost',
                '-keyout', root / (stem + '.key'), '-out', root / (stem + '.csr'))
        openssl('x509', '-req', '-in', root / (stem + '.csr'), '-CA', root / 'ca.pem', '-CAkey', root / 'ca.key',
                '-CAcreateserial', '-days', '1', '-sha256', '-extfile', extensions, '-out', root / (stem + '.pem'))
    (root / 'probe').write_bytes(b'HTTP/1.1 200 OK\r\nContent-Length: 3\r\nConnection: close\r\n\r\nTLS')
    results = []
    failures = []
    tls13 = ['-tls1_3', '-ciphersuites', 'TLS_CHACHA20_POLY1305_SHA256']
    for name, roots, leaf, expected, option in [
            ('http-tls-trusted', 'ca.der', 'leaf.pem', None, {}),
            ('http-tls-utc', 'ca.der', 'leaf.pem', None, {}),
            ('http-tls-unknown-root', 'wrong-ca.der', 'leaf.pem', b'issuer_mismatch', {}),
            ('http-tls-wrong-name', 'ca.der', 'wrong-name.pem', b'name_mismatch', {}),
            ('http-tls-expired', 'ca.der', 'expired.pem', b'expired', {}),
            ('http-tls-bad-signature', 'ca.der', 'bad-signature.pem', b'bad_signature', {}),
            ('http-tls-unframed', 'ca.der', 'leaf.pem', b'wolf-std#133', {}),
            ('http-tls-intermediate', 'ca.der', 'leaf-intermediate.pem', None, {'chain': 'intermediate.pem'}),
            ('http-tls-missing-intermediate', 'ca.der', 'leaf-intermediate.pem', b'issuer_mismatch', {}),
            ('http-tls-issuer-not-ca', 'ca.der', 'leaf-not-ca.pem', b'not_ca', {'chain': 'not-ca.pem'}),
            ('http-tls-client-auth-only', 'ca.der', 'client-auth.pem', b'bad_usage', {}),
            ('http-tls-not-yet-valid', 'ca.der', 'not-yet-valid.pem', b'not_yet_valid', {}),
            ('http-tls-p256-leaf', 'ca.der', 'p256.pem', None, {'key': 'p256.key'}),
            ('http-tls-p384-leaf', 'ca.der', 'p384.pem', None, {'key': 'p384.key'}),
            ('http-tls-version-1-2', 'ca.der', 'leaf.pem', b'handshake_failure', {'protocol': ['-tls1_2']}),
            ('http-tls-git-bypass-ignored', 'wrong-ca.der', 'leaf.pem', b'issuer_mismatch',
             {'env': {'GIT_SSL_NO_VERIFY': '1', 'GIT_SSL_CAINFO': str(root / 'ca.pem')}}),
    ]:
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        chain = ['-cert_chain', str(root / option['chain'])] if 'chain' in option else []
        # -HTTP serves the complete framed response file. Only the dedicated
        # wolf-std#133 refusal row uses -www's close-delimited response.
        with (root / (name + '-server.log')).open('wb') as log:
            server = subprocess.Popen(['/usr/bin/openssl', 's_server', '-accept', str(port),
                                       '-cert', str(root / leaf), '-key', str(root / option.get('key', 'leaf.key')),
                                       *chain, *option.get('protocol', tls13),
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
                if name == 'http-tls-utc': env['TZ'] = 'UTC+12'
                env.update(option.get('env', {}))
                result = subprocess.run([args.client], env=env, capture_output=True, timeout=60)
                ok = result.returncode == 0 and result.stdout.startswith(b'status=200 bytes=') if expected is None else (
                    result.returncode != 0 and expected in result.stderr)
                results.append(dict(row=name, exit=result.returncode, stdout=result.stdout.hex(), stderr=result.stderr.hex()))
                print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else ': exit %d stderr %r' % (
                    result.returncode, result.stderr[:200])), flush=True)
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
