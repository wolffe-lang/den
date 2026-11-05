#!/usr/bin/env python3
"""Environment-only synthetic credentials; HTTP peer logs never contain headers."""
import base64
import json
import os
from pathlib import Path
import pty
import secrets
import selectors
import socket
import subprocess
import sys
import termios
import threading

client = str(Path(sys.argv[1]).resolve())
output = Path(sys.argv[2]).resolve()
output.mkdir(parents=True, exist_ok=True)
token = secrets.token_hex(24)
os.environ['DEN_HTTP_TOKEN'] = token
encoded = base64.b64encode(('x-access-token:' + token).encode())
results = []
failed = []
for name in ['environment', 'wrong-token', 'missing-token', 'prompt', 'prompt-cancel']:
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0)); listener.listen(1); listener.settimeout(15)
    port = listener.getsockname()[1]
    observed = []
    errors = []

    def peer():
        try:
            with listener, listener.accept()[0] as connection:
                connection.settimeout(15)
                for turn in range(2):
                    request = b''
                    while not request.endswith(b'\r\n\r\n'):
                        data = connection.recv(1)
                        if not data:
                            return
                        request += data
                        if len(request) > 16384:
                            raise RuntimeError('oversized request')
                    values = [line.split(b':', 1)[1].strip() for line in request.split(b'\r\n') if line.lower().startswith(b'authorization:')]
                    accepted = values == [b'Basic ' + encoded]
                    observed.append((turn, bool(values), accepted))
                    if accepted:
                        connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok')
                    else:
                        connection.sendall(b'HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Basic realm="fixture"\r\nContent-Length: 0\r\n\r\n')
        except Exception as exc:
            errors.append(type(exc).__name__)

    server = threading.Thread(target=peer); server.start()
    env = {**os.environ, 'DEN_TEST_HTTP_URL': f'http://127.0.0.1:{port}', 'DEN_TEST_HTTP_COUNT': '1'}
    if name == 'wrong-token': env['DEN_HTTP_TOKEN'] = 'incorrect-synthetic-token'
    if name in ['missing-token', 'prompt', 'prompt-cancel']: env.pop('DEN_HTTP_TOKEN', None)
    echo = b''
    restored = True
    if name.startswith('prompt'):
        master, slave = pty.openpty()
        before = termios.tcgetattr(slave)
        process = subprocess.Popen([client], stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        selector = selectors.DefaultSelector(); selector.register(process.stderr, selectors.EVENT_READ)
        prefix = b''
        while b'Token: ' not in prefix:
            if not selector.select(15): raise RuntimeError('prompt timeout')
            part = os.read(process.stderr.fileno(), 1024)
            if not part: break
            prefix += part
        if b'Token: ' in prefix:
            os.write(master, b'\x03' if name == 'prompt-cancel' else token.encode() + b'\n')
        stdout, stderr = process.communicate(timeout=30)
        stderr = prefix + stderr
        restored = termios.tcgetattr(slave) == before
        os.set_blocking(master, False)
        try: echo = os.read(master, 8192)
        except (BlockingIOError, OSError): pass
        os.close(master); os.close(slave)
        code = process.returncode
    else:
        process = subprocess.run([client], stdin=subprocess.DEVNULL, capture_output=True, env=env, timeout=30)
        code, stdout, stderr = process.returncode, process.stdout, process.stderr
    server.join(20)
    assert not server.is_alive(), 'HTTP fixture did not finish'
    ok = not errors and restored and not echo and observed and observed[0] == (0, False, False)
    if name in ['environment', 'prompt']:
        ok = ok and code == 0 and stdout == b'status=200 bytes=2 round=0\nok' and observed[-1] == (1, True, True)
    elif name == 'wrong-token':
        ok = ok and code == 0 and stdout == b'status=401 bytes=0 round=0\n' and len(observed) == 2
    else:
        ok = ok and code != 0 and len(observed) == 1 and (b'authentication required' in stderr if name == 'missing-token' else b'authentication cancelled' in stderr)
    # Refuse to persist any capture if its bytes contain literal or encoded secret.
    assert token.encode() not in stdout + stderr + echo and encoded not in stdout + stderr + echo, 'credential leaked'
    results.append(dict(row=name, exit=code, stdout=stdout.hex(), stderr=stderr.hex(), requests=observed, restored=restored, errors=errors))
    (output/'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(('PASS ' if ok else 'FAIL ') + 'http-auth-' + name, flush=True)
    if not ok: failed.append(name)
for file in output.rglob('*'):
    if file.is_file():
        data = file.read_bytes()
        assert token.encode() not in data and encoded not in data, 'credential persisted'
secrecy_exercised = any(row['row'] == 'environment' and row['requests'][-1] == (1, True, True) for row in results)
print(('PASS ' if secrecy_exercised else 'FAIL ') + 'http-auth-token-secrecy', flush=True)
if not secrecy_exercised: failed.append('token-secrecy-not-exercised')
if failed: raise SystemExit('failed auth rows: ' + ', '.join(failed))
