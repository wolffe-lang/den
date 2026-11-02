#!/usr/bin/env python3
"""Independent real-process wire contract, without implementation-source input."""
import argparse
import contextlib
import selectors
import hashlib
import json
import os
import pathlib
import shutil
import socket
import subprocess
import time


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tier', default='native')
    a = p.parse_args()
    root = pathlib.Path(__file__).resolve().parent.parent
    out = root / 'target' / 'runs' / ('wire-' + a.tier)
    out.mkdir(parents=True, exist_ok=True)
    git = os.environ['DEN_GIT']
    assert hashlib.sha256(pathlib.Path(git).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = root / 'target' / a.tier / 'den'
    wire_client = root / 'target' / a.tier / 'wire-client'
    captures = []

    def run(argv, cwd=None, data=None, ok=True, env=None):
        result = subprocess.run(list(map(str, argv)), cwd=cwd, input=data, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=60, env={**os.environ, **(env or {})})
        captures.append(dict(argv=list(map(str, argv)), cwd=str(cwd), stdin=(data or b'').hex(),
                             stdout=result.stdout.hex(), stderr=result.stderr.hex(), exit=result.returncode,
                             extra_env=env or {}))
        (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')
        if ok:
            assert result.returncode == 0, captures[-1]
        return result

    fixture = out / 'source'
    if fixture.exists():
        shutil.rmtree(fixture)
    run([git, 'init', '-q', fixture])
    (fixture / 'file').write_text('first\n')
    run([git, 'add', '.'], fixture)
    run([git, 'commit', '-qm', 'first'], fixture)
    first = run([git, 'rev-parse', 'HEAD'], fixture).stdout.strip()
    (fixture / 'file').write_text('first\nsecond\n')
    run([git, 'add', '.'], fixture)
    run([git, 'commit', '-qm', 'second'], fixture)
    run([git, 'tag', '-a', 'v1', '-m', 'tag'], fixture)
    source = out / 'source.git'
    if source.exists():
        shutil.rmtree(source)
    run([git, 'clone', '-q', '--bare', fixture, source])
    rows = []
    for server in ('git', 'den'):
        dest = out / ('clone-' + server + '.git')
        if dest.exists():
            shutil.rmtree(dest)
        if server == 'git':
            result = run([den, 'clone', '-q', '--bare', source.as_uri(), dest])
        else:
            upload = root / 'target' / a.tier / 'upload-service'
            result = run([git, '-c', 'protocol.version=2', 'clone', '-q', '--bare',
                          '--upload-pack=' + str(upload), source.as_uri(), dest])
        assert result.stdout == b'' and result.stderr == b'', 'quiet successful clone bytes'
        refs = run([git, 'show-ref'], source).stdout
        assert run([git, 'show-ref'], dest).stdout == refs
        run([git, 'fsck', '--full'], dest)
        objects = run([git, 'cat-file', '--batch-all-objects', '--batch-check'], source).stdout
        assert run([git, 'cat-file', '--batch-all-objects', '--batch-check'], dest).stdout == objects
        rows.append(server + ' file clone refs/objects/fsck')
        normal = out / ('worktree-' + server)
        expected = out / ('worktree-oracle-' + server)
        for path in (normal, expected):
            if path.exists():
                shutil.rmtree(path)
        golden = run([git, 'clone', '-q', source.as_uri(), expected])
        if server == 'git':
            result = run([den, 'clone', '-q', source.as_uri(), normal])
        else:
            result = run([git, '-c', 'protocol.version=2', 'clone', '-q',
                          '--upload-pack=' + str(upload), source.as_uri(), normal])
        assert (result.stdout, result.stderr) == (golden.stdout, golden.stderr), 'normal quiet clone bytes'
        assert run([git, 'show-ref'], normal).stdout == run([git, 'show-ref'], expected).stdout
        assert run([git, 'ls-files', '-s'], normal).stdout == run([git, 'ls-files', '-s'], expected).stdout
        assert run([git, 'status', '--porcelain=v1'], normal).stdout == b''
        assert (normal / 'file').read_bytes() == (expected / 'file').read_bytes()
        run([git, 'fsck', '--full'], normal)
        rows.append(server + ' normal clone refs/index/worktree/fsck')
    api_clone = out / 'api-clone'
    if api_clone.exists():
        shutil.rmtree(api_clone)
    result = run([wire_client, 'clone', source.as_uri(), api_clone])
    assert result.stdout == b'' and result.stderr == b''
    assert run([git, 'show-ref'], api_clone).stdout == run([git, 'show-ref'], expected).stdout
    assert run([git, 'ls-files', '-s'], api_clone).stdout == run([git, 'ls-files', '-s'], expected).stdout
    assert run([git, 'status', '--porcelain=v1'], api_clone).stdout == b''
    rows.append('independent importing normal-clone client')
    self_clone = out / 'den-to-den.git'
    if self_clone.exists():
        shutil.rmtree(self_clone)
    empty_path = out / 'empty-path'
    empty_path.mkdir(exist_ok=True)
    result = run([den, 'clone', '-q', '--bare', source.as_uri(), self_clone],
                 env={'DEN_UPLOAD_PACK': str(root / 'target' / a.tier / 'upload-service'),
                      'PATH': str(empty_path), 'GIT_EXEC_PATH': str(empty_path)})
    assert result.stdout == b'' and result.stderr == b''
    assert run([git, 'show-ref'], self_clone).stdout == run([git, 'show-ref'], source).stdout
    run([git, 'fsck', '--full'], self_clone)
    rows.append('den-to-den native file services, no shell or Git service executable')

    def pkt(data):
        assert len(data) <= 65516
        return f'{len(data) + 4:04x}'.encode() + data

    def packets(data):
        pos = 0
        result = []
        while pos < len(data):
            assert len(data) - pos >= 4
            size = int(data[pos:pos + 4], 16)
            assert size != 3 and size <= 65520
            if size < 4:
                result.append((size, b''))
                pos += 4
            else:
                assert size <= len(data) - pos
                result.append((4, data[pos + 4:pos + size]))
                pos += size
        return result

    tip = run([git, 'rev-parse', 'refs/heads/main'], source).stdout.strip()
    tag = run([git, 'rev-parse', 'refs/tags/v1'], source).stdout.strip()
    request = (pkt(b'command=fetch\n') + b'0001' + pkt(b'include-tag\n') +
               pkt(b'no-progress\n') + pkt(b'ofs-delta\n') + pkt(b'want ' + tip + b'\n') +
               pkt(b'done\n') + b'00000000')
    generated = run([wire_client, 'request', tip.decode(), '-']).stdout
    canonical_request = (pkt(b'command=fetch\n') + b'0001' + pkt(b'thin-pack\n') + pkt(b'ofs-delta\n') +
                         pkt(b'no-progress\n') + pkt(b'want ' + tip + b'\n') + pkt(b'done\n') + b'0000')
    assert generated == canonical_request, 'outbound want includes newline'
    rows.append('independent canonical outbound request bytes')
    for server in ('git', 'den', 'git-no-lf', 'den-no-lf'):
        command = [git, 'upload-pack', source] if server.startswith('git') else [den, 'upload-pack', source]
        incoming = request if not server.endswith('no-lf') else request.replace(pkt(b'want ' + tip + b'\n'), pkt(b'want ' + tip))
        response = run(command, data=incoming, env={'GIT_PROTOCOL': 'version=2'}).stdout
        decoded = packets(response)
        stop = next(i for i, row in enumerate(decoded) if row[0] == 0)
        assert decoded[0] == (4, b'version 2\n')
        response = decoded[stop + 1:]
        assert response[0] == (4, b'packfile\n') and response[-1][0] == 0
        body = b''
        for kind, payload in response[1:-1]:
            assert kind == 4 and payload and payload[0] in (1, 2)
            if payload[0] == 1:
                body += payload[1:]
        assert hashlib.sha1(body[:-20]).digest() == body[-20:]
        target = out / ('include-tag-' + server + '.git')
        if target.exists():
            shutil.rmtree(target)
        run([git, 'init', '-q', '--bare', target])
        run([git, 'index-pack', '--stdin'], target, data=body)
        assert run([git, 'cat-file', '-t', tag.decode()], target).stdout == b'tag\n'
        run([git, 'fsck', '--full'], target)
        rows.append(server + ' include-tag without a tag want, independent pkt parser/index-pack')
    dest = out / 'clone-git.git'
    spec = 'refs/heads/main:refs/heads/copied'
    run([den, 'fetch', '-q', source.as_uri(), spec], dest)
    run([git, 'update-ref', 'refs/heads/main', first.decode()], source)
    before = run([git, 'show-ref'], dest).stdout
    refused = run([den, 'fetch', '-q', source.as_uri(), spec], dest, ok=False)
    assert refused.returncode != 0, 'non-fast-forward fetch must refuse'
    assert run([git, 'show-ref'], dest).stdout == before, 'refusal must preserve refs'
    run([den, 'fetch', '-q', source.as_uri(), '+' + spec], dest)
    assert run([git, 'rev-parse', 'refs/heads/copied'], dest).stdout.strip() == first
    rows.append('fetch refspec creation/non-fast-forward refusal/force')
    for client in ('git', 'den'):
        target = out / ('push-' + client + '.git')
        if target.exists():
            shutil.rmtree(target)
        run([git, 'init', '-q', '--bare', target])
        prefix = [den, 'push', '-q']
        if client == 'git':
            receive = root / 'target' / a.tier / 'receive-service'
            prefix = [git, 'push', '-q', '--receive-pack=' + str(receive)]
        pushspec = 'refs/heads/main:refs/heads/main'
        result = run(prefix + [target.as_uri(), pushspec], fixture)
        assert result.stdout == b'' and result.stderr == b'', 'quiet successful push bytes'
        tip = run([git, 'rev-parse', 'HEAD'], fixture).stdout
        assert run([git, 'rev-parse', 'refs/heads/main'], target).stdout == tip
        run([git, 'fsck', '--full'], target)
        run([git, 'update-ref', 'refs/heads/old', first.decode()], fixture)
        before = run([git, 'show-ref'], target).stdout
        oldspec = 'refs/heads/old:refs/heads/main'
        assert run(prefix + [target.as_uri(), oldspec], fixture, ok=False).returncode != 0
        assert run([git, 'show-ref'], target).stdout == before
        run(prefix + ['--force', target.as_uri(), oldspec], fixture)
        assert run([git, 'rev-parse', 'refs/heads/main'], target).stdout.strip() == first
        run([git, 'update-ref', 'refs/heads/remove', first.decode()], target)
        run(prefix + [target.as_uri(), oldspec, ':refs/heads/remove'], fixture)
        assert run([git, 'show-ref', '--verify', '--quiet', 'refs/heads/remove'], target, ok=False).returncode != 0
        assert run([git, 'rev-parse', 'refs/heads/main'], target).stdout.strip() == first
        rows.append(client + ' delete-only wire request mixed with an unchanged positive refspec')
        before = run([git, 'show-ref'], target).stdout
        assert run(prefix + [target.as_uri(), ':refs/heads/remove'], fixture, ok=False).returncode != 0
        assert run([git, 'show-ref'], target).stdout == before
        rows.append(client + ' nonexistent deletion is an immutable refusal')
        rows.append(client + ' file push/create/non-fast-forward refusal/force/fsck')
        run(prefix + ['--atomic', target.as_uri(),
                      'refs/heads/main:refs/heads/atomic-a',
                      'refs/heads/main:refs/heads/atomic-b'], fixture)
        run([git, 'config', 'receive.denyNonFastForwards', 'true'], target)
        before = run([git, 'show-ref'], target).stdout
        failed = run(prefix + ['--atomic', '--force', target.as_uri(),
                              'refs/heads/old:refs/heads/atomic-a',
                              'refs/heads/main:refs/heads/atomic-c'], fixture, ok=False)
        assert failed.returncode != 0
        assert run([git, 'show-ref'], target).stdout == before
        rows.append(client + ' atomic success/late-policy-rejection all refs unchanged')
        if client == 'git':
            run([git, 'config', 'core.logAllRefUpdates', 'true'], target)
            advertisement = packets(run([den, 'receive-pack', target], data=b'0000').stdout)
            offered = advertisement[0][1].split(b'\0')[1].split()
            assert b'atomic' not in offered, 'do not advertise an unimplemented atomic reflog policy'
            run([git, 'config', 'core.logAllRefUpdates', 'false'], target)
            rows.append('den withdraws atomic for the named unsupported reflog policy')
    self_server = out / 'den-to-den-push.git'
    if self_server.exists():
        shutil.rmtree(self_server)
    run([git, 'init', '-q', '--bare', self_server])
    result = run([den, 'push', '-q', '--atomic', self_server.as_uri(),
                  'HEAD:refs/heads/a', 'HEAD:refs/heads/b'], fixture,
                 env={'DEN_RECEIVE_PACK': str(root / 'target' / a.tier / 'receive-service'),
                      'PATH': str(empty_path), 'GIT_EXEC_PATH': str(empty_path)})
    assert result.stdout == b'' and result.stderr == b''
    self_tip = run([git, 'rev-parse', 'HEAD'], fixture).stdout
    for name in ('a', 'b'):
        assert run([git, 'rev-parse', 'refs/heads/' + name], self_server).stdout == self_tip
    run([git, 'fsck', '--full'], self_server)
    rows.append('den-to-den native atomic push service')
    atomic = root / 'target' / a.tier / 'atomic-client'
    tip = run([git, 'rev-parse', 'HEAD'], fixture).stdout.strip().decode()
    for phase in ('prepare', 'old-published', 'loose-removed', 'commit', ''):
        target = out / ('transaction-' + (phase or 'success') + '.git')
        if target.exists():
            shutil.rmtree(target)
        run([git, 'clone', '-q', '--bare', fixture, target])
        for name in ('main', 'second'):
            run([git, 'update-ref', 'refs/heads/' + name, first.decode()], target)
        before = run([git, 'show-ref'], target).stdout
        command = [atomic, target, phase,
                   'refs/heads/main', first.decode(), tip,
                   'refs/heads/second', first.decode(), tip]
        result = run(command, ok=not phase)
        if phase:
            assert result.returncode != 0
            assert run([git, 'show-ref'], target).stdout == before
        else:
            for name in ('main', 'second'):
                assert run([git, 'rev-parse', 'refs/heads/' + name], target).stdout.strip().decode() == tip
        run([git, 'fsck', '--full'], target)
        rows.append('atomic API phase ' + (phase or 'success'))
    @contextlib.contextmanager
    def daemon(server):
        prefix = b''
        if server == 'den':
            argv = [str(den), 'daemon', '--enable-receive-pack', str(out), '0']
        else:
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                port = reservation.getsockname()[1]
            argv = [git, 'daemon', '--reuseaddr', '--export-all', '--enable=receive-pack',
                    '--listen=127.0.0.1', '--port=' + str(port), '--base-path=' + str(out), str(out)]
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            if server == 'den':
                with selectors.DefaultSelector() as ready:
                    ready.register(proc.stdout, selectors.EVENT_READ)
                    assert ready.select(30), 'den daemon startup timeout'
                prefix = proc.stdout.readline()
                assert prefix.startswith(b'port '), prefix
                port = int(prefix.split()[1])
            else:
                for _ in range(100):
                    assert proc.poll() is None, 'git daemon exited at startup'
                    try:
                        with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                            break
                    except OSError:
                        time.sleep(0.1)
                else:
                    raise AssertionError('git daemon startup timeout')
            yield f'git://127.0.0.1:{port}/'
            if server == 'den':
                assert proc.wait(timeout=30) == 0, 'den one-session daemon failed'
        finally:
            if proc.poll() is None:
                proc.terminate()
            stdout, stderr = proc.communicate(timeout=10)
            captures.append(dict(server_argv=argv, pid=proc.pid, stdout=(prefix + stdout).hex(),
                                 stderr=stderr.hex(), exit=proc.returncode, teardown='own pid only'))
            (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')

    (source / 'git-daemon-export-ok').write_bytes(b'')
    for server in ('git', 'den'):
        network = out / ('network-' + server + '.git')
        if network.exists():
            shutil.rmtree(network)
        client = den if server == 'git' else git
        with daemon(server) as base:
            run([client, 'clone', '-q', '--bare', base + source.name, network])
        assert run([git, 'show-ref'], network).stdout == run([git, 'show-ref'], source).stdout
        run([git, 'fsck', '--full'], network)
        (fixture / 'file').write_bytes((fixture / 'file').read_bytes() + ('network-' + server + '\n').encode())
        run([git, 'add', '.'], fixture)
        run([git, 'commit', '-qm', 'network-' + server], fixture)
        run([git, 'push', '-q', source.as_uri(), 'HEAD:refs/heads/network'], fixture)
        with daemon(server) as base:
            run([client, 'fetch', '-q', base + source.name, 'refs/heads/network:refs/heads/network-copy'], network)
        tip = run([git, 'rev-parse', 'HEAD'], fixture).stdout
        assert run([git, 'rev-parse', 'refs/heads/network-copy'], network).stdout == tip
        run([git, 'fsck', '--full'], network)
        target = out / ('network-push-' + server + '.git')
        if target.exists():
            shutil.rmtree(target)
        run([git, 'init', '-q', '--bare', target])
        (target / 'git-daemon-export-ok').write_bytes(b'')
        with daemon(server) as base:
            run([client, 'push', '-q', '--atomic', base + target.name,
                 'HEAD:refs/heads/a', 'HEAD:refs/heads/b'], fixture)
        for name in ('a', 'b'):
            assert run([git, 'rev-parse', 'refs/heads/' + name], target).stdout == tip
        run([git, 'fsck', '--full'], target)
        rows.append(server + ' daemon: clone, incremental fetch and atomic push, refs/objects/fsck')
    (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')
    (out / 'summary.json').write_text(json.dumps(dict(rows=rows, zero_skips=True), indent=2) + '\n')
    print('wire: ' + ', '.join(rows) + '; zero skips')


if __name__ == '__main__':
    main()
