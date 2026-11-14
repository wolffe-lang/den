#!/usr/bin/env python3
"""Attribute files den need not act on, and the ones it refuses by name.

accepted rows: a repository whose .gitattributes files set only attributes
that change nothing den does (text and crlf unset, whitespace, export and
delta, unspecified diff and merge, names Git gives no meaning). Status, add,
commit -a, a fast-forward pull, a true-merge pull and a switch must equal the
pinned Git's exit status, stdout, stderr, HEAD, index and files byte for byte,
including CRLF bodies, which neither tool converts.

refused rows: an attributes file that sets something den would have to act on
(line-ending conversion, eol, filters, ident, an encoding, diff or merge
drivers, the binary macro, a macro definition) makes den refuse by the
attribute's and the file's name, exit 2, and change nothing.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ACCEPTED = {
    'pax-notes': ('notes/px/.gitattributes',
                  '# Raw terminal evidence: CR and ANSI bytes are data.\n*.tty -text -whitespace\n'
                  '*.log -text -whitespace\ncensus/*.out -text -whitespace\n'),
    'root-unset': ('.gitattributes', '* -text\n*.c whitespace=trailing-space\n'),
    'export-delta': ('.gitattributes', '/notes export-ignore\n*.bin -delta\nVERSION export-subst\n'),
    'unspecified': ('.gitattributes', '*.tty !diff !merge !eol !text\n"quoted name.tty" -crlf\n'),
    'unknown-names': ('notes/.gitattributes', '*.tty linguist-generated=true owner=docs\n'),
}
REFUSED = {
    'text-set': ('.gitattributes', '*.tty text\n', 'text'),
    'text-auto': ('notes/.gitattributes', '* text=auto\n', 'text'),
    'eol': ('.gitattributes', '*.tty -text eol=crlf\n', 'eol'),
    'filter': ('.gitattributes', '*.tty filter=lfs\n', 'filter'),
    'ident': ('.gitattributes', '*.c ident\n', 'ident'),
    'encoding': ('.gitattributes', '*.utf16 working-tree-encoding=UTF-16\n', 'working-tree-encoding'),
    'diff-unset': ('.gitattributes', '*.tty -diff\n', 'diff'),
    'merge-driver': ('.gitattributes', '*.tty merge=ours\n', 'merge'),
    'binary': ('.gitattributes', '*.tty binary\n', 'binary'),
    'macro': ('.gitattributes', '[attr]evidence -text -diff\n*.tty evidence\n', 'macro definition'),
}
COMMANDS = {
    'status': (['status'], False),
    'status-short': (['status', '--short', '--untracked-files=all'], False),
    'commit-all': (['commit', '-qam', 'local edit'], True),
    'pull-ff': (['pull', 'origin', 'main'], False),
    'pull-merge': (['pull', '--no-rebase', 'origin', 'main'], False),
    'pull-rebase': (['pull', '--rebase', 'origin', 'main'], False),
    'switch': (['checkout', '-q', 'origin/main'], False),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--den')
    parser.add_argument('--filter', default='')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target/runs' / ('attributes-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = a.den or str(root / 'target' / a.tier / 'den')
    os.environ['GIT_MERGE_AUTOEDIT'] = 'no'

    def run(args, cwd, check=True):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True)
        if check:
            assert p.returncode == 0, (args, p.stdout, p.stderr)
        return p

    def seed(name, attr_path, attr_text, mode):
        base = out / f'seed-{name}-{mode}'
        base.mkdir()
        origin, remote, work = base / 'origin', base / 'remote.git', base / 'seed'
        run([git, 'init', '-q', origin], root)
        (origin / 'notes' / 'px' / 'census').mkdir(parents=True)
        (origin / 'notes' / 'px' / 'session.tty').write_bytes(b'$ den status\r\n\x1b[1mclean\x1b[0m\r\n')
        (origin / 'notes' / 'px' / 'census' / 'one.out').write_bytes(b'count 1\r\n')
        (origin / 'quoted name.tty').write_bytes(b'q\r\n')
        (origin / 'a').write_text('before\n')
        (origin / attr_path).parent.mkdir(parents=True, exist_ok=True)
        (origin / attr_path).write_text(attr_text)
        run([git, 'add', '.'], origin)
        run([git, 'commit', '-qm', 'base'], origin)
        run([git, 'clone', '-q', '--bare', origin, remote], root)
        run([git, 'clone', '-q', remote.as_uri(), work], root)
        run([git, 'config', 'gc.auto', '0'], work)
        if mode in ('pull-merge', 'pull-rebase'):
            (work / 'b').write_text('local independent change\n')
            run([git, 'add', 'b'], work)
            run([git, 'commit', '-qm', 'local'], work)
        if mode in ('pull-ff', 'pull-merge', 'pull-rebase', 'switch'):
            (origin / 'notes' / 'px' / 'session.tty').write_bytes(b'$ den pull\r\nUpdating\r\n')
            (origin / 'notes' / 'px' / 'census' / 'two.out').write_bytes(b'count 2\r\n')
            (origin / 'a').write_text('after\n')
            run([git, 'add', '.'], origin)
            run([git, 'commit', '-qm', 'next'], origin)
            run([git, 'push', '-q', remote.as_uri(), 'HEAD:refs/heads/main'], origin)
            if mode == 'switch':
                run([git, 'fetch', '-q', 'origin'], work)
        if mode in ('status', 'status-short', 'commit-all'):
            (work / 'notes' / 'px' / 'session.tty').write_bytes(b'$ den log\r\nlocal\r\n')
            (work / 'notes' / 'px' / 'scratch.log').write_bytes(b'untracked\r\n')
        return work

    def files(w):
        found = {}
        for p in sorted(w.rglob('*')):
            if '.git' in p.relative_to(w).parts or not p.is_file():
                continue
            found[str(p.relative_to(w))] = p.read_bytes().hex()
        return found

    def observe(tool, argv, w):
        p = run([tool, *argv], w, check=False)
        head = run([git, 'rev-parse', 'HEAD'], w).stdout.decode().strip()
        index = run([git, 'ls-files', '-s'], w).stdout.decode()
        return dict(status=p.returncode, stdout=p.stdout.hex(), stderr=p.stderr.hex(), head=head, index=index, files=files(w))

    rows = []
    for name, (attr_path, attr_text) in ACCEPTED.items():
        for command, (argv, _) in COMMANDS.items():
            row = f'attributes-accepted-{name}-{command}'
            if a.filter not in row:
                continue
            s = seed(name, attr_path, attr_text, command)
            res = {}
            for label, tool in (('git', git), ('den', den)):
                w = out / 'work'
                if w.exists():
                    shutil.rmtree(w)
                shutil.copytree(s, w, symlinks=True)
                res[label] = observe(tool, argv, w)
            same = all(res['git'][k] == res['den'][k] for k in res['git'])
            detail = '' if same else ' den stderr ' + repr(bytes.fromhex(res['den']['stderr'])[-200:]) + \
                ' differs in ' + ','.join(k for k in res['git'] if res['git'][k] != res['den'][k])
            print(('PASS ' if same else 'FAIL ') + row + detail, flush=True)
            rows.append(dict(row=row, passed=same, **res))
    for name, (attr_path, attr_text, refusal) in REFUSED.items():
        for command in ('status', 'pull-ff', 'pull-merge', 'pull-rebase', 'switch'):
            row = f'attributes-refused-{name}-{command}'
            if a.filter not in row:
                continue
            argv = COMMANDS[command][0]
            s = seed(name, attr_path, attr_text, command)
            w = out / 'work'
            if w.exists():
                shutil.rmtree(w)
            shutil.copytree(s, w, symlinks=True)
            before_head = run([git, 'rev-parse', 'HEAD'], w).stdout.decode().strip()
            before_index = run([git, 'ls-files', '-s'], w).stdout.decode()
            before_files = files(w)
            got = observe(den, argv, w)
            expected_tail = f'den: not yet implemented: worktree attributes: {refusal}\n'.encode()
            stderr = bytes.fromhex(got['stderr'])
            # A pull prints its fetch lines first; the refusal is the last line.
            ok = got['status'] == 2 and stderr.endswith(expected_tail) and \
                stderr.count(b'not yet implemented') == 1 and got['index'] == before_index and \
                got['files'] == before_files and (got['head'] == before_head)
            print(('PASS ' if ok else 'FAIL ') + row + ('' if ok else f' den exit {got["status"]} stderr {stderr[-200:]!r}'), flush=True)
            rows.append(dict(row=row, passed=ok, den=got, expected=expected_tail.decode()))
    assert rows, 'empty selection'
    (out / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
    failures = sum(not r['passed'] for r in rows)
    print(f'attributes: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
