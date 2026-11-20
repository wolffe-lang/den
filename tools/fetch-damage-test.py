#!/usr/bin/env python3
"""A pull refuses a received object damaged in transit, as Git's does.

A fetch checks every object it receives before any ref moves: each entry of
the received pack is inflated and checked, the pack's trailer is checked, and
the received closure is walked. This row damages one received object in
transit and holds both tools to a refusal; den's must leave the repository as
it was.

The remote is a bare repository one commit ahead. Its upload-pack is reached
through this file's --serve mode, which runs the pinned git-upload-pack and
passes its output through, except the packfile section: one byte of the
entry with the most compressed bytes is flipped, and the pack's trailing
SHA-1 is computed again over the damaged bytes, so only the entry itself is
wrong. Each tool pulls through it (`remote.origin.uploadpack`) and must exit
nonzero; den's pull must leave HEAD, every ref, the index, the work tree and
the object set unchanged, with no temporary pack left (whether Git's keeps
objects it unpacked before the damaged one is printed, not held). A pull
through the plain service then succeeds, so the damage is the only cause.
`--witness-undamaged` passes the pack through unchanged: the refusal row must
then fail by name.
"""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import zlib

GIT_SHA256 = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'


def packets(stream):
    """pkt-lines from a binary stream: (length text, payload or None)."""
    while True:
        head = stream.read(4)
        if not head:
            return
        assert len(head) == 4, head
        size = int(head, 16)
        if size < 4:
            yield head, None
            continue
        payload = stream.read(size - 4)
        assert len(payload) == size - 4
        yield head, payload


def entries(pack):
    """(start of compressed data, its length) for every entry of a v2 pack."""
    assert pack[:4] == b'PACK' and int.from_bytes(pack[4:8], 'big') == 2
    count = int.from_bytes(pack[8:12], 'big')
    pos, out = 12, []
    for _ in range(count):
        b = pack[pos]
        pos += 1
        kind = b >> 4 & 7
        while b & 128:
            b = pack[pos]
            pos += 1
        if kind == 6:
            b = pack[pos]
            pos += 1
            while b & 128:
                b = pack[pos]
                pos += 1
        elif kind == 7:
            pos += 20
        inflater = zlib.decompressobj()
        inflater.decompress(pack[pos:])
        assert inflater.eof
        used = len(pack) - pos - len(inflater.unused_data)
        out.append((pos, used))
        pos += used
    assert pos == len(pack) - 20
    return out


