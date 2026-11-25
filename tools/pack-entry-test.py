#!/usr/bin/env python3
"""Corrupt pack entries read beside Git: every refusal named, never a trap, a hang or a read past the entries.

A repository holding a stored, a fixed-Huffman and a dynamic-Huffman blob is packed by Git twice: once with no
deltas, and once with offset-delta chains. Each variant damages one entry of the no-delta pack and re-signs that
entry's idx CRC over the damage, so the read reaches the inflater however den orders its checks. Where the
damage changes the entry's length, every later offset moves with it. The pack and the idx are re-signed so their
own checksums are right:

  block-type        the stream's first block type set to the reserved value
  distance          a stream whose first symbol copies from before the output's start
  length-code       a stream whose first symbol is the reserved length code 286
  adler             one bit of the stream's Adler-32 flipped
  size-under        the entry's declared size one less than the stream's output
  size-over         the entry's declared size one more than the stream's output
  cut-at-end        the last entry's stream cut by three bytes, so it would need the trailer's bytes
  size-400m         the entry's declared size 400 MiB, far more than its stream can make

For each, `cat-file -p` of the damaged object must exit as Git's does, and den's refusal must be the named one in
EXPECTED. An undamaged object read from the same pack must answer as Git's does, byte for byte.

Then the sweep: one bit flipped at each byte of four entries' streams, a stored, a fixed and a dynamic blob in
the no-delta pack and an offset-delta entry in the delta pack, once with the entry's idx CRC re-signed and once
with it left as it was. Each read of the damaged object must:
  - never end by a signal, nor run past its timeout;
  - when Git refuses, be refused by den with a named refusal (`Unsupported(pack ...)` or a `limit:`);
  - when den answers, answer as Git does, byte for byte;
  - when Git answers and den refuses, be refused as `pack entry CRC` (the CRC left as it was: a flipped bit the
    stream never reads) or as `pack object identity`, the two checks Git's read does not make.
"""
import argparse
import hashlib
import os
from pathlib import Path
import random
import shutil
import struct
import subprocess
import zlib

EXPECTED = {
    'block-type': 'pack zlib invalid',
    'distance': 'pack zlib invalid',
    'length-code': 'pack zlib invalid',
    'adler': 'pack zlib checksum',
    'size-under': 'pack zlib limit',
    'size-over': 'pack entry size or trailing bytes',
    'cut-at-end': 'pack zlib truncated',
    'size-400m': 'pack entry size or trailing bytes',
}
NAMED = (b'Unsupported(pack ', b'limit: ')
TIMEOUT = 30


def u32(n):
    return struct.pack('>I', n)


def entry_header(kind, size):
    out = bytearray()
    b = (kind << 4) | (size & 15)
    size >>= 4
    while size:
        out.append(b | 128)
        b = size & 127
        size >>= 7
    out.append(b)
    return bytes(out)


class Bits:
    """An RFC 1951 bit writer: values least significant bit first, Huffman codes most significant bit first."""

    def __init__(self):
        self.bits = []

    def put(self, value, width):
        self.bits.extend((value >> n) & 1 for n in range(width))

    def code(self, value, width):
        self.bits.extend((value >> n) & 1 for n in reversed(range(width)))

    def fixed(self, s):
        if s < 144:
            self.code(48 + s, 8)
        elif s < 256:
            self.code(400 + s - 144, 9)
        elif s < 280:
            self.code(s - 256, 7)
        else:
            self.code(192 + s - 280, 8)

    def data(self):
        return bytes(sum(self.bits[i + j] << j for j in range(min(8, len(self.bits) - i)))
                     for i in range(0, len(self.bits), 8))


def fixed_stream(symbols):
    """A zlib stream of one final fixed-Huffman block: each symbol a literal/length (with its distance code)."""
    b = Bits()
    b.put(1, 1)
    b.put(1, 2)
    for s in symbols:
        if isinstance(s, tuple):
            b.fixed(s[0])
            b.code(s[1], 5)
        else:
            b.fixed(s)
    return b'\x78\x01' + b.data() + u32(1)


