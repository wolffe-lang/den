#!/usr/bin/env python3
"""Discovery redirects must not forward credentials across origins."""
import base64
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading

client = str(Path(sys.argv[1]).resolve())
output = Path(sys.argv[2]); output.mkdir(parents=True, exist_ok=True)
token = secrets.token_hex(24)
encoded = base64.b64encode(('x-access-token:' + token).encode())

class Peer:
    def __init__(self, callback):
        self.callback = callback
        self.socket = socket.socket(); self.socket.bind(('127.0.0.1', 0)); self.socket.listen(4)
        self.socket.settimeout(0.2)
        self.port = self.socket.getsockname()[1]
        self.stopped = threading.Event(); self.seen = []; self.errors = []
        self.thread = threading.Thread(target=self.serve); self.thread.start()
    def serve(self):
        try:
            while not self.stopped.is_set():
                try: connection = self.socket.accept()[0]
                except socket.timeout: continue
                with connection:
                    connection.settimeout(10)
                    while not self.stopped.is_set():
                        data = b''
                        while not data.endswith(b'\r\n\r\n'):
                            piece = connection.recv(1)
                            if not piece: break
                            data += piece
                            if len(data) > 16384: raise RuntimeError('request limit')
                        if not data: break
                        path = data.split(b' ', 2)[1].decode()
                        auth = b'\r\nAuthorization:' in data
                        self.seen.append(dict(path=path, authenticated=auth))
                        connection.sendall(self.callback(path, auth))
        except Exception as exc:
            self.errors.append(type(exc).__name__)
    def close(self):
        self.stopped.set(); self.thread.join(12); self.socket.close()
        assert not self.thread.is_alive(), 'peer did not stop'

def response(status, location=None):
    return (f'HTTP/1.1 {status}\r\nContent-Length: 0\r\n' +
            (f'Location: {location}\r\n' if location else '') + '\r\n').encode()

def challenge():
    return b'HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\nWWW-Authenticate: Basic realm="fixture"\r\n\r\n'

results = []; failed = []
for kind in ['same-origin', 'loop', 'scheme', 'cross-origin-auth']:
    other = Peer(lambda path, auth: challenge())
    def route(path, auth):
        if path == '/probe': return response('404 Not Found')
        if kind == 'loop': return response('301 Moved', '/repo/info/refs?service=git-upload-pack')
        if kind == 'scheme': return response('302 Moved', 'https://127.0.0.1/repo/info/refs?service=git-upload-pack')
        if kind == 'cross-origin-auth':
            if not auth: return challenge()
            return response('301 Moved', f'http://127.0.0.1:{other.port}/repo/info/refs?service=git-upload-pack')
        if path == '/repo/info/refs?service=git-upload-pack':
            return response('301 Moved', '/moved/info/refs?service=git-upload-pack')
        return response('200 OK')
    origin = Peer(route)
    try:
        env = {**os.environ, 'DEN_HTTP_TOKEN': token, 'DEN_TEST_HTTP_URL': f'http://127.0.0.1:{origin.port}/repo', 'DEN_TEST_HTTP_DISCOVER': 'git-upload-pack', 'DEN_TEST_HTTP_COUNT': '1'}
        run = subprocess.run([client], env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    finally:
        origin.close(); other.close()
    ok = not origin.errors and not other.errors
    if kind == 'same-origin':
        ok = ok and run.returncode == 0 and run.stdout == b'status=200 bytes=0 round=0\n' and len(origin.seen) == 2
    else:
        phrase = {'loop': b'HTTP redirect limit', 'scheme': b'HTTP redirect changes scheme', 'cross-origin-auth': b'HTTP cross-origin authentication refused'}[kind]
        ok = ok and run.returncode != 0 and phrase in run.stderr
    if kind == 'cross-origin-auth':
        ok = ok and len(origin.seen) == 2 and origin.seen[-1]['authenticated'] and len(other.seen) == 1 and not other.seen[0]['authenticated']
    assert token.encode() not in run.stdout + run.stderr and encoded not in run.stdout + run.stderr, 'secret leaked'
    results.append(dict(row=kind, code=run.returncode, stdout=run.stdout.hex(), stderr=run.stderr.hex(), origin=origin.seen, other=other.seen))
    (output/'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(('PASS ' if ok else 'FAIL ') + 'http-redirect-' + kind, flush=True)
    if not ok: failed.append(kind)
if failed: raise SystemExit('failed redirects: ' + ', '.join(failed))
