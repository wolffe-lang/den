#!/usr/bin/env python3
"""Black-box pinned-Git pack streams through an independent den import client."""
import argparse
import hashlib
import json
import os
import pathlib
import shutil
import struct
import subprocess
import zlib


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    tier = parser.parse_args().tier
    root = pathlib.Path(__file__).resolve().parent.parent
    out = root / 'target' / 'runs' / ('wire-pack-' + tier)
    out.mkdir(parents=True, exist_ok=True)
    git = os.environ['DEN_GIT']
    assert hashlib.sha256(pathlib.Path(git).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    client = root / 'target' / tier / 'wire-client'
    captures = out / 'captures.jsonl'
    captures.write_bytes(b'')
    count = 0

    def run(argv, cwd=None, data=None, ok=True):
        result = subprocess.run(list(map(str, argv)), cwd=cwd, input=data,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        record = dict(argv=list(map(str, argv)), cwd=str(cwd), stdin=(data or b'').hex(),
                      stdout=result.stdout.hex(), stderr=result.stderr.hex(), exit=result.returncode)
        with captures.open('a') as stream:
            stream.write(json.dumps(record) + '\n')
        if ok:
            assert result.returncode == 0, record
        return result

    def init(path, bare=False):
        if path.exists():
            shutil.rmtree(path)
        run([git, 'init', '-q'] + (['--bare'] if bare else []) + [path])

    def names(path):
        return sorted(run([git, 'cat-file', '--batch-all-objects', '--batch-check=%(objectname)'], path).stdout.splitlines())

    def canonical(path, wanted):
        return run([git, 'cat-file', '--batch'], path, b'\n'.join(wanted) + b'\n').stdout

    def snapshot(path):
        return {str(p.relative_to(path)): [p.stat().st_mode & 0o777, hashlib.sha256(p.read_bytes()).hexdigest()]
                for p in path.rglob('*') if p.is_file()}

    def entries(data):
        assert data[:8] == b'PACK\x00\x00\x00\x02'
        assert hashlib.sha1(data[:-20]).digest() == data[-20:]
        size = struct.unpack('!I', data[8:12])[0]
        pos = 12
        kinds, references = [], []
        for _ in range(size):
            first = data[pos]
            pos += 1
            kind = (first >> 4) & 7
            length, shift = first & 15, 4
            while first & 128:
                first = data[pos]
                pos += 1
                length |= (first & 127) << shift
                shift += 7
            if kind == 6:
                value = data[pos]
                pos += 1
                while value & 128:
                    value = data[pos]
                    pos += 1
            elif kind == 7:
                references.append(data[pos:pos + 20].hex().encode())
                pos += 20
            else:
                assert kind in (1, 2, 3, 4)
            decoder = zlib.decompressobj()
            body = decoder.decompress(data[pos:], length + 1)
            assert decoder.eof and len(body) == length
            pos += len(data) - pos - len(decoder.unused_data)
            kinds.append(kind)
        assert pos == len(data) - 20
        return kinds, references

    source = out / 'source'
    init(source)
    payload = b''.join(hashlib.sha256(str(i).encode()).digest() for i in range(4096))
    (source / 'payload').write_bytes(payload)
    run([git, 'add', '.'], source)
    run([git, 'commit', '-qm', 'base'], source)
    base = run([git, 'rev-parse', 'HEAD'], source).stdout.strip()
    base_blob = run([git, 'rev-parse', 'HEAD:payload'], source).stdout.strip()
    seed = out / 'base.git'
    if seed.exists():
        shutil.rmtree(seed)
    run([git, 'clone', '-q', '--bare', '--no-hardlinks', source, seed])
    (source / 'payload').write_bytes(payload[:64000] + bytes(range(64)) + payload[64064:] + b'end\n')
    run([git, 'add', '.'], source)
    run([git, 'commit', '-qm', 'changed'], source)
    tip = run([git, 'rev-parse', 'HEAD'], source).stdout.strip()
    wanted = names(source)
    expected = canonical(source, wanted)
    rows = []
    for mode in ('none', 'ofs', 'ref', 'thin'):
        flags = ['--no-reuse-object', '--no-reuse-delta']
        if mode == 'none':
            flags += ['--window=0']
        if mode in ('ofs', 'thin'):
            flags += ['--delta-base-offset']
        if mode == 'thin':
            flags += ['--thin']
        revisions = tip + b'\n' + (b'^' + base + b'\n' if mode == 'thin' else b'')
        data = run([git, 'pack-objects', '--stdout', '--revs'] + flags, source, revisions).stdout
        kinds, references = entries(data)
        if mode == 'ofs':
            assert 6 in kinds, 'fixture must contain real OFS deltas'
        if mode == 'ref':
            assert 7 in kinds, 'fixture must contain real REF deltas'
        if mode == 'thin':
            assert base_blob in references, 'fixture must use a real external base'
            sent = run([git, 'rev-list', '--objects', tip.decode(), '^' + base.decode()], source).stdout
            assert base_blob not in {line.split(b' ')[0] for line in sent.splitlines()}
        stream = out / (mode + '.pack')
        stream.write_bytes(data)
        target = out / (mode + '-den.git')
        oracle = out / (mode + '-git.git')
        for path in (target, oracle):
            if mode == 'thin':
                if path.exists():
                    shutil.rmtree(path)
                run([git, 'clone', '-q', '--bare', '--no-hardlinks', seed, path])
            else:
                init(path, bare=True)
        run([client, 'import', target, stream])
        run([git, 'index-pack', '--stdin'] + (['--fix-thin'] if mode == 'thin' else []), oracle, data)
        for path in (target, oracle):
            assert names(path) == wanted
            assert canonical(path, wanted) == expected
            run([git, 'update-ref', 'refs/heads/main', tip.decode()], path)
            run([git, 'fsck', '--full'], path)
        if mode == 'thin':
            empty = out / 'missing-base.git'
            init(empty, bare=True)
            before = snapshot(empty)
            assert run([client, 'import', empty, stream], ok=False).returncode != 0
            assert snapshot(empty) == before
            assert run([git, 'index-pack', '--stdin', '--fix-thin'], empty, data, ok=False).returncode != 0
        rows.append(dict(mode=mode, kinds=kinds, bases=[x.decode() for x in references],
                         bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), objects=len(wanted)))
        count += 1
    # Full decoding must finish before loose publication: corruption at the end
    # of an otherwise valid multi-object stream cannot leave a prefix installed.
    data = bytearray((out / 'ofs.pack').read_bytes())
    data[-1] ^= 1
    mutations = [bytes(data), bytes(data[:-1]), b'PACK' + b'\x00' * 8,
                 b'PACK\x00\x00\x00\x02\x00\x00\x27\x11' + b'\x00' * 20]
    def framed(body, count=1):
        head = b'PACK' + struct.pack('!II', 2, count) + body
        return head + hashlib.sha1(head).digest()
    mutations += [framed(b'\x50' + zlib.compress(b'')), framed(b'\x00' + zlib.compress(b'')),
                  framed(b'\x60\x00' + zlib.compress(b'\x00\x00')),
                  framed(b'\x70' + b'\x00' * 20 + zlib.compress(b'\x00\x00')),
                  framed(b'\x31' + zlib.compress(b'')), framed(b'\x30garbage'),
                  framed(b'\x80' * 12), framed(b'\x30' + zlib.compress(b''), 2),
                  (out / 'ofs.pack').read_bytes() + b'x']
    for i, broken in enumerate(mutations):
        stream = out / f'bad-{i}.pack'
        stream.write_bytes(broken)
        target = out / f'bad-{i}.git'
        init(target, bare=True)
        before = snapshot(target)
        assert run([client, 'import', target, stream], ok=False).returncode != 0
        assert snapshot(target) == before
        oracle = run([git, 'index-pack', '--stdin', '--fix-thin'], target, broken, ok=False)
        # index-pack's stdin interface may leave trailing transport bytes to
        # its caller; den's standalone import API intentionally takes one exact
        # stream. Retain that oracle outcome rather than invent exit parity.
        if i != len(mutations) - 1:
            assert oracle.returncode != 0
        count += 1
    summary = dict(rows=rows, malformed=len(mutations), total=count, zero_skips=True,
                   base=base.decode(), tip=tip.decode(), payload_sha256=hashlib.sha256(payload).hexdigest())
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(f'wire pack streams: {count} modes/refusals; real OFS/REF/thin deltas, canonical bytes, immutable failures; zero skips')


if __name__ == '__main__':
    main()
