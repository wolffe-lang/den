#!/usr/bin/env python3
"""vc24: rev-parse (den#69), the forms scripts use, held to the pinned Git
byte for byte (stdout, stderr, exit status).

    tools/env python3 -I tools/rev-parse-test.py --tier native [--field]

The fixture, built by the pinned Git: a repository with history, tags (a
lightweight and an annotated one), a subdirectory, branches with and without
an upstream (a configured remote's tracking ref, a local "." upstream, an
unmapped one, a gone one), a bare repository, an unborn repository, a detached
checkout, and a directory outside any repository. Each row runs Git, then den,
in the same directory, and compares. No row is skipped or reviewed.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

GIT_SHA256 = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    parser.add_argument('--field', action='store_true', help='a Git other than the pinned one (macOS field leg)')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    git = str(Path(os.environ['DEN_GIT']).resolve())
    if not args.field:
        assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == GIT_SHA256, 'pinned Git digest'
    den = root / 'target' / args.tier / 'den'
    if not den.is_file():
        raise SystemExit('FAIL rev-parse-input: build target/' + args.tier + '/den first')
    out = root / 'target/runs' / ('rev-parse-' + args.tier)
    if out.exists():
        raise SystemExit('FAIL rev-parse-fresh-output: select a fresh build directory')
    out.mkdir(parents=True)
    env = dict(os.environ)

    def g(cwd, *argv):
        result = subprocess.run([git, *map(str, argv)], cwd=str(cwd), env=env, capture_output=True, timeout=120)
        if result.returncode:
            raise AssertionError('pinned Git %s: %s' % (argv[0], result.stderr.decode(errors='replace')[-300:]))
        return result.stdout.decode().strip()

    up = out / 'up.git'
    g(out, 'init', '-q', '--bare', '-b', 'main', up)
    w = out / 'w'
    g(out, 'init', '-q', '-b', 'main', w)
    (w / 'sub/deep').mkdir(parents=True)
    (w / 'f').write_text('one\n')
    (w / 'sub/deep/g').write_text('deep\n')
    g(w, 'add', '.')
    g(w, 'commit', '-q', '-m', 'one')
    g(w, 'tag', 'v1')
    g(w, 'tag', '-a', '-m', 'annotated', 'v2')
    (w / 'f').write_text('two\n')
    g(w, 'commit', '-q', '-a', '-m', 'two')
    g(w, 'remote', 'add', 'origin', up.as_uri())
    g(w, 'push', '-q', '-u', 'origin', 'main')
    g(w, 'branch', 'nou')
    g(w, 'branch', 'dot')
    g(w, 'branch', '--set-upstream-to=main', 'dot')
    g(w, 'branch', 'gone')
    g(w, 'config', 'branch.gone.remote', 'origin')
    g(w, 'config', 'branch.gone.merge', 'refs/heads/gone')
    g(w, 'branch', 'unmapped')
    g(w, 'config', 'branch.unmapped.remote', 'origin')
    g(w, 'config', 'branch.unmapped.merge', 'refs/heads/elsewhere')
    g(w, 'config', 'remote.origin.fetch', '+refs/heads/main:refs/remotes/origin/main')
    g(w, 'branch', 'x')
    g(w, 'tag', 'x')
    detached = out / 'detached'
    g(out, 'clone', '-q', w, detached)
    g(detached, 'checkout', '-q', '--detach', 'HEAD~1')
    unborn = out / 'unborn'
    g(out, 'init', '-q', '-b', 'main', unborn)
    outside = out / 'outside'
    outside.mkdir()
    head = g(w, 'rev-parse', 'HEAD')

    rows = []
    for argv in (['HEAD'], ['main', 'v1', 'v2'], ['--verify', 'HEAD'], ['--verify', 'v2'], ['--verify', 'v2^{}'],
                 ['--verify', 'nosuch'], ['--verify', '-q', 'nosuch'], ['-q', '--verify', 'nosuch'],
                 ['--quiet', '--verify', 'nosuch'], ['--verify', '--quiet', 'HEAD'], ['nosuch'],
                 ['--verify', 'HEAD', 'main'], ['--verify'], ['--verify', 'HEAD', '--'], ['HEAD', '--', 'f'],
                 ['--', 'f'], ['f'], ['@{u}'], ['@{upstream}'], ['@{U}'], ['main@{u}'], ['main@{upstream}'],
                 ['--verify', '@{u}'], ['--abbrev-ref', 'HEAD'], ['--abbrev-ref', '@{u}'], ['--abbrev-ref', 'dot@{u}'],
                 ['--abbrev-ref', 'main', 'v1'], ['--abbrev-ref', 'HEAD~1'], ['--abbrev-ref', head],
                 ['--abbrev-ref', 'origin/main'], ['--abbrev-ref', 'refs/heads/main'], ['--abbrev-ref', 'x'],
                 ['nou@{u}'], ['--abbrev-ref', 'nou@{u}'], ['--verify', 'nou@{u}'], ['--verify', '-q', 'nou@{u}'],
                 ['gone@{u}'], ['--abbrev-ref', 'gone@{u}'], ['unmapped@{u}'], ['nosuchbranch@{u}'],
                 ['--symbolic-full-name', 'HEAD'], ['--symbolic-full-name', '@{u}'], ['--symbolic-full-name', 'main'],
                 ['--symbolic-full-name', 'v1'], ['--symbolic-full-name', 'HEAD~1'],
                 ['--short', 'HEAD'], ['--short=12', 'HEAD'], ['--short=2', 'HEAD'], ['--verify', '--short', 'HEAD'],
                 ['HEAD~1'], ['HEAD^{tree}'], ['HEAD:f'], ['HEAD:nosuch'], ['v2^{commit}'],
                 ['--show-toplevel'], ['--git-dir'], ['--absolute-git-dir'], ['--is-inside-work-tree'],
                 ['--is-inside-git-dir'], ['--is-bare-repository'], ['--show-prefix'], ['--show-cdup'],
                 ['--git-dir', '--show-toplevel', '--is-inside-work-tree', 'HEAD'], ['--parseopt']):
        rows.append(('top', w, argv))
    for argv in (['--show-toplevel'], ['--git-dir'], ['--is-inside-work-tree'], ['--abbrev-ref', 'HEAD'],
                 ['--show-prefix'], ['--show-cdup'], ['HEAD'], ['HEAD:f'], ['g']):
        rows.append(('subdir', w / 'sub/deep', argv))
    for argv in (['--show-toplevel'], ['--git-dir'], ['--is-inside-work-tree'], ['--is-inside-git-dir'],
                 ['--is-bare-repository'], ['HEAD']):
        rows.append(('dotgit', w / '.git', argv))
    rows.append(('dotgit-refs', w / '.git/refs', ['--git-dir']))
    rows.append(('dotgit-refs', w / '.git/refs', ['--is-inside-work-tree']))
    for argv in (['--show-toplevel'], ['--git-dir'], ['--is-inside-work-tree'], ['--is-inside-git-dir'],
                 ['--is-bare-repository'], ['HEAD'], ['--abbrev-ref', 'HEAD'], ['--verify', 'main']):
        rows.append(('bare', up, argv))
    for argv in (['--abbrev-ref', 'HEAD'], ['@{u}'], ['--abbrev-ref', '@{u}'], ['--symbolic-full-name', 'HEAD'],
                 ['HEAD']):
        rows.append(('detached', detached, argv))
    for argv in (['HEAD'], ['--verify', 'HEAD'], ['--verify', '-q', 'HEAD'], ['--abbrev-ref', 'HEAD'],
                 ['--show-toplevel'], ['@{u}'], ['--git-dir']):
        rows.append(('unborn', unborn, argv))
    for argv in (['HEAD'], ['--verify', 'HEAD'], ['--show-toplevel'], ['--git-dir'], ['--is-inside-work-tree'],
                 ['--abbrev-ref', 'HEAD']):
        rows.append(('outside', outside, argv))

    failed, passed = [], 0
    for place, cwd, argv in rows:
        name = 'rev-parse-%s-%s' % (place, '_'.join(a.replace('/', '-') for a in argv) or 'none')
        name = ''.join(c if c.isalnum() or c in '-_.=' else '-' for c in name)[:120]
        results = []
        # git(1) GIT_CEILING_DIRECTORIES keeps the outside directory outside
        # the checkout this harness runs in.
        extra = dict(GIT_CEILING_DIRECTORIES=str(out)) if place == 'outside' else {}
        for binary in (git, str(den)):
            result = subprocess.run([binary, 'rev-parse', *argv], cwd=str(cwd), env={**env, **extra},
                                    capture_output=True, timeout=120)
            results.append((result.returncode, result.stdout, result.stderr))
        (oracle, candidate) = results
        problems = []
        for i, field in enumerate(('exit', 'stdout', 'stderr')):
            if oracle[i] != candidate[i]:
                problems.append('%s: git %r den %r' % (field, oracle[i], candidate[i]))
        if argv == ['--parseopt']:
            # Not implemented: the oracle's strict not-yet case names it.
            want = (2, b'', b'den: not yet implemented: rev-parse (M3, vc10)\n')
            problems = [] if candidate == want else ['den %r, want the named not-yet refusal' % (candidate,)]
        if problems:
            failed.append(name)
            print('FAIL ' + name + ' ' + '; '.join(problems), flush=True)
        else:
            passed += 1
            print('PASS ' + name, flush=True)
    shutil.rmtree(out / 'unborn', ignore_errors=True)
    if failed:
        raise SystemExit('FAIL rev-parse: %d of %d rows: %s' % (len(failed), len(failed) + passed, ', '.join(failed)))
    print('rev-parse: %s %d rows; zero skips' % (args.tier, passed), flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit('FAIL rev-parse-harness: ' + str(exc))
