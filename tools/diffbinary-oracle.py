#!/usr/bin/env python3
"""Independent pinned-Git binary-body differential and application witnesses.

Only the executable is consulted. Python's standard zlib/base64 independently
validate the wire format; neither is a runtime dependency of the wolf module.
Default exit is nonzero on ANY byte difference, even when application succeeds.
--interoperability-only explicitly changes the assertion, never the comparison
or retained witnesses. This option is evidence for a requested ruling, not a
claim that the byte-parity contract passed. --reviewed-compression accepts only
capture-bound reviewed cases whose literal/delta kind and size lines are exact.
The refined R-vc04-4 --reviewed-body mode also admits capture-bound delta-search
representation choices; new/changed captures remain failures, and every body
undergoes canonical framing and forward/reverse exact-blob application checks.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import tomllib
import zlib

ROOT = Path(__file__).resolve().parent.parent
REVIEW = ROOT / 'probes/diffbinary-client/reviewed-captures.json'
BODY_REVIEW = ROOT / 'probes/diffbinary-client/reviewed-body-captures.json'
ORACLE = ROOT / 'target/oracle/4fc1e5da7ea879faa3aa991c60e3c686e7200023717870f5f2961968a72d0327/root/opt/git/bin/git'


def run(argv, *, cwd=None, data=None, expected=(0,), env=None):
    p = subprocess.run([str(x) for x in argv], cwd=cwd, input=data,
                       capture_output=True, timeout=60, env=env)
    assert p.returncode in expected, (argv, p.returncode, p.stdout, p.stderr)
    return p


def sha(data):
    return hashlib.sha256(data).hexdigest()


def review_capture(row, reviewed, body=False):
    record = reviewed.get(row['name'])
    if record is not None and row['captures'] != record['captures']:
        return 'capture-changed'
    if row['byte_identical']:
        return 'exact'
    if record is None:
        return 'unreviewed'
    if row['outer_differences'] and not body:
        return 'outside-compression-scope'
    return 'reviewed-body' if body else 'reviewed-compression'


def review_selftest():
    # These plants prove neither altered inputs/captures nor a new row or
    # changed block header can be accepted by the review predicate.
    row = {'name': 'plant', 'byte_identical': False,
           'captures': {'input': 'a', 'body': 'b'}, 'outer_differences': []}
    reviewed = {'plant': {'captures': dict(row['captures'])}}
    assert review_capture(row, reviewed) == 'reviewed-compression'
    assert review_capture(row, reviewed, True) == 'reviewed-body'
    for key in ('input', 'body'):
        changed = {**row, 'captures': {**row['captures'], key: 'changed'}}
        assert review_capture(changed, reviewed) == 'capture-changed'
        assert review_capture(changed, reviewed, True) == 'capture-changed'
    assert review_capture({**row, 'name': 'new'}, reviewed) == 'unreviewed'
    assert review_capture({**row, 'name': 'new'}, reviewed, True) == 'unreviewed'
    assert review_capture({**row, 'outer_differences': ['delta 20 != delta 10']}, reviewed) == 'outside-compression-scope'


def oid(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def undelta(raw, base):
    pos = 0

    def number():
        nonlocal pos
        out = shift = 0
        while True:
            b = raw[pos]
            pos += 1
            out |= (b & 127) << shift
            shift += 7
            assert shift <= 63
            if not b & 128:
                return out

    assert number() == len(base)
    size = number()
    out = bytearray()
    opcodes = []
    while pos < len(raw):
        op = raw[pos]
        pos += 1
        assert op != 0
        if op & 128:
            offset = length = 0
            for i in range(4):
                if op & (1 << i):
                    offset |= raw[pos] << (8 * i)
                    pos += 1
            for i in range(3):
                if op & (16 << i):
                    length |= raw[pos] << (8 * i)
                    pos += 1
            length = length or 65536
            assert offset + length <= len(base)
            out.extend(base[offset:offset + length])
            opcodes.append(['copy', offset, length])
        else:
            assert pos + op <= len(raw)
            out.extend(raw[pos:pos + op])
            pos += op
            opcodes.append(['insert', op])
        assert len(out) <= size
    assert len(out) == size
    return bytes(out), opcodes


def blocks(body, before, after):
    assert body.startswith(b'GIT binary patch\n') and body.endswith(b'\n\n')
    assert b'\r' not in body
    parts = body.removeprefix(b'GIT binary patch\n').split(b'\n\n')
    assert len(parts) == 3 and parts[-1] == b''
    result = []
    for part, base, target in zip(parts[:2], (before, after), (after, before)):
        header, *lines = part.split(b'\n')
        kind, size = header.split()
        assert kind in (b'literal', b'delta')
        assert header == kind + b' ' + str(int(size)).encode()
        packed = bytearray()
        lengths = []
        for i, line in enumerate(lines):
            mark = line[0]
            assert 65 <= mark <= 90 or 97 <= mark <= 122
            n = mark - 64 if mark <= 90 else mark - 96 + 26
            assert 1 <= n <= 52 and len(line) == 1 + ((n + 3) // 4) * 5
            if i < len(lines) - 1:
                assert n == 52
            decoded = base64.b85decode(line[1:])
            assert decoded[n:] == bytes(len(decoded) - n)
            packed.extend(decoded[:n])
            lengths.append(n)
        dec = zlib.decompressobj()
        raw = dec.decompress(packed) + dec.flush()
        assert dec.eof and not dec.unused_data and not dec.unconsumed_tail
        assert len(raw) == int(size)
        reconstructed, ops = (raw, []) if kind == b'literal' else undelta(raw, base)
        assert reconstructed == target
        result.append({'header': header.decode(), 'kind': kind.decode(), 'raw_size': len(raw),
                       'compressed_size': len(packed), 'line_lengths': lengths,
                       'zlib_level_matches': [n for n in range(10) if zlib.compress(raw, n) == packed],
                       'raw_hex': raw.hex(), 'compressed_hex': packed.hex(),
                       'opcodes': ops})
    return result


def cases():
    rng = random.Random(0xB104)
    yield 'empty-add', b'', b'\0'
    yield 'empty-delete', b'\0', b''
    # All final-line lengths and all 256 byte values appear independently.
    for n in range(1, 80):
        yield f'short-{n}', b'\0old', b'\0' + rng.randbytes(n)
    yield 'alphabet', b'\0old', bytes(range(256))
    for n in (16, 17, 31, 32, 63, 64, 127, 128, 255, 256, 1024, 8192, 32768, 65536, 131072):
        old = b'\0' + rng.randbytes(n - 1)
        middle = n // 2
        yield f'insert-{n}', old, old[:middle] + b'NEW\0' + old[middle:]
        yield f'replace-{n}', old, old[:middle] + b'!\0!' + old[middle + 3:]
        yield f'delete-{n}', old, old[:middle] + old[middle + min(13, n - middle):]
        yield f'repeat-{n}', b'\0' + b'x' * n, b'\0' + b'x' * middle + b'NEW' + b'x' * (n - middle)
    for n in (2048, 70000):
        old = b'\0' + rng.randbytes(n)
        yield f'move-{n}', old, old[n // 2:] + old[:n // 2]
        yield f'multi-edit-{n}', old, old[:33] + b'abc' + old[40:900] + old[1100:] + b'\0end'
        yield f'copy-offset-{n}', old, b'\0prefix' + old[-256:]
    # Change a binary pair into unrelated low/high entropy targets.
    yield 'unrelated-random', b'\0' + rng.randbytes(4096), b'\0' + rng.randbytes(5000)
    yield 'unrelated-compressible', b'\0abc' * 2000, b'\0XYZ' * 3000
    extra = random.Random(0xB185)
    for n in range(80, 180):
        yield f'line-boundary-{n}', b'\0old', b'\0' + extra.randbytes(n)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), required=True)
    parser.add_argument('--git', type=Path, default=Path(os.environ.get('DEN_GIT', ORACLE)))
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--interoperability-only', action='store_true')
    modes.add_argument('--reviewed-compression', action='store_true')
    modes.add_argument('--reviewed-body', action='store_true')
    parser.add_argument('--with-cli', action='store_true')
    args = parser.parse_args()
    review_selftest()
    reviewed = {}
    review_file = BODY_REVIEW if args.reviewed_body else REVIEW
    if args.reviewed_compression or args.reviewed_body:
        manifest = json.loads(review_file.read_text())
        assert manifest['schema'] == 1
        reviewed = {r['name']: r for r in manifest['rows']}
        assert len(reviewed) == len(manifest['rows']) == (96 if args.reviewed_body else 95)
        assert manifest['scope'] == ('R-vc04-4 binary representation; exact reconstruction and validated framing' if args.reviewed_body else 'compressed payload only; exact kind/size headers required')
    pin = tomllib.loads((ROOT / 'den-oracle.toml').read_text())['oracle']
    if args.reviewed_compression or args.reviewed_body:
        assert manifest['oracle_sha256'] == pin['binary_sha256']
    git = args.git.resolve()
    assert hashlib.sha256(git.read_bytes()).hexdigest() == pin['binary_sha256']
    assert run([git, '--version']).stdout.decode().strip() == pin['version_line']
    driver = ROOT / f'target/{args.tier}/diffbinary-client'
    den = ROOT / f'target/{args.tier}/den'
    if args.with_cli: assert den.is_file(), den
    root = ROOT / f'target/diffbinary-{args.tier}'
    root.mkdir(parents=True, exist_ok=True)
    home = root / 'home'
    home.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(home), GIT_CONFIG_NOSYSTEM='1',
               GIT_CONFIG_GLOBAL='/dev/null', LC_ALL='C', GIT_ATTR_NOSYSTEM='1', GIT_OPTIONAL_LOCKS='0')
    repo = root / 'apply'
    repo.mkdir(exist_ok=True)
    run([git, 'init', '-q', '--object-format=sha1', repo], env=env)
    results = []
    rejected = 0
    alphabet = set()
    line_lengths = set()
    for name, before, after in cases():
        case = root / name
        case.mkdir(exist_ok=True)
        old, new, output = case / 'old.bin', case / 'new.bin', case / 'actual.body'
        old.write_bytes(before)
        new.write_bytes(after)
        oracle = run([git, '-c', 'diff.external=', 'diff', '--no-index', '--no-ext-diff',
                      '--no-textconv', '--binary', '--', 'old.bin', 'new.bin'],
                     cwd=case, expected=(1,), env=env)
        assert not oracle.stderr
        oracle_status = oracle.returncode
        oracle_stderr = oracle.stderr
        oracle = oracle.stdout
        (case / 'oracle.patch').write_bytes(oracle)
        oracle_body = b'GIT binary patch\n' + oracle.split(b'GIT binary patch\n', 1)[1]
        (case / 'oracle.body').write_bytes(oracle_body)
        p = run([driver, old, new, output], env=env)
        assert not p.stdout and not p.stderr, (name, p.stdout, p.stderr)
        actual = output.read_bytes()
        observed = blocks(oracle_body, before, after)
        generated = blocks(actual, before, after)
        for block in generated:
            line_lengths.update(block['line_lengths'])
        for block in actual.split(b'\n\n')[:2]:
            for line in block.splitlines():
                if line and not line.startswith((b'GIT', b'literal', b'delta')):
                    alphabet.update(line[1:])
        header = f'diff --git a/data b/data\nindex {oid(before)}..{oid(after)} 100644\n'.encode()
        patch = header + actual
        (case / 'actual.patch').write_bytes(patch)
        oracle_apply_patch = header + oracle_body
        (case / 'oracle-apply.patch').write_bytes(oracle_apply_patch)
        (repo / 'data').write_bytes(before)
        # Exercise the index too, so forward/reverse object IDs are checked.
        run([git, 'add', '--', 'data'], cwd=repo, env=env)
        if args.with_cli:
            (repo / 'data').write_bytes(after)
            index_before = (repo / '.git/index').read_bytes()
            oracle_cli = run([git, 'diff', '--binary'], cwd=repo, env=env)
            actual_cli = run([den, 'diff', '--binary'], cwd=repo, env=env)
            assert not oracle_cli.stderr and not actual_cli.stderr
            assert oracle_cli.stdout == header + oracle_body, (name, 'oracle CLI envelope')
            assert actual_cli.stdout == header + actual, (name, 'den CLI envelope/body')
            assert (repo / '.git/index').read_bytes() == index_before and (repo / 'data').read_bytes() == after
            (case / 'oracle-cli.patch').write_bytes(oracle_cli.stdout)
            (case / 'actual-cli.patch').write_bytes(actual_cli.stdout)
            (repo / 'data').write_bytes(before)
            run([git, 'add', '--', 'data'], cwd=repo, env=env)
        run([git, 'apply', '--check', '--index', '--binary', '-'], cwd=repo, data=patch, env=env)
        run([git, 'apply', '--index', '--binary', '-'], cwd=repo, data=patch, env=env)
        assert (repo / 'data').read_bytes() == after
        run([git, 'apply', '-R', '--index', '--binary', '-'], cwd=repo, data=patch, env=env)
        assert (repo / 'data').read_bytes() == before
        # Every selected fixture also proves corrupt data cannot pass the
        # oracle application gate. The deliberately bad body stays on disk.
        if name in ('empty-add', 'alphabet', 'insert-8192', 'copy-offset-70000'):
            lines = patch.splitlines(keepends=True)
            at = next(i for i, line in enumerate(lines) if line.startswith((b'literal ', b'delta '))) + 1
            lines[at] = lines[at][:1] + b'~' + lines[at][2:]
            broken = b''.join(lines)
            (case / 'corrupt.patch').write_bytes(broken)
            q = run([git, 'apply', '--check', '--index', '--binary', '-'], cwd=repo,
                    data=broken, env=env, expected=(1, 128))
            (case / 'corrupt.stderr').write_bytes(q.stderr)
            rejected += 1
        differences = []
        outer_differences = []
        for direction, ours, theirs in zip(('forward', 'reverse'), generated, observed):
            if ours['header'] != theirs['header']:
                outer_differences.append({'direction': direction, 'actual': ours['header'],
                                          'oracle': theirs['header']})
            if ours['kind'] != theirs['kind']:
                differences.append(direction + ':block-choice')
            elif ours['raw_hex'] != theirs['raw_hex']:
                differences.append(direction + ':delta-instructions')
            elif ours['compressed_hex'] != theirs['compressed_hex']:
                differences.append(direction + ':deflate-bytes')
        captures = {'before_sha256': sha(before), 'after_sha256': sha(after),
                    'actual_body_sha256': sha(actual), 'oracle_body_sha256': sha(oracle_body),
                    'actual_full_patch_sha256': sha(patch),
                    'oracle_full_stdout_sha256': sha(oracle),
                    'oracle_apply_patch_sha256': sha(oracle_apply_patch),
                    'oracle_stderr_sha256': sha(oracle_stderr), 'oracle_status': oracle_status,
                    'actual_stdout_sha256': sha(p.stdout), 'actual_stderr_sha256': sha(p.stderr),
                    'actual_status': p.returncode}
        row = {'name': name, 'before_size': len(before), 'after_size': len(after),
               'byte_identical': actual == oracle_body, 'differences': differences,
               'forward_reverse_index_apply': True, 'captures': captures,
               'outer_differences': outer_differences, 'canonical_base85_framing': True,
               'oracle': observed, 'actual': generated}
        row['review_status'] = review_capture(row, reviewed, args.reviewed_body)
        (case / 'measurements.json').write_text(json.dumps(row, indent=2) + '\n')
        results.append({k: v for k, v in row.items() if k not in ('oracle', 'actual')})
    # Oversize input is refused before opening/truncating the output path.
    oversized = root / 'oversized.bin'
    with oversized.open('wb') as file:
        file.truncate(16777217)
    sentinel = root / 'limit-output'
    sentinel.write_bytes(b'UNCHANGED')
    limit = run([driver, oversized, new, sentinel], expected=(1,), env=env)
    assert b'limit' in limit.stderr and not limit.stdout
    assert sentinel.read_bytes() == b'UNCHANGED'
    (root / 'limit.stderr').write_bytes(limit.stderr)
    exact = sum(row['byte_identical'] for row in results)
    summary = {'tier': args.tier, 'oracle_sha256': pin['binary_sha256'],
               'driver_sha256': hashlib.sha256(driver.read_bytes()).hexdigest(),
               'scope': ('interoperability-only' if args.interoperability_only else
                         'reviewed-body' if args.reviewed_body else 'reviewed-compression' if args.reviewed_compression else 'byte-parity'),
               'rows': results, 'exact': exact, 'total': len(results),
               'forward_reverse_index_apply': len(results), 'cli_envelope_exact': len(results) if args.with_cli else 0, 'corrupt_rejected': rejected,
               'base85_symbols_covered': len(alphabet), 'line_lengths_covered': sorted(line_lengths),
               'oversize_refused_without_output_change': True, 'zero_skips': True,
               'outer_difference_cases': [r['name'] for r in results if r['outer_differences']],
               'review_rejected': [{'name': r['name'], 'reason': r['review_status']}
                                   for r in results if r['review_status'] not in ('exact', 'reviewed-compression', 'reviewed-body')],
               'review_manifest_sha256': sha(review_file.read_bytes()) if args.reviewed_compression or args.reviewed_body else None,
               'review_predicate_plants_rejected': 4}
    (root / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (root / f"summary-{summary['scope']}.json").write_text(json.dumps(summary, indent=2) + '\n')
    print(f'diffbinary {args.tier}: bytes {exact}/{len(results)}; '
          f'forward/reverse indexed apply {len(results)}/{len(results)}; '
          f'corrupt rejected {rejected}/4; base85 symbols {len(alphabet)}/85; zero skips', flush=True)
    assert rejected == 4 and len(alphabet) == 85
    assert line_lengths == set(range(1, 53)), sorted(line_lengths)
    print(f"OUTER HEADER DIFFERENCES: {len(summary['outer_difference_cases'])} cases; " +
          ('representation-dependent under R-vc04-4' if args.reviewed_body else 'kind/size discrepancies are OUTSIDE the compression-only scope'), flush=True)
    if args.reviewed_compression or args.reviewed_body:
        rejected_reviews = summary['review_rejected']
        accepted = sum(r['review_status'] in ('reviewed-compression', 'reviewed-body') for r in results)
        print(f'REVIEWED REPRESENTATION: {accepted} capture-bound exceptions; '
              f'{len(rejected_reviews)} rejected; not byte parity', flush=True)
        for r in rejected_reviews:
            print(f"REVIEW REJECT {r['name']}: {r['reason']}", flush=True)
        for name in reviewed.keys() - {r['name'] for r in results}:
            raise AssertionError(f'reviewed fixture missing: {name}')
    if exact != len(results):
        print(f'BYTE PARITY FAIL: {len(results) - exact} named differences retained under {root}', flush=True)
        if args.interoperability_only:
            print('INTEROPERABILITY ONLY: byte parity remains failed; no waiver is assumed', flush=True)
    summary['completed'] = True
    (root / f"summary-{summary['scope']}.json").write_text(json.dumps(summary, indent=2) + '\n')
    if args.reviewed_compression or args.reviewed_body:
        return int(bool(summary['review_rejected']))
    return int(not args.interoperability_only and exact != len(results))


if __name__ == '__main__':
    raise SystemExit(main())
