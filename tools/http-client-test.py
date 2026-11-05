#!/usr/bin/env python3
"""Independent raw HTTP peer. No HTTP/TLS implementation source is consumed.
Run only inside the oracle container. All ports are ephemeral loopback sockets.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import threading


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--client', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    captures = []
    failures = []

    def row(name, responses, expected=None, error=None, split=False):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(2)
        listener.settimeout(15)
        port = listener.getsockname()[1]
        requests = []
        server_errors = []

        def serve():
            try:
                with listener:
                    # Multiple requests must reuse this single connection.
                    with listener.accept()[0] as peer:
                        peer.settimeout(15)
                        for response in responses:
                            request = b''
                            while not request.endswith(b'\r\n\r\n'):
                                part = peer.recv(1)
                                if not part:
                                    raise RuntimeError('request ended before headers')
                                request += part
                                if len(request) > 65536:
                                    raise RuntimeError('oversized request')
                            requests.append(request.decode('ascii'))
                            try:
                                if split:
                                    for b in response:
                                        peer.sendall(bytes([b]))
                                else:
                                    peer.sendall(response)
                            except (BrokenPipeError, ConnectionResetError):
                                if error is None:
                                    raise
            except Exception as exc:
                server_errors.append(str(exc))

        server = threading.Thread(target=serve)
        server.start()
        env = {**os.environ, 'DEN_TEST_HTTP_URL': f'http://127.0.0.1:{port}',
               'DEN_TEST_HTTP_COUNT': str(len(responses))}
        result = subprocess.run([args.client], env=env, capture_output=True, timeout=30)
        server.join(timeout=20)
        assert not server.is_alive(), 'fixture thread did not finish'
        capture = dict(row=name, exit=result.returncode, stdout=result.stdout.hex(),
                       stderr=result.stderr.hex(), requests=requests, server_errors=server_errors)
        captures.append(capture)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(captures, indent=2) + '\n')
        ok = not server_errors
        if error is None:
            ok = ok and result.returncode == 0 and result.stdout == expected and not result.stderr
        else:
            ok = ok and result.returncode != 0 and error.encode() in result.stderr
        for request in requests:
            ok = ok and request.startswith('GET /probe HTTP/1.1\r\n')
            ok = ok and f'Host: 127.0.0.1:{port}\r\n' in request
            ok = ok and 'Authorization:' not in request
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok:
            failures.append(name)

    row('http-content-length', [b'HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\na\x00\xff'],
        b'status=200 bytes=3 round=0\na\x00\xff', split=True)
    row('http-chunked-body', [b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n'
                             b'2; pad="a;b"\r\nab\r\n3\r\nc\x00\xff\r\n0\r\nX-End: yes\r\n\r\n'],
        b'status=200 bytes=5 round=0\nabc\x00\xff', split=True)
    row('http-persistent', [b'HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\na',
                            b'HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\nb'],
        b'status=200 bytes=1 round=0\nastatus=200 bytes=1 round=1\nb')
    row('http-empty-chunked', [b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n'],
        b'status=200 bytes=0 round=0\n')
    row('http-close-delimited', [b'HTTP/1.0 200 OK\r\n\r\nabc'],
        b'status=200 bytes=3 round=0\nabc')
    row('http-informational', [b'HTTP/1.1 103 Early Hints\r\n\r\nHTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\na'],
        b'status=200 bytes=1 round=0\na')
    for name, response in [
        ('http-truncated-chunk', b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n4\r\nabc'),
        ('http-lying-content-length', b'HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nabc'),
        ('http-truncated-header', b'HTTP/1.1 200 OK\r\nContent-Length: 4'),
        ('http-missing-last-chunk', b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n3\r\nabc\r\n'),
    ]:
        row(name, [response], error='truncated')
    row('http-bad-chunk-crlf', [b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n3\r\nabcXX0\r\n\r\n'], error='invalid')
    row('http-oversize-header', [b'HTTP/1.1 200 OK\r\nX-Pad: ' + b'x' * 8193 + b'\r\n\r\n'], error='limit')
    row('http-conflicting-length', [b'HTTP/1.1 200 OK\r\nContent-Length: 1\r\nContent-Length: 2\r\n\r\nxx'], error='conflicting Content-Length')
    row('http-chunk-overflow', [b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\nFFFFFFFFFFFFFFFFFFFFFFFF\r\n'], error='limit')
    if failures:
        raise SystemExit('failed rows: ' + ', '.join(failures))


if __name__ == '__main__':
    main()
