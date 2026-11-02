#!/usr/bin/env python3
"""Independent real-process wire contract, without implementation-source input."""
import argparse
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
    out = root / 'target' / ('wire-' + a.tier)
    out.mkdir(parents=True, exist_ok=True)
    git = os.environ['DEN_GIT']
    assert hashlib.sha256(pathlib.Path(git).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = root / 'target' / a.tier / 'den'
    captures = []

    def run(argv, cwd=None, data=None, ok=True):
        result = subprocess.run(list(map(str, argv)), cwd=cwd, input=data, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=60)
        captures.append(dict(argv=list(map(str, argv)), cwd=str(cwd), stdin=(data or b'').hex(),
                             stdout=result.stdout.hex(), stderr=result.stderr.hex(), exit=result.returncode))
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
            run([den, 'clone', '-q', '--bare', source.as_uri(), dest])
        else:
            upload = out / 'den-upload-pack'
            upload.write_text('#!/bin/sh\nexec "' + str(den) + '" upload-pack "$@"\n')
            upload.chmod(0o755)
            run([git, '-c', 'protocol.version=2', 'clone', '-q', '--bare',
                 '--upload-pack=' + str(upload), source.as_uri(), dest])
        refs = run([git, 'show-ref'], source).stdout
        assert run([git, 'show-ref'], dest).stdout == refs
        run([git, 'fsck', '--full'], dest)
        objects = run([git, 'cat-file', '--batch-all-objects', '--batch-check'], source).stdout
        assert run([git, 'cat-file', '--batch-all-objects', '--batch-check'], dest).stdout == objects
        rows.append(server + ' file clone refs/objects/fsck')
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
            receive = out / 'den-receive-pack'
            receive.write_text('#!/bin/sh\nexec "' + str(den) + '" receive-pack "$@"\n')
            receive.chmod(0o755)
            prefix = [git, 'push', '-q', '--receive-pack=' + str(receive)]
        pushspec = 'refs/heads/main:refs/heads/main'
        run(prefix + [target.as_uri(), pushspec], fixture)
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
    (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')
    (out / 'summary.json').write_text(json.dumps(dict(rows=rows, zero_skips=True), indent=2) + '\n')
    print('wire: ' + ', '.join(rows) + '; zero skips')


if __name__ == '__main__':
    main()
