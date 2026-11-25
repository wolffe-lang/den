#!/usr/bin/env python3
"""zlib streams resumed at every split point, against Python's zlib; no codec source imports.

`zpipe inflate_splits` runs inflate_resume over each stream's first k bytes, for every k, and, when that
meets the window's end, again over the stream from the resume point on. It prints, for each split, the first
call's answer, the resume point (byte, bit, output made before it), the final answer, the bytes consumed, the
output's length and its SHA-1. Every split must end as Python's zlib does: the stream's bytes and its whole
length. A first call may end early only by `truncated`, and its resume point must lie before the split.

Four streams, made here by Python's zlib so that their block boundaries are known:
- stored: three stored blocks, each ended by a full flush (an empty stored block);
- fixed: fixed Huffman codes (Z_FIXED);
- flushed: dynamic blocks, each ended by a full flush, so the next block starts on a known byte;
- long: one dynamic final block.

Named rows pick out the places a resumption must hold:
- inside a stored block's length field;
- inside a dynamic header;
- inside a code;
- exactly between blocks;
- just past the final block's first byte;
- inside each of the four Adler-32 bytes.
"""
import argparse
import hashlib
import os
import random
import subprocess
import zlib


def stream(chunks, level, strategy=zlib.Z_DEFAULT_STRATEGY):
    c = zlib.compressobj(level, zlib.DEFLATED, 15, 8, strategy)
    out, bounds = b'', []
    for i, chunk in enumerate(chunks):
        out += c.compress(chunk)
        if i + 1 < len(chunks):
            out += c.flush(zlib.Z_FULL_FLUSH)
            bounds.append(len(out))
    out += c.flush(zlib.Z_FINISH)
    return out, bounds


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--binary', default='target/native/zpipe')
    a = p.parse_args()
    rng = random.Random(0x7265)
    words = [b'tree', b'blob', b'commit', b'parent', b'author', b'den', b'pack', b'delta', b'\n']
    text = lambda n: b' '.join(rng.choice(words) for _ in range(n))
    streams = {
        'stored': stream([rng.randbytes(700), rng.randbytes(900), rng.randbytes(400)], 0),
        'fixed': stream([text(400)], 6, zlib.Z_FIXED),
        'flushed': stream([text(300), text(500), text(200)], 9),
        'long': stream([text(1200)], 9),
    }
    os.makedirs('target/codec', exist_ok=True)
    rows, results = [], {}

    def row(name, ok, detail=''):
        rows.append(ok)
        print(('PASS ' if ok else 'FAIL ') + name + (': ' + detail if detail else ''), flush=True)

    for label, (data, bounds) in streams.items():
        whole = zlib.decompress(data)
        want = hashlib.sha1(whole).hexdigest()
        path = f'target/codec/resume-{label}.z'
        open(path, 'wb').write(data)
        r = subprocess.run([a.binary, 'inflate_splits', path, '/dev/null', str(len(whole)), '0'],
                           capture_output=True, timeout=120)
        lines = r.stdout.decode().split('\n')[:-1]
        by_k, bad = {}, []
        for line in lines:
            k, first, at, bit, made, last, consumed, n, sha = line.split()
            k, at, bit, made, consumed, n = int(k), int(at), int(bit), int(made), int(consumed), int(n)
            by_k[k] = (first, at, bit, made)
            # The first call ends the stream only when it holds all of it, and ends early only by truncated,
            # its resume point at or before the split; the final answer is the whole stream's, always.
            good = (last, consumed, n, sha) == ('ok', len(data), len(whole), want)
            if first == 'ok':
                good = good and k == len(data)
            else:
                good = good and first == 'truncated' and at <= k and 0 <= bit < 8 and made <= len(whole)
            if not good:
                bad.append(line)
        results[label] = (data, bounds, whole, by_k)
        row(f'resume-every-split-{label}', r.returncode == 0 and len(lines) == len(data) and not bad,
            f'{len(lines)} splits of {len(data)} bytes; exit {r.returncode}; ' + '; '.join(bad[:3]))

    def at(label, k):
        return results[label][3].get(k, ('missing', -1, -1, -1))

    # Inside a stored block's length field: the block's header byte is the stream's third (byte 2), LEN its
    # fourth and fifth; a window of four bytes ends inside LEN, so the block is decoded again from byte 2.
    first, b, bit, made = at('stored', 4)
    row('resume-stored-length', (first, b, bit, made) == ('truncated', 2, 0, 0), f'{first} at {b}.{bit} made {made}')
    # Inside a dynamic header: the long stream's one block begins at byte 2, bit 0; its code-length tables run
    # well past byte 10.
    first, b, bit, made = at('long', 10)
    row('resume-dynamic-header', (first, b, bit, made) == ('truncated', 2, 0, 0), f'{first} at {b}.{bit} made {made}')
    # Inside a code: halfway through the long stream's coded data, the one block again from its start.
    data = results['long'][0]
    first, b, bit, made = at('long', len(data) // 2)
    row('resume-inside-code', (first, b, bit, made) == ('truncated', 2, 0, 0), f'{first} at {b}.{bit} made {made}')
    # Exactly between blocks: a window ending at a full flush's end decodes every block before it, and the
    # next block begins there, on bit 0, with all the output before it made.
    data, bounds, whole, _ = results['flushed']
    for i, edge in enumerate(bounds):
        made_before = len(zlib.decompressobj().decompress(data[:edge]))
        first, b, bit, made = at('flushed', edge)
        row(f'resume-between-blocks-{i + 1}', (first, b, bit, made) == ('truncated', edge, 0, made_before),
            f'{first} at {b}.{bit} made {made}; the flush ends at {edge}, {made_before} bytes before it')
    # The final block: a window one byte into it decodes every block before it again; resumed, the rest.
    edge = bounds[-1]
    first, b, bit, made = at('flushed', edge + 1)
    row('resume-final-block', first == 'truncated' and b == edge and bit == 0 and made < len(whole),
        f'{first} at {b}.{bit} made {made}; the final block begins at {edge}')
    # Inside the Adler-32: every block decoded, the checksum's bytes cut short; resumed at its first byte.
    for label in ('stored', 'flushed', 'long'):
        data, _, whole, _ = results[label]
        for cut in (4, 3, 2, 1):
            first, b, bit, made = at(label, len(data) - cut)
            row(f'resume-adler-{label}-{5 - cut}', (first, b, bit, made) == ('truncated', len(data) - 4, 0, len(whole)),
                f'{first} at {b}.{bit} made {made}')
    failures = rows.count(False)
    print(f'codec-resume: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
