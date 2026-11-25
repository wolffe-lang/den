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

Then what reads cost, from the session's counters (probes/pack-client --read-counts: sorted, resolved, read, the
pack bytes read for the entries, and reserved, the output bytes reserved for them):
  read-counts-no-delta   a read of an object with no delta orders no offsets and resolves none
  read-counts-delta      nor does an offset delta's read: its base's slot is the one its rebuilt identity names
  gap-after-first|last   seven junk bytes after an entry: every read answers as Git's, and fsck and verify-pack
                         fail as Git's do
  unused-bit             a bit the stream never reads, flipped, the CRC as it was: den refuses it as `pack entry
                         CRC` (its CRC is checked over the bytes the stream used); Git reads it
  false-claim-counts     a declared size of 400 MiB in a pack running on past 8 MiB: refused, having read no more
                         than a first window (4 KiB and a MiB) and reserved no more than a MiB or eight times what
                         the stream decodes
  residual-counts        the same claim on a stream that truly consumes more than a MiB (220,000 empty stored
                         blocks) before its few bytes: refused as Git refuses it; its read at most the header's 4
                         KiB, the stream and one window past it, its reservation at most a MiB, made once, and no
                         window over a MiB
  big-incompressible     16 MiB blobs of random bytes, of numbered lines and of four symbols (a stream about a
  big-compressible       quarter of the size, past the first window): each read back as Git reads it, read in
  big-four-symbol        windows of at most a MiB that slide on from the stream's last whole block; its read at
                         most its entry's bytes, a MiB, 4 KiB and a sixteenth of the entry (each window reads again
                         the block it stopped in), its output reserved once, at most 1.2 times its size: what the
                         read charges, stated as a multiple of the size beside what Git's read holds
  big-crc                the incompressible entry, read across sixteen windows, with its idx CRC flipped and the
                         idx re-signed: refused as `pack entry CRC` (the CRC is taken window by window), where Git
                         reads it
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

    def packed(name, args, source=None):
        repo = out / name
        shutil.copytree(source or seed, repo)
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

    # What a read costs, from the session's own counters (probes/pack-client --read-counts).
    client = str(root / 'target' / a.tier / 'pack-client')

    def counts(repo, name):
        p = subprocess.run([client, '--read-counts', str(repo / '.git'), name], capture_output=True, env=env,
                           timeout=TIMEOUT)
        line = p.stdout.decode(errors='replace').strip()
        fields = dict(f.split('=', 1) for f in line.split() if '=' in f)
        outcome = ' '.join(f for f in line.split() if '=' not in f)
        return p.returncode, fields, outcome, line

    def num(fields, key):
        return int(fields.get(key, '-1'))

    # A read of an object with no delta orders nothing and resolves no offset.
    rc, f, outcome, line = counts(plain_repo, blob['stored.bin'])
    row('entry-read-counts-no-delta', rc == 0 and outcome.startswith('read blob') and num(f, 'sorted') == 0 and
        num(f, 'resolved') == 0, line)
    # Nor does a delta's: an offset delta's base is read at its offset, and its slot (for its CRC) is the one
    # its rebuilt identity names, at that offset.
    rc, f, outcome, line = counts(delta_repo, delta.names[ofs[0]])
    row('entry-read-counts-delta', rc == 0 and outcome.startswith('read ') and num(f, 'sorted') == 0 and
        num(f, 'resolved') == 0, line)

    # Bytes between entries: Git reads every object, as it finds each entry's end from its own stream.
    for name, after in (('gap-after-first', plain.order[0]), ('gap-after-last', plain.order[-1])):
        kind_, size_, hend_, eend_ = plain.span(after)
        pack, idx = plain.rewrite(after, plain.pack[plain.offsets[after]:eend_] + b'JUNK!!!', resign=False)
        repo = install(plain_repo, plain_idx, 'case-' + name, pack, idx)
        bad = []
        for args in [['status', '--porcelain'], ['log', '--oneline']] + [['cat-file', '-p', x] for x in plain.names]:
            g = subprocess.run([git, *args], cwd=repo, capture_output=True, env=env, timeout=TIMEOUT)
            d = subprocess.run([den, *args], cwd=repo, capture_output=True, env=env, timeout=TIMEOUT)
            if g.returncode != d.returncode or (g.returncode == 0 and (g.stdout, g.stderr) != (d.stdout, d.stderr)):
                bad.append(f'{" ".join(args[:2])} {args[2][:12] if len(args) > 2 else ""}: git {g.returncode} den {d.returncode} {d.stderr[-100:]!r}')
        for args in (['fsck', '--full'], ['verify-pack', str(repo / '.git/objects/pack' / plain_idx.name)]):
            g = subprocess.run([git, *args], cwd=repo, capture_output=True, env=env, timeout=TIMEOUT)
            d = subprocess.run([den, *args], cwd=repo, capture_output=True, env=env, timeout=TIMEOUT)
            if (g.returncode == 0) != (d.returncode == 0):
                bad.append(f'{args[0]}: git {g.returncode} den {d.returncode}')
        row(f'entry-{name}-reads', not bad, '; '.join(bad[:4]))

    # A bit the stream never reads: its output is the same, so only the CRC sees it. den refuses it (the
    # CRC checked after the inflate, over the bytes the stream used); Git's read does not check the CRC.
    found = None
    for slot_ in plain.order:
        kind_, size_, hend_, eend_ = plain.span(slot_)
        stream_ = plain.pack[hend_:eend_]
        want_ = zlib.decompress(stream_)
        for bit in range(8):
            m = bytearray(stream_)
            m[-5] ^= 1 << bit
            try:
                same = zlib.decompress(bytes(m)) == want_
            except zlib.error:
                same = False
            if same:
                found = (slot_, plain.pack[plain.offsets[slot_]:hend_] + bytes(m))
                break
        if found:
            break
    if found is None:
        row('entry-unused-bit', False, 'no entry has an unused bit in its last deflate byte')
    else:
        pack, idx = plain.rewrite(found[0], found[1], resign=False)
        repo = install(plain_repo, plain_idx, 'case-unused-bit', pack, idx)
        g, d = read(git, repo, plain.names[found[0]]), read(den, repo, plain.names[found[0]])
        row('entry-unused-bit', g[0] == 0 and d[0] == 128 and b'Unsupported(pack entry CRC)' in d[2],
            f'git {g[0]} den {d[0]} {d[2][-120:]!r}')

    # A false declared size in a pack whose entries run on past 8 MiB: the read reads at most a first window
    # and reserves at most a MiB or eight times what the stream decodes.
    padded = out / 'padded-seed'
    shutil.copytree(seed, padded)
    (padded / 'pad.bin').write_bytes(rng.randbytes(8 << 20))
    run([git, 'add', 'pad.bin'], padded)
    run([git, 'commit', '-q', '--date', '1700000900 +0000', '-m', 'pad'], padded)
    pad_repo, pad_idx = packed('padded', ['-f', '--window=0', '--depth=0'], padded)
    padp = Pack(pad_idx.with_suffix('.pack').read_bytes(), pad_idx.read_bytes())
    pad_name = run([git, 'rev-parse', 'HEAD:pad.bin'], padded).decode().strip()
    small = [i for i in range(padp.count) if padp.span(i)[0] == 3 and padp.names[i] != pad_name]
    victim = max(small, key=lambda i: padp.end - padp.offsets[i])
    kind_, size_, hend_, eend_ = padp.span(victim)
    rest = padp.end - padp.offsets[victim]
    pack, idx = padp.rewrite(victim, entry_header(kind_, 400 << 20) + padp.pack[hend_:eend_])
    repo = install(pad_repo, pad_idx, 'case-false-claim', pack, idx)
    rc, f, outcome, line = counts(repo, padp.names[victim])
    first = 4096 + (1 << 20)
    row('entry-false-claim-counts', outcome.startswith('refused') and num(f, 'read') <= first and
        0 < num(f, 'reserved') <= max(1 << 20, 8 * size_), f'{line} (the pack runs on {rest} bytes past the entry)')
    print(f'  false claim: read={num(f, "read")} reserved={num(f, "reserved")}; decoded {size_}; the pack runs on {rest} bytes', flush=True)

    # The residual, built: a stream that truly consumes more than a MiB (empty stored blocks) before it
    # decodes its few bytes, under the same false claim. Its windows slide on from its last whole block, so
    # its read is the stream and at most one window past it, and its output is reserved once, at most a MiB.
    data_ = zlib.decompress(padp.pack[hend_:eend_])
    blocks = 220000
    crafted = b'\x78\x01' + b'\x00\x00\x00\xff\xff' * blocks + b'\x01' + struct.pack('<HH', len(data_), 0xffff ^ len(data_)) + \
        data_ + zlib.adler32(data_).to_bytes(4, 'big')
    assert zlib.decompress(crafted) == data_
    pack, idx = padp.rewrite(victim, entry_header(kind_, 400 << 20) + crafted)
    repo = install(pad_repo, pad_idx, 'case-residual', pack, idx)
    rest = len(pack) - 20 - padp.offsets[victim]
    rc, f, outcome, line = counts(repo, padp.names[victim])
    g = read(git, repo, padp.names[victim])
    row('entry-residual-counts', outcome.startswith('refused') and g[0] != 0 and
        num(f, 'read') <= 4096 + (hend_ - padp.offsets[victim]) + len(crafted) + (1 << 20) + (64 << 10) and
        0 < num(f, 'reserved') <= 1 << 20 and 0 < num(f, 'window') <= 1 << 20,
        f'{line}; Git {g[0]}')
    print(f'  residual: read={num(f, "read")} reserved={num(f, "reserved")} window={num(f, "window")}; the stream is {len(crafted)} bytes '
          f'(what Git inflates through); the pack runs on {rest} bytes past the entry', flush=True)

    # A sound entry well over a MiB, in three forms: incompressible, compressible, and four symbols (a stream
    # about a quarter of its size, past the first window). Each is read back as Git reads it, in windows of at
    # most a MiB that slide on from the stream's last whole block, so its read is its entry's bytes, a MiB at
    # most past them, the header's 4 KiB, and what each window reads again of the block it stopped in (a
    # sixteenth of the entry at most). Its output is reserved once, at most 1.2 times its size (a MiB first,
    # doubling to an eighth, then the size). What the read charges, its read and its reservations, is printed
    # as a multiple of the size beside what Git's read holds: the entry mapped and the output.
    big = out / 'big-seed'
    run([git, 'init', '-q', '-b', 'main', big], out)
    lines = b''.join(b'%08d the compressible form of a 16 MiB blob, line by line\n' % i for i in range(300000))
    symbols = bytes(b'ACGT'[i & 3] for i in range(256))
    bodies = {'incompressible.bin': rng.randbytes(16 << 20), 'compressible.txt': lines[:16 << 20],
              'four-symbol.bin': rng.randbytes(16 << 20).translate(symbols)}
    for path, body in bodies.items():
        (big / path).write_bytes(body)
    run([git, 'add', '-A'], big)
    run([git, 'commit', '-q', '--date', '1700001000 +0000', '-m', 'big'], big)
    run([git, 'repack', '-adq'], big)
    run([git, 'prune-packed'], big)
    big_idx = next((big / '.git/objects/pack').glob('*.idx'))
    bigp = Pack(big_idx.with_suffix('.pack').read_bytes(), big_idx.read_bytes())
    for path, body in bodies.items():
        label = path.split('.')[0]
        name = run([git, 'rev-parse', f'HEAD:{path}'], big).decode().strip()
        slot_ = bigp.names.index(name)
        _, _, hend_, eend_ = bigp.span(slot_)
        entry = eend_ - bigp.offsets[slot_]
        rest = bigp.end - bigp.offsets[slot_]
        rc, f, outcome, line = counts(big, name)
        g, d = read(git, big, name), read(den, big, name)
        size = len(body)
        same = g[0] == 0 and d[0] == 0 and hashlib.sha256(d[1]).digest() == hashlib.sha256(g[1]).digest()
        read_n, reserved_n, window_n = num(f, 'read'), num(f, 'reserved'), num(f, 'window')
        ok = (read_n <= entry + (1 << 20) + 4096 + entry // 16 and reserved_n <= 1.2 * size and
              0 < window_n <= 1 << 20)
        row(f'entry-big-{label}', outcome == f'read blob {size}' and same and ok,
            f'{line}; entry {entry} bytes; same as Git {same}')
        print(f'  big {path}: read={read_n} ({read_n / entry:.3f} of its entry of {entry} bytes, '
              f'{read_n / size:.3f} of its size), reserved={reserved_n} ({reserved_n / size:.3f} of {size}), '
              f'window={window_n}; charged {(read_n + reserved_n) / size:.3f} times its size; Git maps the entry and '
              f'holds the output, {(entry + size) / size:.3f} times its size; the pack runs on {rest} bytes',
              flush=True)

    # The CRC, taken window by window: the incompressible entry's idx CRC flipped and the idx re-signed.
    name = run([git, 'rev-parse', 'HEAD:incompressible.bin'], big).decode().strip()
    slot_ = bigp.names.index(name)
    idx = bytearray(bigp.idx)
    idx[bigp.crc_table + 4 * slot_] ^= 1
    idx = bytes(idx[:-20]) + hashlib.sha1(bytes(idx[:-20])).digest()
    repo = install(big, big_idx, 'case-big-crc', bigp.pack, idx)
    g, d = read(git, repo, name), read(den, repo, name)
    row('entry-big-crc', g[0] == 0 and d[0] != 0 and b'pack entry CRC' in d[2],
        f'git {g[0]} den {d[0]} {d[2][-200:]!r}')
    failures = rows.count(False)
    print(f'pack-entry: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
