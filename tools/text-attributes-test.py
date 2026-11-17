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

    def state(w, hashes=False):
        return dict(head=run(git, ['rev-parse', 'HEAD'], w).stdout.hex(),
                    index=run(git, ['ls-files', '-s'], w).stdout.hex(),
                    **{'file_sha256' if hashes else 'files': {
                        str(p.relative_to(w)): hashlib.sha256(p.read_bytes()).hexdigest() if hashes else p.read_bytes().hex()
                        for p in sorted(w.rglob('*'))
                        if '.git' not in p.relative_to(w).parts and p.is_file()}})

    commands = {
        'status': ['status', '--porcelain'],
        'add': ['add', 'sub/a.txt'],
        'commit': ['commit', '-qam', 'edit'],
        'checkout': ['checkout', '-q', 'other'],
        'checkout-path': ['checkout', '--', 'sub/a.txt'],
        'restore': ['restore', 'sub/a.txt'],
        'pull': ['pull', '--ff-only', 'origin', 'main'],
        'pull-rebase': ['pull', '--rebase', 'origin', 'main'],
        'pull-rebase-staged': ['pull', '--rebase', 'origin', 'main'],
        'pull-rebase-both': ['pull', '--rebase', 'origin', 'main'],
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
        'forced-nul': ('.gitattributes', '* text eol=lf\n'),
        'bare-cr': ('.gitattributes', '* text=auto eol=lf\n'),
        'binary': ('.gitattributes', '*.png binary\n'),
        'quote-literal': ('.gitattributes', 'sub/a"quoted.txt text=auto eol=lf\n'),
        'quoted-space': ('.gitattributes', '"sub/a quoted.txt" text=auto eol=lf\n'),
        'quoted-escaped': ('.gitattributes', '"sub/a\\"quoted.txt" text=auto eol=lf\n'),
        'history-autocrlf': (None, ''),
        'history-core-eol': (None, ''),
        'review-ignorecase': ('.gitattributes', '*.TXT text=auto eol=lf\n'),
        'review-case-sensitive': ('.gitattributes', '*.TXT text=auto eol=lf\n'),
        'review-ignorecase-range': ('.gitattributes', '[A-z].TXT text=auto eol=lf\n'),
        'review-meta-case': ('.GITATTRIBUTES', '* text\n'),
        'review-cr-separator': ('.gitattributes', '* text\rfoo\n'),
        'review-quote-close': ('.gitattributes', '"sub/a.txt"text\n'),
        'review-nul-line': ('.gitattributes', '* text\0junk\n'),
        'review-nul-reset': ('.gitattributes', '* text\0junk\n* -text\n'),
    }
    converting = {'auto-lf', 'text', 'auto', 'eol-lf', 'nested', 'info', 'deleted',
                  'chunk-boundary', 'forced-nul', 'bare-cr', 'quote-literal', 'quoted-space', 'quoted-escaped',
                  'review-ignorecase', 'review-ignorecase-range', 'review-cr-separator', 'review-quote-close', 'review-nul-line'}
    rows = []
    for kind, (attr_path, attr) in attrs.items():
        file_path = {'quote-literal': 'sub/a"quoted.txt', 'quoted-space': 'sub/a quoted.txt',
                     'quoted-escaped': 'sub/a"quoted.txt', 'review-ignorecase-range': 'sub/_.txt'}.get(kind, 'sub/a.txt')
        for command, base_argv in commands.items():
            # Pure index/tree readers must not acquire unrelated checkout
            # configuration refusals while sharing the attributes guard.
            if kind.startswith('history-') and command not in ('diff-cached', 'diff-tree', 'log-p', 'log-stat', 'show', 'show-root', 'log-root'):
                continue
            argv = [file_path if part == 'sub/a.txt' else part for part in base_argv]
            for crlf in (False, True):
                if crlf and command not in ('status', 'add', 'commit', 'checkout', 'checkout-path', 'restore', 'pull', 'pull-rebase', 'pull-rebase-staged', 'pull-rebase-both', 'diff'):
                    continue
                name = f'text-attributes-{kind}-{"crlf" if crlf else "lf"}-{command}'
                if a.filter not in name:
                    continue
                case = out / name
                case.mkdir()
                seed = case / 'seed'
                run(git, ['init', '-q', seed], root)
                if kind in ('review-ignorecase', 'review-ignorecase-range', 'review-case-sensitive'):
                    run(git, ['config', 'core.ignorecase', 'false' if kind == 'review-case-sensitive' else 'true'], seed)
                (seed / 'sub').mkdir()
                if attr_path is not None:
                    (seed / attr_path).parent.mkdir(parents=True, exist_ok=True)
                    (seed / attr_path).write_text(attr)
                if kind == 'nested-unset':
                    (seed / '.gitattributes').write_text('* text=auto eol=lf\n')
                (seed / file_path).write_bytes(b'base\n')
                if kind == 'binary':
                    (seed / 'asset.png').write_bytes(b'\0PNG\r\n')
                run(git, ['add', '.'], seed)
                run(git, ['commit', '-qm', 'base'], seed)
                (seed / file_path).write_bytes(b'next\n')
                run(git, ['commit', '-qam', 'next'], seed)
                run(git, ['branch', 'other', 'HEAD~'], seed)
                remote = case / 'remote.git'
                run(git, ['clone', '-q', '--bare', seed, remote], root)
                run(git, ['remote', 'add', 'origin', remote.as_uri()], seed)
                if kind == 'history-autocrlf':
                    run(git, ['config', 'core.autocrlf', 'true'], seed)
                if kind == 'history-core-eol':
                    run(git, ['config', 'core.eol', 'crlf'], seed)
                if command == 'pull' or command.startswith('pull-rebase'):
                    run(git, ['reset', '--hard', '-q', 'HEAD~'], seed)
                if command in ('status', 'add', 'commit', 'diff', 'checkout-path', 'restore', 'pull-rebase-staged', 'pull-rebase-both') or crlf:
                    body = b'changed\r\n' if crlf else b'changed\n'
                    if kind == 'chunk-boundary':
                        body = b'x' * 65535 + body.replace(b'changed', b'')
                    if kind in ('nul', 'forced-nul'):
                        body = b'\0' + body
                    if kind == 'bare-cr' and not crlf:
                        body = b'changed\rbare\n'
                    (seed / file_path).write_bytes(body)
                if command in ('pull-rebase-staged', 'pull-rebase-both'):
                    run(git, ['add', file_path], seed)
                    if command == 'pull-rebase-both':
                        with (seed / file_path).open('ab') as f:
                            f.write(b'additional unstaged\n')
                if kind == 'deleted':
                    (seed / attr_path).unlink()
                if command == 'diff-cached':
                    (seed / file_path).write_bytes(b'staged\n')
                    run(git, ['add', '.'], seed)
                results = {}
                before = state(seed)
                meta_case_active = kind == 'review-meta-case' and run(git, ['check-attr', 'text', '--', file_path], seed).stdout.endswith(b': text: set\n')
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
                elif crlf and (kind in converting or meta_case_active):
                    got = results['den']
                    err = bytes.fromhex(got['stderr'])
                    ok = got['status'] == 2 and b'worktree attributes: text' in err and file_path.encode() in err and got['state'] == before
                else:
                    ok = results['git'] == results['den']
                print(('PASS ' if ok else 'FAIL ') + name, flush=True)
                if not ok:
                    print(json.dumps(results), flush=True)
                rows.append(dict(name=name, passed=ok, **results))
    # Incoming attributes govern bytes installed by a transition, not the
    # outgoing worktree/index. Stage raw content before introducing the rule.
    for command, metadata in [(cmd, filename) for cmd in ('checkout', 'restore', 'pull')
                              for filename in ('.gitattributes', '.GITATTRIBUTES')]:
        for crlf in (False, True):
            suffix = '-metadata-alias' if metadata == '.GITATTRIBUTES' else ''
            name = f'text-attributes-review-incoming-{command}-{"crlf" if crlf else "lf"}{suffix}'
            if a.filter not in name:
                continue
            case = out / name
            case.mkdir()
            origin = case / 'origin'
            run(git, ['init', '-q', origin], root)
            (origin / 'a.txt').write_bytes(b'base\n')
            run(git, ['add', 'a.txt'], origin)
            run(git, ['commit', '-qm', 'base'], origin)
            remote = case / 'remote.git'
            run(git, ['clone', '-q', '--bare', origin, remote], root)
            seed = case / 'seed'
            run(git, ['clone', '-q', remote.as_uri(), seed], root)
            (origin / 'a.txt').write_bytes(b'next\r\n' if crlf else b'next\n')
            run(git, ['add', 'a.txt'], origin)
            (origin / metadata).write_text('a.txt text\n')
            run(git, ['add', metadata], origin)
            incoming_text = run(git, ['check-attr', 'text', '--', 'a.txt'], origin).stdout.endswith(b': text: set\n')
            run(git, ['commit', '-qm', 'incoming attributes'], origin)
            target = run(git, ['rev-parse', 'HEAD'], origin).stdout.decode().strip()
            run(git, ['push', '-q', remote.as_uri(), 'HEAD:refs/heads/main'], origin)
            run(git, ['fetch', '-q', 'origin'], seed)
            run(git, ['branch', 'incoming', target], seed)
            argv = {'checkout': ['checkout', '-q', 'incoming'],
                    'restore': ['restore', '--source=incoming', '--staged', '--worktree', '.'],
                    'pull': ['pull', '--ff-only', 'origin', 'main']}[command]
            before = state(seed)
            results = {}
            for label, tool in (('git', git), ('den', den)):
                work = case / 'work'
                if work.exists():
                    shutil.rmtree(work)
                shutil.copytree(seed, work, symlinks=True)
                p = run(tool, argv, work, check=False)
                results[label] = dict(status=p.returncode, stdout=p.stdout.hex(), stderr=p.stderr.hex(), state=state(work))
            if crlf and incoming_text:
                got = results['den']
                err = bytes.fromhex(got['stderr'])
                ok = got['status'] == 2 and b'worktree attributes: text' in err and b'a.txt' in err and got['state'] == before
            else:
                ok = results['git'] == results['den']
            print(('PASS ' if ok else 'FAIL ') + name, flush=True)
            if not ok:
                print(json.dumps(results), flush=True)
            rows.append(dict(name=name, passed=ok, **results))
    # Selected restore sources are overlays, not a replacement for all current
    # worktree metadata. A removed worktree file can expose the retained index.
    controls = [
        ('target-nested-unset', 'checkout', None, None, '* text\n', '*.txt -text\n', None, ''),
        ('target-nested-text', 'checkout', None, None, '* -text\n', '*.txt text\n', None, 'text'),
        ('target-info-unset', 'checkout', None, None, '* text\n', None, '* -text\n', ''),
        ('restore-unselected-attributes', 'worktree-file', '* -text\n', '* -text\n', '* text\n', None, None, ''),
        ('restore-unselected-acting-metadata', 'worktree-file', '* -text\n', '* -text\n', '* filter=lfs\n', None, None, ''),
        ('restore-selected-attributes', 'both', '* -text\n', '* -text\n', '* text\n', None, None, 'text'),
        ('restore-delete-index-fallback', 'worktree', '* text\n', '* -text\n', None, None, None, 'text'),
        ('restore-delete-both', 'both', '* text\n', '* -text\n', None, None, None, ''),
        ('restore-overlay-retain', 'overlay', '* -text\n', '* -text\n', None, None, None, ''),
        ('restore-staged-worktree-precedence', 'staged', '* -text\n', '* -text\n', '* text\n', None, None, ''),
        ('restore-staged-index-fallback', 'staged', '* -text\n', None, '* text\n', None, None, 'text'),
        ('restore-staged-acting-source', 'staged', None, None, '* filter=lfs\n', None, None, 'filter'),
    ]
    for kind, command, indexed, working, incoming, nested, info, refusal in controls:
        name = f'text-attributes-review-policy-{kind}'
        if a.filter not in name:
            continue
        case = out / name
        case.mkdir()
        seed = case / 'seed'
        run(git, ['init', '-q', seed], root)
        (seed / 'sub').mkdir()
        (seed / 'sub/a.txt').write_bytes(b'base\n')
        run(git, ['add', '.'], seed)
        run(git, ['commit', '-qm', 'base'], seed)
        old = run(git, ['rev-parse', 'HEAD'], seed).stdout.decode().strip()
        (seed / 'sub/a.txt').write_bytes(b'next\n' if refusal == 'filter' else b'next\r\n')
        run(git, ['add', 'sub/a.txt'], seed)
        if incoming is not None:
            (seed / '.gitattributes').write_text(incoming)
            run(git, ['add', '.gitattributes'], seed)
        if nested is not None:
            (seed / 'sub/.gitattributes').write_text(nested)
            run(git, ['add', 'sub/.gitattributes'], seed)
        run(git, ['commit', '-qm', 'incoming'], seed)
        run(git, ['branch', 'incoming'], seed)
        run(git, ['checkout', '-q', '-f', '--detach', old], seed)
        if indexed is not None:
            (seed / '.gitattributes').write_text(indexed)
            run(git, ['add', '.gitattributes'], seed)
            run(git, ['commit', '-qm', 'current metadata'], seed)
        if working is None:
            (seed / '.gitattributes').unlink(missing_ok=True)
        else:
            (seed / '.gitattributes').write_text(working)
        if info is not None:
            (seed / '.git/info').mkdir(exist_ok=True)
            (seed / '.git/info/attributes').write_text(info)
        argv = {
            'checkout': ['checkout', '-q', 'incoming'],
            'worktree-file': ['restore', '--source=incoming', '--worktree', 'sub/a.txt'],
            'worktree': ['restore', '--source=incoming', '--worktree', '.'],
            'both': ['restore', '--source=incoming', '--staged', '--worktree', '.'],
            'overlay': ['checkout', 'incoming', '--', '.'],
            'staged': ['restore', '--source=incoming', '--staged', '.'],
        }[command]
        before = state(seed)
        results = {}
        for label, tool in (('git', git), ('den', den)):
            work = case / 'work'
            if work.exists():
                shutil.rmtree(work)
            shutil.copytree(seed, work, symlinks=True)
            p = run(tool, argv, work, check=False)
            results[label] = dict(status=p.returncode, stdout=p.stdout.hex(), stderr=p.stderr.hex(), state=state(work))
        if refusal:
            got = results['den']
            err = bytes.fromhex(got['stderr'])
            ok = got['status'] == 2 and f'worktree attributes: {refusal}'.encode() in err and got['state'] == before
            if refusal == 'text':
                ok = ok and b'sub/a.txt' in err
        else:
            ok = results['git'] == results['den']
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok:
            print(json.dumps(results), flush=True)
        rows.append(dict(name=name, passed=ok, **results))
    # Boundaries retain SHA-256 file manifests rather than duplicating tens of
    # MiB of comment bytes in every capture. HEAD/index bytes remain explicit.
    bounds = [('file-exact', 1, 1048576, False, ''),
              ('file-over', 1, 1048577, False, '1048576'),
              ('staged-file-over', 1, 1048577, True, '1048576'),
              ('aggregate-exact', 16, 1048576, False, ''),
              ('staged-aggregate-exact', 16, 1048576, True, ''),
              ('aggregate-over', 17, 1048576, False, '16777216'),
              ('staged-aggregate-over', 17, 1048576, True, '16777216')]
    for kind, count, size, staged, limit in bounds:
        name = f'text-attributes-review-policy-limit-{kind}'
        if a.filter not in name:
            continue
        case = out / name
        case.mkdir()
        seed = case / 'seed'
        run(git, ['init', '-q', seed], root)
        (seed / 'a.txt').write_bytes(b'base\n')
        run(git, ['add', '.'], seed)
        run(git, ['commit', '-qm', 'base'], seed)
        old = run(git, ['rev-parse', 'HEAD'], seed).stdout.decode().strip()
        data = b'#' + b'x' * (size - 2) + b'\n'
        for i in range(count):
            directory = seed / f'rules-{i:02}'
            directory.mkdir()
            (directory / '.gitattributes').write_bytes(data)
        run(git, ['add', '.'], seed)
        run(git, ['commit', '-qm', 'incoming metadata boundary'], seed)
        run(git, ['branch', 'incoming'], seed)
        run(git, ['checkout', '-q', '-f', '--detach', old], seed)
        argv = ['restore', '--source=incoming', '--staged', '.'] if staged else ['checkout', '-q', 'incoming']
        before = state(seed, hashes=True)
        results = {}
        for label, tool in (('git', git), ('den', den)):
            work = case / 'work'
            if work.exists():
                shutil.rmtree(work)
            shutil.copytree(seed, work, symlinks=True)
            p = run(tool, argv, work, check=False)
            results[label] = dict(status=p.returncode, stdout=p.stdout.hex(), stderr=p.stderr.hex(), state=state(work, hashes=True))
        if limit:
            got = results['den']
            err = bytes.fromhex(got['stderr'])
            ok = got['status'] == 128 and b'limit:' in err and limit.encode() in err and got['state'] == before
        else:
            ok = results['git'] == results['den']
        print(('PASS ' if ok else 'FAIL ') + name, flush=True)
        if not ok:
            print(json.dumps(results), flush=True)
        rows.append(dict(name=name, passed=ok, **results))
    # A revert can synthesize a blob which has not been published yet. The
    # safety preflight must inspect that supplied content, not require storage.
    name = 'text-attributes-review-policy-revert-synthesized-lf'
    if a.filter in name:
        case = out / name
        case.mkdir()
        seed = case / 'seed'
        run(git, ['init', '-q', seed], root)
        (seed / '.gitattributes').write_text('* text\n')
        lines = [f'line {i}\n' for i in range(12)]
        (seed / 'a.txt').write_text(''.join(lines))
        run(git, ['add', '.'], seed)
        run(git, ['commit', '-qm', 'base'], seed)
        lines[2] = 'target edit\n'
        (seed / 'a.txt').write_text(''.join(lines))
        run(git, ['commit', '-qam', 'target'], seed)
        target = run(git, ['rev-parse', 'HEAD'], seed).stdout.decode().strip()
        lines[9] = 'retained edit\n'
        (seed / 'a.txt').write_text(''.join(lines))
        run(git, ['commit', '-qam', 'later'], seed)
        results = {}
        for label, tool in (('git', git), ('den', den)):
            work = case / 'work'
            if work.exists():
                shutil.rmtree(work)
            shutil.copytree(seed, work, symlinks=True)
            p = run(tool, ['revert', '--no-edit', target], work, check=False)
            results[label] = dict(status=p.returncode, stdout=p.stdout.hex(), stderr=p.stderr.hex(), state=state(work))
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
