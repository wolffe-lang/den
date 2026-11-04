#!/usr/bin/env python3
"""Mac-to-peer SSH interop with an explicitly planned host, owned root and pinned
Git service. No Mac Git is an oracle here: expected canonical bodies/refs come
from the pinned server, independently checked with zlib/SHA-1. A reservation
owns its CPU slot.
"""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import selectors
import shutil
import subprocess
import sys
import zlib

# vc16's recorded peer, and tools/gate-record's fallback host. The host applies
# only when the plan names none (DEN_SSH_HOST); the owner check only when the
# plan names no root (DEN_SSH_PEER_ROOT).
LEGACY_HOST, LEGACY_OWNER = 'kasumi', '/lanes/vc16/'


def planned_peer(host, peer_root, environ):
    """Refuse, before any network access, a peer the explicit plan did not name."""
    planned_host = environ.get('DEN_SSH_HOST') or LEGACY_HOST
    planned_root = environ.get('DEN_SSH_PEER_ROOT') or None
    if not isinstance(host, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', host):
        raise ValueError('ssh peer plan: invalid host')
    if host != planned_host:
        raise ValueError('ssh peer plan mismatch: host is not the planned host')
    if not peer_root or not peer_root.startswith('/') or any(c in peer_root for c in (' ', "'", '\n', '\r', '\0')):
        raise ValueError('ssh peer plan: unsafe root')
    if posixpath.normpath(peer_root) != peer_root or peer_root.startswith('//'):
        raise ValueError('ssh peer owner escape: root is not normalized')
    parts = peer_root.split('/')[1:]
    if not any(part == 'lanes' and re.fullmatch(r'[a-z][a-z0-9_-]*', parts[i + 1]) for i, part in enumerate(parts[:-2])):
        raise ValueError('ssh peer owner escape: root is not inside a lane')
    if planned_root is None:
        if LEGACY_OWNER not in peer_root:
            raise ValueError('ssh peer plan mismatch: no planned root, and root is not the vc16 default')
    elif peer_root != planned_root:
        raise ValueError('ssh peer plan mismatch: root is not the planned root')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default=os.environ.get('DEN_SSH_HOST') or LEGACY_HOST)
    parser.add_argument('--peer-root', default=os.environ.get('DEN_SSH_PEER_ROOT'))
    parser.add_argument('--tier', default='native')
    parser.add_argument('--reservation-token', default=os.environ.get('DEN_SSH_RESERVATION_TOKEN'))
    a = parser.parse_args()
    try:
        planned_peer(a.host, a.peer_root, os.environ)
    except ValueError as error:
        print('ssh-test: ' + str(error), file=sys.stderr, flush=True)
        return 2
    root = Path(__file__).resolve().parent.parent
    out = root / 'target/runs' / ('wire-ssh-' + a.tier)
    out.mkdir(parents=True, exist_ok=True)
    den = str(root / 'target' / a.tier / 'den')
    options = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'UpdateHostKeys=no',
               '-o', 'ControlMaster=no', '-o', 'ControlPath=none', '-o', 'ClearAllForwardings=yes', a.host]
    environment = {k: v for k, v in os.environ.items() if k.startswith(('GIT_', 'DEN_')) or k in ('HOME', 'TZ', 'LC_ALL', 'PATH', 'TMPDIR')}
    captures, rows = [], []
    def retain(argv, data, result, cwd=None):
        captures.append(dict(argv=list(map(str, argv)), cwd=str(cwd or root), environment=environment, stdin=data.hex(), stdout=result.stdout.hex(), stderr=result.stderr.hex(), exit=result.returncode))
        (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')
    def run(argv, data=b''):
        result = subprocess.run(list(map(str, argv)), input=data, capture_output=True, timeout=90)
        retain(argv, data, result)
        return result
    def peer(op, **args):
        argv = [*options, 'python3', '-I', a.peer_root + '/control.py']
        data = json.dumps(dict(op=op, **args)).encode()
        result = run(argv, data)
        assert result.returncode == 0, (argv, result.stderr)
        return json.loads(result.stdout)
    @contextlib.contextmanager
    def reserve():
        if a.reservation_token:
            state = peer('hello')['reservation']
            assert state and state['token'] == a.reservation_token, 'external SSH CPU reservation is not live'
            yield
            return
        argv = [*options, a.peer_root + '/bin/reserve']
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        prefix = b''
        token = os.urandom(32).hex()
        request = (json.dumps(dict(token=token)) + '\n').encode()
        process.stdin.write(request)
        process.stdin.flush()
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while not selector.select(60):
                    assert process.poll() is None, 'SSH slot reservation exited'
                    print('WAIT ssh-peer CPU reservation', flush=True)
                prefix = process.stdout.readline()
            ready = json.loads(prefix)
            assert ready['ready'] and ready['token'] == token, prefix
            yield
        finally:
            process.stdin.close()
            process.stdin = None
            stdout, stderr = process.communicate(timeout=30)
            result = subprocess.CompletedProcess(argv, process.returncode, prefix + stdout, stderr)
            retain(argv, request, result)
            assert process.returncode == 0, (process.returncode, stderr)
    def row(name, operation):
        print('RUN ssh-' + name, flush=True)
        try:
            detail = operation()
            rows.append(dict(name=name, passed=True, detail=detail))
            print('PASS ssh-' + name, flush=True)
        except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as e:
            rows.append(dict(name=name, passed=False, error=str(e)))
            print('FAIL ssh-' + name + ' ' + str(e), flush=True)
        (out / 'summary.json').write_text(json.dumps(dict(rows=rows, zero_skips=True), indent=2) + '\n')
    def url(path, scp=False):
        assert path.startswith(a.peer_root + '/repos/')
        return (a.host + ':' if scp else 'ssh://' + a.host) + path
    def reset_local(name):
        path = out / name
        if path.exists():
            shutil.rmtree(path)
        return path
    def validate(repo, state, bare=True):
        admin = repo if bare else repo / '.git'
        for reference, value in state['refs'].items():
            local = admin / reference
            assert local.read_text().strip() == value, (reference, local)
        for value, body in state['objects'].items():
            encoded = (admin / 'objects' / value[:2] / value[2:]).read_bytes()
            raw = zlib.decompress(encoded)
            expected = body['kind'].encode() + b' ' + str(len(bytes.fromhex(body['data']))).encode() + b'\0' + bytes.fromhex(body['data'])
            assert raw == expected and hashlib.sha1(raw).hexdigest() == value, value
    def local_source(name, state, head):
        repo = reset_local(name)
        result = run([den, 'init', '-q', '--bare', str(repo)])
        assert result.returncode == 0, result.stderr
        for value, body in state['objects'].items():
            data = bytes.fromhex(body['data'])
            raw = body['kind'].encode() + b' ' + str(len(data)).encode() + b'\0' + data
            assert hashlib.sha1(raw).hexdigest() == value
            path = repo / 'objects' / value[:2] / value[2:]
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(zlib.compress(raw, 1))
        (repo / 'refs/heads/main').write_text(head + '\n')
        return repo
    def quiet(result):
        assert result.returncode == 0 and result.stdout == result.stderr == b'', (result.returncode, result.stdout, result.stderr)
    with reserve():
        hello = peer('hello')
        assert hello['root'] == a.peer_root and hello['git_sha256'] == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
        assert hello['control_sha256'] == hashlib.sha256((root / 'tools/ssh-peer.py').read_bytes()).hexdigest()
        upload, receive = a.peer_root + '/bin/upload', a.peer_root + '/bin/receive'
        seed = peer('seed', repo='plain.git')
        first_state = peer('state', repo='plain.git')
        def clone_case(name, remote_name='plain.git', scp=False, bare=True):
            info = seed if remote_name == 'plain.git' else peer('seed', repo=remote_name)
            before = peer('state', repo=remote_name)
            dest = reset_local(name)
            quiet(run([den, 'clone', '-q', *(['--bare'] if bare else []), '--upload-pack=' + upload, url(info['path'], scp), str(dest)]))
            validate(dest, before, bare)
            assert peer('state', repo=remote_name) == before
            if not bare:
                assert (dest / 'a').read_bytes() == b'first\n'
            return dict(remote=info, canonical_objects=len(before['objects']))
        row('clone-uri', lambda: clone_case('clone-uri'))
        row('clone-scp', lambda: clone_case('clone-scp', scp=True))
        row('normal-checkout', lambda: clone_case('normal', bare=False))
        row('space-path', lambda: clone_case('space', 'space repo.git'))
        row('quote-path', lambda: clone_case('quote', "quote'repo.git"))
        row('shell-literal-path', lambda: clone_case('literal', 'semi;true.git'))
        peer('update', repo='plain.git', id=seed['second'])
        second_state = peer('state', repo='plain.git')
        source = local_source('source', second_state, seed['second'])
        def fetch_case():
            dest = local_source('fetch', first_state, seed['first'])
            result = subprocess.run([den, 'fetch', '-q', '--upload-pack=' + upload, url(seed['path']), 'refs/heads/main:refs/heads/main'], cwd=dest, capture_output=True, input=b'', timeout=90)
            retain([den, 'fetch', '-q', '--upload-pack=' + upload, url(seed['path']), 'refs/heads/main:refs/heads/main'], b'', result, dest)
            quiet(result)
            validate(dest, second_state)
            return dict(canonical_objects=len(second_state['objects']))
        row('incremental-fetch', fetch_case)
        def push_case(scp=False):
            remote = 'push-scp.git' if scp else 'push.git'
            target = peer('empty', repo=remote)
            argv = [den, 'push', '-q', '--receive-pack=' + receive, url(target['path'], scp), 'HEAD:refs/heads/main']
            result = subprocess.run(argv, cwd=source, capture_output=True, input=b'', timeout=90)
            retain(argv, b'', result, source)
            quiet(result)
            state = peer('state', repo=remote)
            assert state['refs']['refs/heads/main'] == seed['second'] and state['objects'] == second_state['objects']
            return dict(refs=state['refs'], canonical_objects=len(state['objects']))
        row('push-uri', push_case)
        row('push-scp', lambda: push_case(True))
        rewind = local_source('rewind', second_state, seed['first'])
        def lease_case(expected, succeeds):
            before = peer('state', repo='plain.git')
            argv = [den, 'push', '-q', '--receive-pack=' + receive, '--force-with-lease=refs/heads/main:' + expected, url(seed['path']), 'HEAD:refs/heads/main']
            result = subprocess.run(argv, cwd=rewind, capture_output=True, input=b'', timeout=90)
            retain(argv, b'', result, rewind)
            after = peer('state', repo='plain.git')
            if succeeds:
                quiet(result)
                assert after['refs']['refs/heads/main'] == seed['first']
            else:
                assert result.returncode != 0 and b'stale info' in result.stderr and after == before
            return dict(exit=result.returncode, refs=after['refs'])
        row('stale-lease', lambda: lease_case(seed['first'], False))
        row('matching-lease', lambda: lease_case(seed['second'], True))
        def v0_case():
            dest = reset_local('v0-refusal')
            result = run([den, 'clone', '-q', '--bare', '--upload-pack=' + a.peer_root + '/bin/upload-v0', url(seed['path']), str(dest)])
            assert result.returncode != 0 and b'does not advertise protocol v2' in result.stderr
            return dict(exit=result.returncode, stderr=result.stderr.hex())
        row('v0-refusal', v0_case)
    failures = sum(not r['passed'] for r in rows)
    print(f'ssh interop: {len(rows)} groups, {failures} failures; zero skips', flush=True)
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