def damage(pack):
    """Flip one byte inside the entry with the most compressed bytes and sum
    the pack again: the trailer is right, the entry is not."""
    start, length = max(entries(pack), key=lambda e: e[1])
    data = bytearray(pack[:-20])
    data[start + length // 2] ^= 0x20
    return bytes(data) + hashlib.sha1(bytes(data)).digest()


def serve(repository, damaging):
    """The pinned git-upload-pack with its packfile section damaged (passed
    through unchanged when not damaging: the row's own red witness)."""
    child = subprocess.Popen(['git-upload-pack', repository], stdout=subprocess.PIPE)
    out = sys.stdout.buffer
    pack, inside = bytearray(), False
    for head, payload in packets(child.stdout):
        if not inside:
            out.write(head + (payload or b''))
            if payload == b'packfile\n':
                inside = True
            out.flush()
            continue
        if payload is None:
            damaged = damage(bytes(pack)) if damaging else bytes(pack)
            for at in range(0, len(damaged), 65515):
                part = b'\x01' + damaged[at:at + 65515]
                out.write(b'%04x' % (len(part) + 4) + part)
            out.write(head)
            out.flush()
            pack, inside = bytearray(), False
        elif payload[:1] == b'\x01':
            pack += payload[1:]
        elif payload[:1] == b'\x03':
            out.write(head + payload)
            out.flush()
    return child.wait()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tier', choices=('native', 'release'))
    p.add_argument('--serve')
    p.add_argument('--pass-through', action='store_true')
    # The row's red witness: the service damages nothing, so den's pull must
    # succeed and the refusal row must fail by name.
    p.add_argument('--witness-undamaged', action='store_true')
    a = p.parse_args()
    if a.serve:
        return serve(a.serve, not a.pass_through)
    root = pathlib.Path(__file__).resolve().parent.parent
    G = os.environ['DEN_GIT']
    assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest() == GIT_SHA256
    den = root / 'target' / a.tier / 'den'
    out = root / 'target' / 'runs' / ('fetch-damage-' + a.tier)
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    captures = []

    def run(argv, cwd, ok=True):
        q = subprocess.run([str(x) for x in argv], cwd=cwd, capture_output=True, timeout=120)
        captures.append(dict(argv=[str(x) for x in argv], cwd=str(cwd), exit=q.returncode,
                             stdout=q.stdout.hex(), stderr=q.stderr.hex()))
        (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')
        if ok:
            assert q.returncode == 0, captures[-1]
        return q

    def git(*args, cwd):
        return run([G, *args], cwd).stdout

    upstream = out / 'upstream'
    git('init', '-q', '-b', 'main', str(upstream), cwd=out)
    for n in range(4):
        (upstream / ('f%d.txt' % n)).write_bytes(b''.join(b'line %d of file %d\n' % (k, n) for k in range(300)))
    git('add', '.', cwd=upstream)
    git('commit', '-qm', 'base', cwd=upstream)
    origin = out / 'origin.git'
    git('clone', '-q', '--bare', '--no-local', str(upstream), str(origin), cwd=out)
    case = out / 'case-template'
    git('clone', '-q', '--no-local', origin.as_uri(), str(case), cwd=out)
    (upstream / 'f1.txt').write_bytes(b''.join(b'changed line %d\n' % k for k in range(400)))
    git('commit', '-qam', 'ahead', cwd=upstream)
    git('push', '-q', str(origin), 'main', cwd=upstream)
    serve_script = out / 'damaging-upload-pack'
    serve_script.write_text('#!/bin/sh\nexec python3 -I -B %s%s --serve "$@"\n'
                            % (pathlib.Path(__file__).resolve(), ' --pass-through' if a.witness_undamaged else ''))
    serve_script.chmod(0o755)

    def state(repo):
        objects = git('cat-file', '--batch-all-objects', '--batch-check', cwd=repo)
        files = {}
        for f in sorted(repo.rglob('*')):
            rel = f.relative_to(repo)
            if f.is_file() and rel.parts[0] != '.git':
                files[str(rel)] = hashlib.sha256(f.read_bytes()).hexdigest()
        temps = sorted(str(f.name) for f in (repo / '.git/objects/pack').iterdir() if not f.name.startswith('pack-'))
        return dict(refs=git('show-ref', '--head', cwd=repo).decode(),
                    index=hashlib.sha256((repo / '.git/index').read_bytes()).hexdigest(),
                    objects=hashlib.sha256(objects).hexdigest(), files=files, temps=temps)

    failed = 0
    for name, exe in (('git', G), ('den', den)):
        repo = out / ('case-' + name)
        shutil.copytree(case, repo, symlinks=True)
        git('config', 'remote.origin.uploadpack', str(serve_script), cwd=repo)
        before = state(repo)
        q = run([exe, 'pull', '--ff-only', 'origin', 'main'], repo, ok=False)
        after = state(repo)
        refused = q.returncode != 0
        unchanged = before == after
        # den must refuse and leave the repository as it was; Git must refuse
        # (whether it kept objects it unpacked before the damaged one is
        # stated, not held).
        ok = refused and (unchanged or name == 'git')
        failed += not ok
        print(('PASS' if ok else 'FAIL'), 'fetch-refuses-damaged-received-object-%s-%s' % (name, a.tier),
              'exit=%d unchanged=%s' % (q.returncode, unchanged),
              'stderr=%r' % q.stderr.decode(errors='replace').strip().splitlines()[-1:], flush=True)
        git('config', '--unset', 'remote.origin.uploadpack', cwd=repo)
        q = run([exe, 'pull', '--ff-only', '-q', 'origin', 'main'], repo, ok=False)
        clean = q.returncode == 0 and git('rev-parse', 'HEAD', cwd=repo) == git('rev-parse', 'main', cwd=origin)
        failed += not clean
        print(('PASS' if clean else 'FAIL'), 'fetch-undamaged-pull-%s-%s' % (name, a.tier),
              'exit=%d' % q.returncode, flush=True)
    print('fetch-damage: %d failures' % failed, flush=True)
    return int(failed > 0)


if __name__ == '__main__':
    raise SystemExit(main())
