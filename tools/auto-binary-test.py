#!/usr/bin/env python3
"""Pinned black-box auto-text boundaries and identity-only Den requirements.

Git hash-object --path, add, checkout and status decide the canonical bytes.
No fixed NUL scan window, extension rule, or assumed binary result is used.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

PIN = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
PATH = 'sub/probe.dat'


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tier', default='native')
    p.add_argument('--den')
    p.add_argument('--filter', default='')
    p.add_argument('--dev-oracle', action='store_true')
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target/runs' / ('auto-binary-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    digest = hashlib.sha256(Path(git).read_bytes()).hexdigest()
    if a.dev_oracle:
        assert os.uname().sysname == 'Darwin'
        print('DEV ORACLE (not pinned Linux evidence):', digest, flush=True)
    else:
        assert digest == PIN
    den = a.den or str(root / 'target' / a.tier / 'den')

    def run(tool, argv, cwd, check=True):
        q = subprocess.run([str(tool), *map(str, argv)], cwd=cwd, capture_output=True)
        if check:
            assert q.returncode == 0, (argv, q.returncode, q.stdout, q.stderr)
        return q

    def g(cwd, *argv):
        return run(git, argv, cwd).stdout

    def state(cwd):
        return dict(head=(cwd / '.git/HEAD').read_bytes().hex(),
                    index=(cwd / '.git/index').read_bytes().hex(),
                    objects=g(cwd, 'cat-file', '--batch-all-objects', '--batch-check=%(objectname) %(objecttype) %(objectsize)').hex(),
                    body=(cwd / PATH).read_bytes().hex() if (cwd / PATH).exists() else None)

    def result(q):
        return dict(status=q.returncode, stdout=q.stdout.hex(), stderr=q.stderr.hex())

    bodies = {}
    for offset in (0, 7999, 8000, 8001, 100000):
        body = b'A' * offset + b'\0tail\r\n'
        assert body.find(b'\0') == offset
        bodies[f'nul-{offset}-crlf-after'] = body
        if offset >= 6:
            body = b'head\r\n' + b'A' * (offset - 6) + b'\0tail\n'
            assert body.find(b'\0') == offset
            bodies[f'nul-{offset}-crlf-before'] = body
    bodies.update({
        'lone-cr-middle': b'one\rtwo\r\n',
        'lone-cr-first': b'\r' + b'A' * 100000 + b'tail\r\n',
        'lone-cr-last': b'one\r\n' + b'A' * 100000 + b'\r',
        'cr-nul-middle': b'one\r\0two\r\n',
        'cr-nul-last': b'one\r\ntwo\r\0',
        'cr-nul-first': b'\r\0' + b'A' * 100000 + b'\r\n',
        'ordinary-crlf': b'one\r\ntwo\r\n',
    })
    auto = '* text=auto eol=lf\n'
    cases = [(f'auto-{name}', auto, None, body) for name, body in bodies.items()]
    for mode, rule in [('forced', '* text eol=lf\n'), ('eol-only', '* eol=lf\n'), ('unset', '* -text\n')]:
        for name in ('nul-0-crlf-after', 'nul-100000-crlf-before', 'lone-cr-middle', 'ordinary-crlf'):
            cases.append((f'{mode}-{name}', rule, None, bodies[name]))
    cases += [
        ('info-forced-over-auto', auto, '* text\n', bodies['nul-0-crlf-after']),
        ('info-auto-over-forced', '* text eol=lf\n', '* text=auto\n', bodies['nul-0-crlf-after']),
    ]
    # A third content family: no NUL and no lone CR. Density and denominator
    # probes are byte-defined; Git, not a guessed printable predicate, decides.
    def controls(name, body):
        assert b'\0' not in body and b'\r' not in body.replace(b'\r\n', b'')
        cases.append((name, auto, None, body))

    values = list(range(1, 9)) + [11] + list(range(14, 32)) + [127]
    for value in values:
        for denominator in (1000, 128, 100, 10, 1):
            block = bytes([value]) * 100
            printable = b'A' * (100 * (denominator - 1))
            controls(f'control-density-{value:02x}-1-in-{denominator}-before', block + printable + b'\r\n')
            controls(f'control-density-{value:02x}-1-in-{denominator}-after', b'\r\n' + printable + block)
    for count, printables in [(1, (0, 1, 126, 127, 128, 129, 254, 255, 256)),
                              (2, (254, 255, 256, 257)),
                              (3, (382, 383, 384, 385)),
                              (8, (1022, 1023, 1024, 1025))]:
        for printable in printables:
            block = b'\x01' * count + b'A' * printable
            controls(f'control-threshold-{count}-{printable}-before', block + b'\r\n')
            controls(f'control-threshold-{count}-{printable}-after', b'\r\n' + block)
    for value in (8, 9, 12, 27, 32, 128):
        for printable in (127, 128):
            controls(f'control-denominator-{value:02x}-{printable}', b'\x01' + bytes([value]) * printable + b'\r\n')
    controls('high-valid-utf8', b'\xc3\xa9' * 50000 + b'\r\n')
    controls('high-invalid-utf8', b'\xff\xfe\x80' * 33000 + b'\r\n')
    for count in (127, 128):
        high = b'A' * (count % 2) + b'\xc3\xa9' * (count // 2)
        controls(f'control-denominator-valid-utf8-{count}', b'\x01' + high + b'\r\n')
    for name, body in {
        'control-denominator-lf': b'\x01' + b'\n' * 128 + b'\r\n',
        'control-denominator-crlf': b'\x01' + b'\r\n' * 128,
        'control-sub-before': b'\x1a\r\n',
        'control-sub-at-eof': b'\r\n\x1a',
        'control-sub-two-at-eof': b'\r\n\x1a\x1a',
        'control-sub-mixed-at-eof': b'\x01\r\n\x1a',
        'control-sub-mixed-threshold-127': b'A' * 127 + b'\x01\r\n\x1a',
        'control-sub-mixed-threshold': b'A' * 128 + b'\x01\r\n\x1a',
    }.items():
        controls(name, body)
    rows, oracle_rows = [], []
    for name, rule, info, body in cases:
        if a.filter not in name:
            continue
        case = out / name
        case.mkdir()
        seed = case / 'seed'
        run(git, ['init', '-q', '-b', 'main', seed], root)
        g(seed, 'config', 'gc.auto', '0')
        (seed / 'sub').mkdir()
        (seed / '.gitattributes').write_text(rule)
        (seed / PATH).write_bytes(b'base\n')
        if info is not None:
            (seed / '.git/info').mkdir(exist_ok=True)
            (seed / '.git/info/attributes').write_text(info)
        g(seed, 'add', '.')
        g(seed, 'commit', '-qm', 'base')
        old = g(seed, 'rev-parse', 'HEAD').decode().strip()
        (seed / PATH).write_bytes(body)
        oracle = case / 'oracle'
        shutil.copytree(seed, oracle)
        raw_id = g(oracle, 'hash-object', '--no-filters', PATH).decode().strip()
        clean_id = g(oracle, 'hash-object', '--path=' + PATH, PATH).decode().strip()
        before_status = run(git, ['status', '--porcelain'], oracle)
        added = run(git, ['add', PATH], oracle)
        canonical = g(oracle, 'show', ':' + PATH)
        assert canonical in (body, body.replace(b'\r\n', b'\n'))
        assert (raw_id == clean_id) == (canonical == body)
        (oracle / PATH).unlink()
        checked = run(git, ['checkout', '--', PATH], oracle)
        assert (oracle / PATH).read_bytes() == canonical
        g(oracle, 'commit', '-qm', 'probe')
        g(oracle, 'branch', 'incoming')
        clean_status = run(git, ['status', '--porcelain'], oracle)
        assert clean_status.stdout == b''
        identity = canonical == body
        detail = dict(name=name, rule=rule, info=info, bytes=len(body), first_nul=body.find(b'\0'),
                      crlf=body.count(b'\r\n'), raw_oid=raw_id, clean_oid=clean_id,
                      canonical_sha256=hashlib.sha256(canonical).hexdigest(), identity=identity,
                      hash_path_matches_add=True, checkout_matches_index=True,
                      status_before=result(before_status), status_after=result(clean_status))
        oracle_rows.append(detail)
        print('ORACLE ' + name + ' ' + json.dumps(detail, sort_keys=True), flush=True)
        (case / 'oracle-clean.bin').write_bytes(canonical)
        for command in ('status-before-add', 'add', 'checkout-path', 'restore-path', 'checkout-branch', 'status-clean'):
            work = case / ('den-' + command)
            shutil.copytree(seed if command in ('status-before-add', 'add') else oracle, work)
            needs_conversion = not identity and command in ('status-before-add', 'add')
            if command == 'status-before-add':
                argv, expected = ['status', '--porcelain'], before_status
            elif command == 'add':
                argv, expected = ['add', PATH], added
            elif command in ('checkout-path', 'restore-path'):
                (work / PATH).unlink()
                argv = ['checkout', '--', PATH] if command == 'checkout-path' else ['restore', PATH]
                expected = checked
            elif command == 'checkout-branch':
                g(work, 'checkout', '-q', '--detach', old)
                argv = ['checkout', '-q', 'incoming']
                expected = subprocess.CompletedProcess([], 0, b'', b'')
            else:
                argv, expected = ['status', '--porcelain'], clean_status
            before = state(work)
            q = run(den, argv, work, check=False)
            if needs_conversion:
                ok = q.returncode == 2 and b'worktree attributes: text' in q.stderr and PATH.encode() in q.stderr and state(work) == before
            else:
                ok = result(q) == result(expected)
                if command != 'status-before-add':
                    ok = ok and (work / PATH).read_bytes() == canonical
                if command == 'add':
                    ok = ok and g(work, 'show', ':' + PATH) == canonical
            row_name = f'auto-binary-{name}-{command}'
            print(('PASS ' if ok else 'FAIL ') + row_name, flush=True)
            row = dict(name=row_name, passed=ok, oracle_identity=identity, git=result(expected), den=result(q))
            if not ok:
                print(json.dumps(row), flush=True)
            rows.append(row)
    assert rows, 'empty selection'
    (out / 'oracle.json').write_text(json.dumps(oracle_rows, indent=2) + '\n')
    (out / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
    failed = sum(not x['passed'] for x in rows)
    print(f'auto-binary: {len(oracle_rows)} oracle fixtures, {len(rows)} rows, {failed} failures; zero skips', flush=True)
    return int(failed != 0)


if __name__ == '__main__':
    raise SystemExit(main())