class Pack:
    """A pack and its idx, parsed enough to rewrite one entry and re-sign both."""

    def __init__(self, pack, idx):
        self.pack, self.idx = pack, idx
        self.count = struct.unpack_from('>I', idx, 1028)[0]
        self.names = [idx[1032 + 20 * i:1052 + 20 * i].hex() for i in range(self.count)]
        self.crc_table = 1032 + 20 * self.count
        self.off_table = 1032 + 24 * self.count
        self.offsets = [struct.unpack_from('>I', idx, self.off_table + 4 * i)[0] for i in range(self.count)]
        self.order = sorted(range(self.count), key=lambda i: self.offsets[i])
        self.end = len(pack) - 20

    def span(self, slot):
        """(kind, size, header end, entry end) of slot's entry, its end from the next offset."""
        o = self.offsets[slot]
        r = self.order.index(slot)
        nxt = self.offsets[self.order[r + 1]] if r + 1 < self.count else self.end
        b = self.pack[o]
        kind, size, shift, pos = (b >> 4) & 7, b & 15, 4, o + 1
        while b & 128:
            b = self.pack[pos]
            size |= (b & 127) << shift
            shift += 7
            pos += 1
        if kind == 6:
            b = self.pack[pos]
            pos += 1
            while b & 128:
                b = self.pack[pos]
                pos += 1
        return kind, size, pos, nxt

    def rewrite(self, slot, entry, resign=True):
        """(pack, idx) with slot's entry replaced by entry: later offsets moved, slot's CRC re-signed if asked."""
        o = self.offsets[slot]
        old_end = self.span(slot)[3]
        delta = len(entry) - (old_end - o)
        body = self.pack[:o] + entry + self.pack[old_end:self.end]
        pack = body + hashlib.sha1(body).digest()
        idx = bytearray(self.idx)
        for i in range(self.count):
            if self.offsets[i] > o and delta:
                assert self.span(i)[0] != 6, 'an offset delta cannot move'
                idx[self.off_table + 4 * i:self.off_table + 4 * i + 4] = u32(self.offsets[i] + delta)
        if resign:
            idx[self.crc_table + 4 * slot:self.crc_table + 4 * slot + 4] = u32(zlib.crc32(entry) & 0xffffffff)
        idx[-40:-20] = pack[-20:]
        idx = bytes(idx[:-20]) + hashlib.sha1(bytes(idx[:-20])).digest()
        return pack, idx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--dev-oracle', action='store_true', help='Darwin development evidence only; not the pinned Linux oracle')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target' / ('pack-entry-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    digest = hashlib.sha256(Path(git).read_bytes()).hexdigest()
    if a.dev_oracle:
        assert os.uname().sysname == 'Darwin', 'development oracle is Darwin-only'
        print('DEV ORACLE (not pinned Linux evidence):', digest, flush=True)
    else:
        assert digest == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = str(root / 'target' / a.tier / 'den')
    env = dict(os.environ, GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
               GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid')

    def run(args, cwd):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, env=env)
        assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p.stdout

    def read(tool, repo, name):
        try:
            p = subprocess.run([tool, 'cat-file', '-p', name], cwd=repo, capture_output=True, env=env, timeout=TIMEOUT)
            return p.returncode, p.stdout, p.stderr
        except subprocess.TimeoutExpired:
            return 'timeout', b'', b''

    rng = random.Random(0x656e7472)
    seed = out / 'seed'
    run([git, 'init', '-q', '-b', 'main', seed], out)
    files = {'stored.bin': rng.randbytes(600),
             'fixed.txt': b'den reads\n',
             'dynamic.txt': b''.join(b'line %d of the dynamic blob, %s\n' % (i, b'xyz' * (i % 5)) for i in range(60))}
    for i, (path, data) in enumerate(files.items()):
        (seed / path).write_bytes(data)
        run([git, 'add', path], seed)
        run([git, 'commit', '-q', '--date', f'{1700000000 + 60 * i} +0000', '-m', f'add {path}'], seed)
    (seed / 'dynamic.txt').write_bytes(files['dynamic.txt'] + b'one more line\n')
    run([git, 'commit', '-q', '-a', '--date', '1700000600 +0000', '-m', 'grow'], seed)
    blob = {path: run([git, 'rev-parse', f'HEAD:{path}'], seed).decode().strip() for path in files}
    first_dynamic = run([git, 'rev-parse', 'HEAD~1:dynamic.txt'], seed).decode().strip()

    def packed(name, args):
        repo = out / name
        shutil.copytree(seed, repo)
        run([git, '-c', 'gc.writeCommitGraph=false', '-c', 'repack.writeBitmaps=false', 'repack', '-adq', *args], repo)
        run([git, 'prune-packed'], repo)
        idx = list((repo / '.git/objects/pack').glob('*.idx'))
        assert len(idx) == 1, idx
        return repo, idx[0]

    plain_repo, plain_idx = packed('plain', ['-f', '--window=0', '--depth=0'])
    delta_repo, delta_idx = packed('delta', ['-f', '--window=10', '--depth=10'])
    plain = Pack(plain_idx.with_suffix('.pack').read_bytes(), plain_idx.read_bytes())
    delta = Pack(delta_idx.with_suffix('.pack').read_bytes(), delta_idx.read_bytes())
    slot = {path: plain.names.index(name) for path, name in blob.items()}
    assert all(plain.span(i)[0] != 6 for i in range(plain.count)), 'the plain pack has a delta'
    ofs = [i for i in range(delta.count) if delta.span(i)[0] == 6]
    assert ofs, 'the delta pack has no offset delta'
    rows = []

    def row(name, ok, detail=''):
        rows.append(ok)
        print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else ': ' + detail), flush=True)

    def install(base_repo, base_idx, name, pack, idx):
        repo = out / name
        shutil.copytree(base_repo, repo)
        p = repo / '.git/objects/pack' / base_idx.with_suffix('.pack').name
        i = repo / '.git/objects/pack' / base_idx.name
        os.chmod(p, 0o644)
        os.chmod(i, 0o644)
        p.write_bytes(pack)
        i.write_bytes(idx)
        return repo

    # The targeted variants, on the dynamic blob unless the damage needs the last entry.
    s = slot['dynamic.txt']
    kind, size, hend, eend = plain.span(s)
    o = plain.offsets[s]
    head, stream = plain.pack[o:hend], plain.pack[hend:eend]
    last = plain.order[-1]
    lkind, lsize, lhend, leend = plain.span(last)
    cases = {
        'block-type': (s, head + stream[:2] + bytes([stream[2] | 6]) + stream[3:]),
        'distance': (s, head + fixed_stream([(257, 0), 256])),
        'length-code': (s, head + fixed_stream([286, 256])),
        'adler': (s, head + stream[:-1] + bytes([stream[-1] ^ 1])),
        'size-under': (s, entry_header(kind, size - 1) + stream),
        'size-over': (s, entry_header(kind, size + 1) + stream),
        'cut-at-end': (last, plain.pack[plain.offsets[last]:leend - 3]),
        'size-400m': (s, entry_header(kind, 400 << 20) + stream),
    }
    assert len(entry_header(kind, size - 1)) == len(head) == len(entry_header(kind, size + 1))
    for name, (target, entry) in cases.items():
        pack, idx = plain.rewrite(target, entry)
        repo = install(plain_repo, plain_idx, 'case-' + name, pack, idx)
        damaged = plain.names[target]
        g, d = read(git, repo, damaged), read(den, repo, damaged)
        want = ('Unsupported(' + EXPECTED[name] + ')').encode()
        ok = g[0] != 0 and d[0] == g[0] and want in d[2]
        row(f'entry-{name}-read', ok, f'git {g[0]} {g[2][-120:]!r} den {d[0]} {d[2][-160:]!r} want {want!r}')
        other = blob['fixed.txt'] if damaged != blob['fixed.txt'] else blob['stored.bin']
        g, d = read(git, repo, other), read(den, repo, other)
        row(f'entry-{name}-untouched', g[0] == 0 and d == g, f'git {g[0]} den {d[0]} {d[2][-160:]!r}')

    # The sweep.
    def sweep(label, base, base_repo, base_idx, target):
        _, _, hend, eend = base.span(target)
        o = base.offsets[target]
        counts = dict(same=0, refused=0, crc=0, identity=0)
        bad = []
        for resign in (True, False):
            for pos in range(hend, eend):
                entry = bytearray(base.pack[o:eend])
                entry[pos - o] ^= 1 << (pos % 8)
                pack, idx = base.rewrite(target, bytes(entry), resign)
                repo = install(base_repo, base_idx, f'sweep-{label}', pack, idx)
                name = base.names[target]
                g, d = read(git, repo, name), read(den, repo, name)
                shutil.rmtree(repo)
                where = f'{label} byte {pos - hend} {"re-signed" if resign else "CRC as it was"}'
                if not isinstance(d[0], int) or d[0] < 0 or d[0] > 128:
                    bad.append(f'{where}: den ended {d[0]} {d[2][-120:]!r}')
                elif g[0] != 0 and d[0] == 0:
                    bad.append(f'{where}: Git refused, den answered')
                elif d[0] != 0 and not any(n in d[2] for n in NAMED):
                    bad.append(f'{where}: an unnamed refusal {d[2][-160:]!r}')
                elif d[0] == 0 and d[1] != g[1]:
                    bad.append(f'{where}: den answered other bytes than Git')
                elif g[0] == 0 and d[0] != 0:
                    if b'Unsupported(pack entry CRC)' in d[2] and not resign:
                        counts['crc'] += 1
                    elif b'Unsupported(pack object identity)' in d[2]:
                        counts['identity'] += 1
                    else:
                        bad.append(f'{where}: Git answered, den refused {d[2][-160:]!r}')
                elif d[0] == 0:
                    counts['same'] += 1
                else:
                    counts['refused'] += 1
        row(f'entry-sweep-{label}', not bad, '; '.join(bad[:5]) + (f' (+{len(bad) - 5} more)' if len(bad) > 5 else ''))
        print(f'  sweep {label}: {counts}', flush=True)

    for path, label in (('stored.bin', 'stored'), ('fixed.txt', 'fixed'), ('dynamic.txt', 'dynamic')):
        sweep(label, plain, plain_repo, plain_idx, slot[path])
    sweep('ofs-delta', delta, delta_repo, delta_idx, ofs[0])
    failures = rows.count(False)
    print(f'pack-entry: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
