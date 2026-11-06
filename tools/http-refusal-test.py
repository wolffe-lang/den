#!/usr/bin/env python3
"""Transport policy refuses before contacting a peer or executing a helper.

The TLS root rows connect to a loopback listener that accepts and sends
nothing: den must refuse at its root bundle before any TLS byte, never read
Git's TLS variables, and honour no verification bypass. A refused clone
leaves no destination.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading

binary = str(Path(sys.argv[1]).resolve())
output = Path(sys.argv[2]).resolve(); output.mkdir(parents=True, exist_ok=True)
(output/'empty.der').write_bytes(b'')
listener = socket.socket(); listener.bind(('127.0.0.1', 0)); listener.listen(16); listener.settimeout(0.2)
port = listener.getsockname()[1]
silent = f'https://127.0.0.1:{port}/repo'
stop = threading.Event(); held = []
def accept():
    while not stop.is_set():
        try: held.append(listener.accept()[0])
        except socket.timeout: continue
server = threading.Thread(target=accept); server.start()
ROOTLESS = ('DEN_TLS_ROOTS', 'GIT_SSL_CAINFO', 'GIT_SSL_CAPATH', 'GIT_SSL_NO_VERIFY')
rows = [
    ('http-credential-helper', ['clone', '-q', 'http://127.0.0.1:1/repo', str(output/'helper')],
     {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'credential.helper', 'GIT_CONFIG_VALUE_0': 'must-not-execute'}, b'HTTP credential.helper'),
    ('http-url-userinfo', ['clone', '-q', 'https://user@example.invalid/repo', str(output/'userinfo')], {}, b'HTTP URL userinfo'),
    ('http-nonloopback', ['clone', '-q', 'http://example.invalid/repo', str(output/'nonloopback')], {}, b'HTTP requires literal loopback'),
    ('http-empty-roots-option', ['clone', '--tls-roots=', '-q', 'https://example.invalid/repo', str(output/'roots')], {}, b'empty TLS roots option'),
    # No verification bypass by configuration or option.
    ('http-config-ssl-verify', ['clone', '-q', 'http://127.0.0.1:1/repo', str(output/'sslverify')],
     {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'http.sslVerify', 'GIT_CONFIG_VALUE_0': 'false'}, b'HTTP configuration'),
    ('http-config-follow-redirects', ['clone', '-q', 'http://127.0.0.1:1/repo', str(output/'redirects')],
     {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'http.followRedirects', 'GIT_CONFIG_VALUE_0': 'true'}, b'HTTP configuration'),
    ('http-insecure-option', ['clone', '--insecure', '-q', silent, str(output/'insecure')], {}, b'clone option --insecure'),
    # Roots come only from --tls-roots or DEN_TLS_ROOTS, the option first.
    ('http-roots-required', ['clone', '-q', silent, str(output/'required')], {}, b'TLS roots required (DEN_TLS_ROOTS)'),
    ('http-roots-git-variables-ignored', ['clone', '-q', silent, str(output/'git-variables')],
     {'GIT_SSL_CAINFO': '/etc/ssl/certs/ca-certificates.crt', 'GIT_SSL_NO_VERIFY': '1'}, b'TLS roots required (DEN_TLS_ROOTS)'),
    ('http-roots-unreadable', ['clone', '-q', silent, str(output/'unreadable')],
     {'DEN_TLS_ROOTS': str(output/'missing.der')}, b'TLS roots unreadable'),
    ('http-roots-empty', ['clone', '-q', silent, str(output/'empty')], {'DEN_TLS_ROOTS': str(output/'empty.der')}, b'TLS empty root bundle'),
    ('http-roots-option-precedence', ['clone', '--tls-roots=' + str(output/'missing.der'), '-q', silent, str(output/'precedence')],
     {'DEN_TLS_ROOTS': str(output/'empty.der')}, b'TLS roots unreadable'),
]
results = []; failed = []
try:
    for name, argv, extra, expected in rows:
        env = {key: value for key, value in os.environ.items() if key not in ROOTLESS}
        env.update(extra)
        result = subprocess.run([binary, *argv], env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
        ok = result.returncode != 0 and expected in result.stderr and not Path(argv[-1]).exists()
        results.append(dict(row=name, exit=result.returncode, stdout=result.stdout.hex(), stderr=result.stderr.hex(), passed=ok))
        (output/'results.json').write_text(json.dumps(results, indent=2)+'\n')
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else ': exit %d stderr %r' % (result.returncode, result.stderr[:200])), flush=True)
        if not ok: failed.append(name)
finally:
    stop.set(); server.join(timeout=5); listener.close()
    for connection in held: connection.close()
if failed: raise SystemExit('failed transport refusals: ' + ', '.join(failed))
