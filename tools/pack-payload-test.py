#!/usr/bin/env python3
"""Malformed packs' diagnostics after they leave a reader's scratch region.

src/pack_payload_test.lu prints one ROW line per reader: the error its caller
sees, read only after other regions have reused memory. This builds it with a
compiler (the pin unless --wolf names another), runs it natively and on the
release tier, observes it on the checked machine, and holds every row to the
diagnostic the reader builds.

tools/checked-exceptions.json lists rows that one compiler's checked machine
is known to render differently. An entry is honoured only for the compiler it
names, on the machine it names, and it must name the pinned compiler: an entry
left behind when the pin moves fails (checked-exception-pin). An entry whose
row the compiler renders correctly fails too (checked-exception-needed-ROW),
so it is removed as soon as it is not needed.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = 'src/pack_payload_test.lu'
ZLIB = 'Unsupported(pack zlib bad_header)'
EXPECTED = {
    'received-scan-zlib': ZLIB,
    'received-resolve-delta': 'Unsupported(pack delta invalid)',
    'install-zlib': ZLIB,
    'read-object-zlib': ZLIB,
    'session-peek-zlib': ZLIB,
    'session-cached-zlib': ZLIB,
    'session-find-zlib': ZLIB,
    'session-read-zlib': ZLIB,
    'inspect-zlib': ZLIB,
}


def pinned_version_line():
    section = None
    for line in (ROOT / 'wolf-toolchain.toml').read_text().splitlines():
        line = line.strip()
        if line.startswith('['):
            section = line.strip('[]')
        elif section == 'wolf' and line.startswith('version_line'):
            return line.split('=', 1)[1].strip().strip('"')
    raise SystemExit('pack-payload: wolf-toolchain.toml has no [wolf] version_line')


def parse_rows(text):
    rows = {}
    for line in text.splitlines():
        if line.startswith('ROW '):
            parts = line.split(' ', 2)
            rows[parts[1]] = parts[2] if len(parts) > 2 else ''
    return rows


def judge_pin(table, pinned):
    """One row: every exception names the pinned compiler."""
    stale = [e for e in table if e.get('compiler') != pinned]
    detail = '; '.join(f"{e.get('row')} names {e.get('compiler')!r}" for e in stale)
    return [(not stale, 'checked-exception-pin',
             f'the pin is {pinned!r}: remove {detail}' if stale else f'{len(table)} entries for {pinned!r}')]


def judge(rows, compiler, machine, table):
    """[(ok, row, detail)] for one machine's ROW lines."""
    out = []
    for name, correct in EXPECTED.items():
        excepted = [e for e in table
                    if e.get('compiler') == compiler and e.get('machine') == machine and e.get('row') == name]
        have = rows.get(name)
        want = correct
        if excepted:
            if have == correct:
                out.append((False, f'checked-exception-needed-{name}',
                            f'{compiler} on {machine} prints {have!r}: the exception is not needed; remove it'))
                continue
            want = excepted[0]['prints']
        note = f' (the exception for {compiler})' if excepted else ''
        out.append((have == want, f'pack-payload-{machine}-{name}', f'got {have!r}, want {want!r}{note}'))
    extra = sorted(set(rows) - set(EXPECTED))
    if extra:
        out.append((False, f'pack-payload-{machine}-rows', f'rows no table names: {extra}'))
    return out


def run(argv, env, cwd=ROOT):
    return subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=600)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wolf', default=os.environ.get('WOLF', str(ROOT / '.wolf-bin/wolf')))
    parser.add_argument('--std', default=os.environ.get('WOLF_STD', str(ROOT / '.wolf-bin/std')))
    parser.add_argument('--machines', default='native,release,checked')
    parser.add_argument('--table', default=str(ROOT / 'tools/checked-exceptions.json'))
    a = parser.parse_args()
    table = json.loads(Path(a.table).read_text())['exceptions']
    (ROOT / 'target/tmp').mkdir(parents=True, exist_ok=True)
    home = Path(tempfile.mkdtemp(prefix='pack-payload-home-', dir=ROOT / 'target/tmp'))
    env = dict(os.environ, WOLF_STD=a.std, SHELL='/bin/sh', HOME=str(home), LC_ALL='C')
    version = run([a.wolf, '--version'], env)
    compiler = version.stdout.splitlines()[0] if version.returncode == 0 and version.stdout else ''
    results = judge_pin(table, pinned_version_line())
    out = ROOT / 'target/pack-payload'
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for machine in a.machines.split(','):
        if machine == 'checked':
            q = run([a.wolf, 'conform-run', PROGRAM, '--checked', '--json'], env)
            (out / 'checked.json').write_text(q.stdout + q.stderr)
            records = [json.loads(x) for x in q.stdout.splitlines() if x.startswith('{')]
            ok = len(records) == 1 and records[0].get('verdict') == 'exit(0)' and 'stdout_inline' in records[0]
            results.append((ok, 'pack-payload-checked-verdict',
                            records[0].get('verdict') if len(records) == 1 else f'{len(records)} records'))
            text = records[0].get('stdout_inline', '') if ok else ''
        elif machine in ('native', 'release'):
            binary = out / machine
            flag = ['--release'] if machine == 'release' else []
            q = run([a.wolf, 'build', *flag, '--deny-warnings', PROGRAM, '-o', str(binary)], env)
            results.append((q.returncode == 0, f'pack-payload-{machine}-build', f'exit {q.returncode}'))
            if q.returncode != 0:
                for line in (q.stdout + q.stderr).splitlines():
                    print('  ' + line)
                continue
            q = run([str(binary)], env)
            results.append((q.returncode == 0, f'pack-payload-{machine}-exit', f'exit {q.returncode} {q.stderr.strip()}'))
            text = q.stdout
        else:
            raise SystemExit(f'pack-payload: no machine {machine}')
        results += judge(parse_rows(text), compiler, machine, table)
    shutil.rmtree(home, ignore_errors=True)
    for path in (ROOT / 'target/tmp').glob('pack-payload-*'):
        shutil.rmtree(path, ignore_errors=True)
    failed = 0
    for ok, name, detail in results:
        print(('PASS ' if ok else 'FAIL ') + name + ': ' + detail, flush=True)
        failed += not ok
    print(f'pack-payload: {compiler}, {a.machines}: {len(results) - failed} pass, {failed} fail')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
