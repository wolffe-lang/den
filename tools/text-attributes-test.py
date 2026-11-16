#!/usr/bin/env python3
"""LF-only text attribute acceptance, and path-named conversion refusals.

Black-box Git is the oracle. This is deliberately not a normalization claim.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tier', default='native')
    ap.add_argument('--den')
    ap.add_argument('--filter', default='')
    ap.add_argument('--dev-oracle', action='store_true', help='Darwin development evidence only; not the pinned Linux oracle')
    a = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target/runs' / ('text-attributes-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    digest = hashlib.sha256(Path(git).read_bytes()).hexdigest()
    if a.dev_oracle:
        assert os.uname().sysname == 'Darwin', 'development oracle is Darwin-only'
        print('DEV ORACLE (not pinned Linux evidence):', subprocess.check_output([git, '--version']).decode().strip(), digest, flush=True)
    else:
        assert digest == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = a.den or str(root / 'target' / a.tier / 'den')

    def run(tool, args, cwd, check=True):
        p = subprocess.run([str(tool), *map(str, args)], cwd=cwd, capture_output=True)
        if check:
            assert p.returncode == 0, (tool, args, p.stdout, p.stderr)
        return p

    def state(w):
        return dict(head=run(git, ['rev-parse', 'HEAD'], w).stdout.hex(),
                    index=run(git, ['ls-files', '-s'], w).stdout.hex(),
                    files={str(p.relative_to(w)): p.read_bytes().hex()
                           for p in sorted(w.rglob('*'))
                           if '.git' not in p.relative_to(w).parts and p.is_file()})

    commands = {
        'status': ['status', '--porcelain'],
        'add': ['add', 'sub/a.txt'],
        'commit': ['commit', '-qam', 'edit'],
        'checkout': ['checkout', '-q', 'other'],
        'checkout-path': ['checkout', '--', 'sub/a.txt'],
        'restore': ['restore', 'sub/a.txt'],
        'pull': ['pull', '--ff-only', 'origin', 'main'],
        'pull-rebase': ['pull', '--rebase', 'origin', 'main'],
        'diff': ['diff'],
        'diff-cached': ['diff', '--cached'],
        'diff-tree': ['diff', 'HEAD~', 'HEAD'],
        'log-p': ['log', '-p', '-1'],
        'log-stat': ['log', '--stat', '-1'],
        'show': ['show', 'HEAD'],
        'show-root': ['show', 'HEAD~'],
        'log-root': ['log', '-p', '-1', 'HEAD~'],
    }
    attrs = {
        'auto-lf': ('.gitattributes', '* text=auto eol=lf\n'),
        'text': ('.gitattributes', '* text\n'),
        'auto': ('.gitattributes', '* text=auto\n'),
        'eol-lf': ('.gitattributes', '* eol=lf\n'),
        'nested': ('sub/.gitattributes', '*.txt text=auto eol=lf\n'),
        'unset': ('.gitattributes', '* -text\n'),
        'unknown': ('.gitattributes', '* linguist-generated\n'),
        'nonmatching': ('.gitattributes', '*.other text=auto eol=lf\n'),
        'nested-unset': ('sub/.gitattributes', '*.txt -text\n'),
        'override': ('.gitattributes', '* text=auto eol=lf\nsub/a.txt -text\n'),
        'info': ('.git/info/attributes', '* text=auto eol=lf\n'),
        'deleted': ('.gitattributes', '* text=auto eol=lf\n'),
        'chunk-boundary': ('.gitattributes', '* text=auto eol=lf\n'),
        'nul': ('.gitattributes', '* text=auto eol=lf\n'),
        'bare-cr': ('.gitattributes', '* text=auto eol=lf\n'),
        'binary': ('.gitattributes', '*.png binary\n'),
    }
    converting = {'auto-lf', 'text', 'auto', 'eol-lf', 'nested', 'info', 'deleted',
                  'chunk-boundary', 'nul', 'bare-cr'}
    rows = []
    for kind, (attr_path, attr) in attrs.items():
        for command, argv in commands.items():
            for crlf in (False, True):
                if crlf and command not in ('status', 'add', 'commit', 'checkout', 'checkout-path', 'restore', 'pull', 'pull-rebase', 'diff'):
                    continue
                name = f'text-attributes-{kind}-{"crlf" if crlf else "lf"}-{command}'
                if a.filter not in name:
                    continue
                case = out / name
                case.mkdir()
                seed = case / 'seed'
                run(git, ['init', '-q', seed], root)
                (seed / 'sub').mkdir()
                (seed / attr_path).parent.mkdir(parents=True, exist_ok=True)
                (seed / attr_path).write_text(attr)
                if kind == 'nested-unset':
                    (seed / '.gitattributes').write_text('* text=auto eol=lf\n')
                (seed / 'sub/a.txt').write_bytes(b'base\n')
                if kind == 'binary':
                    (seed / 'asset.png').write_bytes(b'\0PNG\r\n')
                run(git, ['add', '.'], seed)
                run(git, ['commit', '-qm', 'base'], seed)
                (seed / 'sub/a.txt').write_bytes(b'next\n')
                run(git, ['commit', '-qam', 'next'], seed)
                run(git, ['branch', 'other', 'HEAD~'], seed)
                remote = case / 'remote.git'
                run(git, ['clone', '-q', '--bare', seed, remote], root)
                run(git, ['remote', 'add', 'origin', remote.as_uri()], seed)
                if command in ('pull', 'pull-rebase'):
                    run(git, ['reset', '--hard', '-q', 'HEAD~'], seed)
                if command in ('status', 'add', 'commit', 'diff', 'checkout-path', 'restore') or crlf:
                    body = b'changed\r\n' if crlf else b'changed\n'
                    if kind == 'chunk-boundary':
                        body = b'x' * 65535 + body.replace(b'changed', b'')
                    if kind == 'nul':
                        body = b'\0' + body
                    if kind == 'bare-cr' and not crlf:
                        body = b'changed\rbare\n'
                    (seed / 'sub/a.txt').write_bytes(body)
                if kind == 'deleted':
                    (seed / attr_path).unlink()
                if command == 'diff-cached':
                    (seed / 'sub/a.txt').write_bytes(b'staged\n')
                    run(git, ['add', '.'], seed)
                results = {}
                before = state(seed)
                for label, tool in (('git', git), ('den', den)):
                    # Same pathname for equal remote diagnostics and reflog values.
                    work = case / 'work'
                    if work.exists():
                        shutil.rmtree(work)
                    shutil.copytree(seed, work, symlinks=True)
                    p = run(tool, argv, work, check=False)
                    results[label] = dict(status=p.returncode, stdout=p.stdout.hex(),
                                          stderr=p.stderr.hex(), state=state(work))
                if kind == 'binary':
                    got = results['den']
                    ok = got['status'] == 2 and b'worktree attributes: binary' in bytes.fromhex(got['stderr']) and got['state'] == before
                elif crlf and kind in converting:
                    got = results['den']
                    err = bytes.fromhex(got['stderr'])
                    ok = got['status'] == 2 and b'worktree attributes: text' in err and b'sub/a.txt' in err and got['state'] == before
                else:
                    ok = results['git'] == results['den']
                print(('PASS ' if ok else 'FAIL ') + name, flush=True)
                if not ok:
                    print(json.dumps(results), flush=True)
                rows.append(dict(name=name, passed=ok, **results))
    assert rows, 'empty selection'
    (out / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
    failed = sum(not r['passed'] for r in rows)
    print(f'text-attributes: {len(rows)} rows, {failed} failures; zero skips', flush=True)
    return int(failed != 0)


if __name__ == '__main__':
    raise SystemExit(main())
