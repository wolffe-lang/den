#!/usr/bin/env python3
"""Transport policy refuses before contacting a peer or executing a helper."""
import json
import os
from pathlib import Path
import subprocess
import sys

binary = str(Path(sys.argv[1]).resolve())
output = Path(sys.argv[2]).resolve(); output.mkdir(parents=True, exist_ok=True)
rows = [
    ('http-credential-helper', ['clone', '-q', 'http://127.0.0.1:1/repo', str(output/'helper')],
     {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'credential.helper', 'GIT_CONFIG_VALUE_0': 'must-not-execute'}, b'HTTP credential.helper'),
    ('http-url-userinfo', ['clone', '-q', 'https://user@example.invalid/repo', str(output/'userinfo')], {}, b'HTTP URL userinfo'),
    ('http-nonloopback', ['clone', '-q', 'http://example.invalid/repo', str(output/'nonloopback')], {}, b'HTTP requires literal loopback'),
    ('http-empty-roots-option', ['clone', '--tls-roots=', '-q', 'https://example.invalid/repo', str(output/'roots')], {}, b'empty TLS roots option'),
]
results = []; failed = []
for name, argv, extra, expected in rows:
    result = subprocess.run([binary, *argv], env={**os.environ, **extra}, stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
    ok = result.returncode != 0 and expected in result.stderr
    results.append(dict(row=name, exit=result.returncode, stdout=result.stdout.hex(), stderr=result.stderr.hex(), passed=ok))
    (output/'results.json').write_text(json.dumps(results, indent=2)+'\n')
    print(('PASS ' if ok else 'FAIL ') + name, flush=True)
    if not ok: failed.append(name)
if failed: raise SystemExit('failed transport refusals: ' + ', '.join(failed))
