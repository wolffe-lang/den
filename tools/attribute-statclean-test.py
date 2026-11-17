#!/usr/bin/env python3
"""Stat-clean entries under attributes that would change their bodies.

Git takes a tracked file whose lstat matches its index entry as that entry's
blob, unread, whatever its attributes say; only a changed or racily clean
file is read and converted. Each shape below is seeded with the pinned Git,
copied once per tool and refreshed there by the pinned Git, so its entries
are stat-clean (the copy's mtimes are a second older than the index):

  crlf-under-text  a CR-LF body committed raw, then `* text` in
                   info/attributes after the refresh: cleaning it would
                   change it, but Git never reads it.
  eol-crlf         a checkout under a committed `* text eol=crlf`: CR-LF in
                   the work tree, LF blobs in the index.
  ident            a checkout under a committed `*.c ident`: `$Id$` expanded
                   in the work tree.

statclean rows: status, short status, diff, diff --quiet and diff --stat
must equal the pinned Git's exit status, stdout and stderr, and leave the
files as they were.

touched rows: the same file rewritten with its own bytes after the refresh
(new ctime and mtime, so it is read): den still refuses by the attribute's
name and the path, exit 2, and changes nothing. Line-ending conversion and
identity attributes on a body den reads are a later step.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

SHAPES = {
    'crlf-under-text': dict(path='a.txt', refusal='text at a.txt (CR-LF conversion)'),
    'eol-crlf': dict(path='a.txt', refusal='eol at a.txt'),
    'ident': dict(path='a.c', refusal='ident at a.c'),
}
COMMANDS = {
    'status': ['status'],
    'status-short': ['status', '--short'],
    'diff': ['diff'],
    'diff-quiet': ['diff', '--quiet'],
    'diff-stat': ['diff', '--stat'],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--den')
    parser.add_argument('--filter', default='')
    parser.add_argument('--dev-oracle', action='store_true', help='Darwin development evidence only; not the pinned Linux oracle')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target/runs' / ('attribute-statclean-' + a.tier)
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
    den = a.den or str(root / 'target' / a.tier / 'den')
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=str(out / 'gitconfig'), GIT_OPTIONAL_LOCKS='0')
    (out / 'gitconfig').write_text('[user]\n\tname = Den Tester\n\temail = den@example.invalid\n'
                                   '[core]\n\tautocrlf = false\n[init]\n\tdefaultBranch = main\n')

    def run(args, cwd, check=True):
        p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, env=env)
        if check:
            assert p.returncode == 0, (args, p.stdout, p.stderr)
        return p

    def seed(shape):
        base = out / ('seed-' + shape)
        base.mkdir()
        origin = base / 'origin'
        run([git, 'init', '-q', origin], base)
        if shape == 'crlf-under-text':
            (origin / 'a.txt').write_bytes(b'one\r\ntwo\r\n')
        elif shape == 'eol-crlf':
            (origin / '.gitattributes').write_bytes(b'* text eol=crlf\n')
            (origin / 'a.txt').write_bytes(b'one\ntwo\n')
        else:
            (origin / '.gitattributes').write_bytes(b'*.c ident\n')
            (origin / 'a.c').write_bytes(b'/* $Id$ */\nint x;\n')
        (origin / 'b.txt').write_bytes(b'plain\n')
        run([git, 'add', '.'], origin)
        run([git, 'commit', '-qm', 'base'], origin)
        work = base / 'seed'
        run([git, 'clone', '-q', origin, work], base)
        run([git, 'config', 'gc.auto', '0'], work)
        return work

    def files(w):
        found = {}
        for p in sorted(w.rglob('*')):
            if '.git' in p.relative_to(w).parts or not p.is_file():
                continue
            found[str(p.relative_to(w))] = p.read_bytes().hex()
        return found

    seeds = {shape: seed(shape) for shape in SHAPES}
    # The copies' mtimes stay those of the seeds; the refresh after this
    # pause writes an index a second later, so no entry is racily clean.
    time.sleep(1.1)

    def prepared(shape, kind):
        w = out / 'work'
        if w.exists():
            shutil.rmtree(w)
        shutil.copytree(seeds[shape], w, symlinks=True)
        run([git, 'update-index', '-q', '--refresh'], w)
        if shape == 'crlf-under-text':
            (w / '.git/info').mkdir(exist_ok=True)
            (w / '.git/info/attributes').write_bytes(b'* text\n')
        if kind == 'touched':
            target = w / SHAPES[shape]['path']
            body = target.read_bytes()
            time.sleep(0.01)
            target.write_bytes(body)
        return w

    rows = []
    for shape, facts in SHAPES.items():
        for command, argv in COMMANDS.items():
            row = f'attribute-statclean-{shape}-{command}'
            if a.filter in row:
                res = {}
                for label, tool in (('git', git), ('den', den)):
                    w = prepared(shape, 'statclean')
                    before = files(w)
                    p = run([tool, *argv], w, check=False)
                    res[label] = dict(status=p.returncode, stdout=p.stdout.hex(), stderr=p.stderr.hex(),
                                      files_kept=files(w) == before)
                same = all(res['git'][k] == res['den'][k] for k in res['git'])
                detail = '' if same else ' den exit %d stderr %r differs in %s' % (
                    res['den']['status'], bytes.fromhex(res['den']['stderr'])[-200:],
                    ','.join(k for k in res['git'] if res['git'][k] != res['den'][k]))
                print(('PASS ' if same else 'FAIL ') + row + detail, flush=True)
                rows.append(dict(row=row, passed=same, **res))
            row = f'attribute-statclean-{shape}-touched-{command}'
            if a.filter in row:
                w = prepared(shape, 'touched')
                before = files(w)
                index_before = (w / '.git/index').read_bytes()
                p = run([den, *argv], w, check=False)
                expected = f'den: not yet implemented: worktree attributes: {facts["refusal"]}\n'.encode()
                ok = p.returncode == 2 and p.stderr == expected and p.stdout == b'' and \
                    files(w) == before and (w / '.git/index').read_bytes() == index_before
                print(('PASS ' if ok else 'FAIL ') + row + ('' if ok else ' den exit %d stdout %r stderr %r' % (
                    p.returncode, p.stdout[-120:], p.stderr[-200:])), flush=True)
                rows.append(dict(row=row, passed=ok, status=p.returncode, stdout=p.stdout.hex(),
                                 stderr=p.stderr.hex(), expected=expected.decode()))
    assert rows, 'empty selection'
    (out / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n')
    failures = sum(not r['passed'] for r in rows)
    print(f'attribute-statclean: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    return int(failures > 0)


if __name__ == '__main__':
    raise SystemExit(main())
