#!/usr/bin/env python3
"""den#185: a transition refuses or completes as Git does, never half-applied.

A merge (a fast-forward or a true merge), checkout, switch, reset --hard or
cherry-pick moves the work tree toward a target whose new paths may find
something in their way: an untracked or ignored file, a symlink or a staged
file where a new path needs a directory, or a directory where a new path is a
file. Each case runs the pinned Git and den on fresh copies of the same work
tree, under tools/env. A cell passes when den's exit status, stdout and stderr,
HEAD, refs, ORIG_HEAD and AUTO_MERGE, index entries and work tree equal Git's;
and, where Git refuses (its HEAD, refs, index bytes and work tree unchanged),
when den's index bytes, work tree, HEAD and refs are byte-identical to before.

Two of Git's results here remove what the user had, and den follows Git, each
in rows of their own:
  ignored-lead-removed, ignored-deep-removed, ignored-dir-removed
      an ignored file, or a directory holding only ignored files, in the way is
      removed and the transition completes;
  staged-addition-dropped
      a staged new file in the way, unchanged in the work tree, where
      core.ignorecase is set, is dropped from the index and the work tree, and
      the merge, checkout or switch completes (its blob stays in the object
      store). Git sets core.ignorecase in a repository on a case-insensitive
      file system, as macOS's is by default; where it is unset, as on Linux,
      Git refuses that file as untracked (staged-addition-refused). Each of the
      two rows sets it, so every host reads both.

The fixture is made with Git alone: main tracks d0/s0/f0.txt, d1/s0/f0.txt,
keep.txt, tz, lf, q/x and r.txt; target changes d0/s0/f0.txt, q/x and r.txt,
makes tz and lf directories (tz/new.txt, lf/x.txt) and adds zz/new.txt,
a/b/c/d.txt and yy.txt; local changes d1/s0/f0.txt, so merging target into it
is a true merge. The cases come from a sweep of every kind of thing in a written
path's way against Git (tracked unchanged, changed, deleted or replaced; staged;
untracked; ignored; as a file, symlink, directory or nothing; at the path or at
a directory it needs). A true merge over a dirty or staged path is den's named
limit (`merge dirty recursive recovery`); those cells are skipped by name.

gitlink-kept has a fixture of its own, made with Git alone: main tracks a.txt
and three submodules, sm, same and gone, each checked out in the work tree (sm
at main's commit); target changes a.txt, moves sm to a new commit and removes
gone. A submodule's directory is a directory where its gitlink is, and Git
leaves each as it is in every one of these commands (gone with its "unable to
rmdir" warning).
"""
import argparse
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

COMMANDS = {
    'ff': ('main', ['merge', 'target']),
    'true': ('local', ['merge', '-m', 'merged', 'target']),
    'checkout': ('main', ['checkout', 'target']),
    'switch': ('main', ['switch', 'target']),
    'reset': ('main', ['reset', '--hard', 'target']),
    'pick': ('main', ['cherry-pick', 'target']),
}
# row: (cases, commands); the reset row holds every obstruction's reset cell.
ROWS = {
    'untracked-lead': (['untracked-lead'], 'nonreset'),
    'symlink-lead': (['symlink-lead'], 'nonreset'),
    'index-lead-dirty': (['index-lead-dirty'], 'nonreset'),
    'untracked-deep': (['untracked-deep'], 'nonreset'),
    'two-untracked': (['two-untracked'], 'nonreset'),
    'untracked-dir': (['untracked-dir'], 'nonreset'),
    # all three of Git's lists at once: their order and texts.
    'three-kinds': (['three-kinds'], 'nonreset'),
    # Git removes what the user had here, and den follows Git: each has a row of its own.
    'ignored-lead-removed': (['ignored-lead'], 'nonreset'),
    'ignored-deep-removed': (['ignored-deep'], 'nonreset'),
    'ignored-dir-removed': (['untracked-dir-ignored'], 'nonreset'),
    'staged-addition-dropped': (['index-lead'], 'nonreset'),
    # the same file where core.ignorecase is unset: Git refuses it as untracked.
    'staged-addition-refused': (['index-lead-exact'], 'nonreset'),
    # the rest of the family, from the sweep against Git: a tracked path's directory, or the path itself, taken by
    # something else; a tracked path the target removes, become a directory; a staged addition gone from disk.
    'tracked-under-file': (['tracked-under-file'], 'nonreset'),
    'tracked-under-symlink': (['tracked-under-symlink'], 'nonreset'),
    'tracked-under-ignored': (['tracked-under-ignored'], 'nonreset'),
    'tracked-became-directory': (['tracked-became-directory'], 'nonreset'),
    'removed-became-directory': (['removed-became-directory'], 'nonreset'),
    'staged-addition-gone': (['staged-addition-gone'], 'nonreset'),
    # a submodule's checked-out directory is not in its gitlink's way, the gitlink moved, unchanged or removed.
    'gitlink-kept': (['gitlink'], 'gitlink'),
    'reset': (['untracked-lead', 'symlink-lead', 'untracked-deep', 'two-untracked', 'untracked-dir', 'three-kinds',
               'ignored-lead', 'ignored-deep', 'untracked-dir-ignored', 'index-lead', 'index-lead-exact',
               'index-lead-dirty', 'tracked-under-file', 'tracked-under-symlink', 'tracked-under-ignored',
               'tracked-became-directory', 'removed-became-directory', 'staged-addition-gone'], 'reset'),
    'dirty': (['dirty'], 'all'),
    'untracked-same': (['untracked-same'], 'all'),
    'index-same': (['index-same'], 'all'),
    'tracked-lead-dirty': (['tracked-lead-dirty'], 'all'),
}
NAMED_LIMIT = {('dirty', 'true'), ('index-same', 'true'), ('index-lead', 'true'), ('index-lead-exact', 'true'),
               ('index-lead-dirty', 'true'), ('tracked-lead-dirty', 'true'), ('three-kinds', 'true'),
               ('tracked-under-file', 'true'), ('tracked-under-symlink', 'true'), ('tracked-under-ignored', 'true'),
               ('tracked-became-directory', 'true'), ('removed-became-directory', 'true'),
               ('staged-addition-gone', 'true')}
PSEUDO = ('ORIG_HEAD', 'AUTO_MERGE', 'MERGE_HEAD', 'MERGE_MSG', 'MERGE_MODE', 'CHERRY_PICK_HEAD')


def exclude(work, pattern):
    (work / '.git/info').mkdir(exist_ok=True)
    with open(work / '.git/info/exclude', 'a') as handle:
        handle.write(pattern + '\n')


def obstruct(work, name, run):
    def write(rel, text):
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_text(text)
    if name == 'dirty':
        write('d0/s0/f0.txt', 'dirty\n')
    elif name == 'untracked-same':
        write('yy.txt', 'untracked\n')
    elif name == 'untracked-lead':
        write('zz', 'untracked\n')
    elif name == 'symlink-lead':
        os.symlink('keep.txt', work / 'zz')
    elif name == 'untracked-deep':
        write('a/b', 'untracked\n')
    elif name == 'two-untracked':
        write('zz', 'untracked\n')
        write('a/b', 'untracked\n')
    elif name == 'untracked-dir':
        write('yy.txt/x', 'untracked\n')
    elif name == 'three-kinds':
        write('d0/s0/f0.txt', 'dirty\n')
        write('yy.txt/x', 'untracked\n')
        write('zz', 'untracked\n')
        write('a/b', 'untracked\n')
    elif name == 'ignored-lead':
        exclude(work, 'zz')
        write('zz', 'ignored\n')
    elif name == 'ignored-deep':
        exclude(work, 'a/b')
        write('a/b', 'ignored\n')
    elif name == 'untracked-dir-ignored':
        exclude(work, '*.o')
        write('yy.txt/x.o', 'ignored\n')
    elif name == 'index-same':
        write('yy.txt', 'staged\n')
        run(['add', 'yy.txt'], work)
    elif name == 'index-lead':
        run(['config', 'core.ignorecase', 'true'], work)
        write('zz', 'staged\n')
        run(['add', 'zz'], work)
    elif name == 'index-lead-exact':
        run(['config', 'core.ignorecase', 'false'], work)
        write('zz', 'staged\n')
        run(['add', 'zz'], work)
    elif name == 'gitlink':
        pass
    elif name == 'index-lead-dirty':
        write('zz', 'staged\n')
        run(['add', 'zz'], work)
        write('zz', 'staged, then changed\n')
    elif name == 'tracked-lead-dirty':
        write('tz', 'tz changed in the work tree\n')
    elif name == 'tracked-under-file':
        shutil.rmtree(work / 'q')
        write('q', 'untracked\n')
    elif name == 'tracked-under-symlink':
        shutil.rmtree(work / 'q')
        os.symlink('keep.txt', work / 'q')
    elif name == 'tracked-under-ignored':
        shutil.rmtree(work / 'q')
        exclude(work, 'q')
        write('q', 'ignored\n')
    elif name == 'tracked-became-directory':
        (work / 'r.txt').unlink()
        write('r.txt/u', 'untracked\n')
    elif name == 'removed-became-directory':
        (work / 'lf').unlink()
        write('lf/u', 'untracked\n')
    elif name == 'staged-addition-gone':
        write('zz', 'staged\n')
        run(['add', 'zz'], work)
        (work / 'zz').unlink()
    else:
        raise SystemExit('FAIL transition-obstruction: unknown case ' + name)


def tree(work):
    rows = []
    for p in sorted(work.rglob('*')):
        rel = p.relative_to(work).as_posix()
        if rel == '.git' or rel.startswith('.git/'):
            continue
        if p.is_symlink():
            rows.append((rel, 'link', os.readlink(p)))
        elif p.is_dir():
            rows.append((rel, 'dir', ''))
        elif p.is_file():
            rows.append((rel, 'file', hashlib.sha256(p.read_bytes()).hexdigest()))
        else:
            rows.append((rel, 'other', ''))
    return hashlib.sha256(repr(rows).encode()).hexdigest()[:16]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    parser.add_argument('--den', help="another den binary to hold to Git (default: the tier's build)")
    parser.add_argument('--observe', action='store_true', help='print every cell as read')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    den = a.den or str(root / 'target' / a.tier / 'den')
    git = os.environ['DEN_GIT']
    out = root / 'target' / 'runs' / ('transition-obstruction-' + a.tier)
    # The cells' repositories stay out of target/runs, which CI uploads as
    # evidence (tools/evidence-modes.py). Only the summary is evidence.
    trees = root / 'target' / ('transition-obstruction-' + a.tier)
    for d in (out, trees):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    def run(args, cwd, exe=None, ok=True):
        p = subprocess.run([exe or git, *args], cwd=cwd, capture_output=True, timeout=120)
        if ok:
            assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p

    def state(work):
        refs = run(['for-each-ref', '--format=%(refname) %(objectname)'], work).stdout
        head = run(['symbolic-ref', '-q', 'HEAD'], work, ok=False).stdout + run(['rev-parse', 'HEAD'], work).stdout
        index = (work / '.git/index').read_bytes() if (work / '.git/index').exists() else b''
        pseudo = tuple((n, (work / '.git' / n).read_bytes()) for n in PSEUDO if (work / '.git' / n).exists())
        entries = run(['ls-files', '-s'], work).stdout
        return dict(head=head, refs=refs, index=hashlib.sha256(index).hexdigest(), pseudo=pseudo,
                    entries=entries, tree=tree(work))

    seed = trees / 'seed'
    run(['init', '-q', '-b', 'main', str(seed)], trees)
    for rel, text in (('d0/s0/f0.txt', 'f0\n'), ('d1/s0/f0.txt', 'f1\n'), ('keep.txt', 'keep\n'), ('tz', 'tz\n'),
                      ('q/x', 'q/x\n'), ('r.txt', 'r\n'), ('lf', 'lf\n')):
        (seed / rel).parent.mkdir(parents=True, exist_ok=True)
        (seed / rel).write_text(text)
    run(['add', '-A'], seed)
    run(['commit', '-q', '-m', 'one'], seed)
    run(['switch', '-q', '-c', 'target'], seed)
    (seed / 'd0/s0/f0.txt').write_text('changed by target\n')
    (seed / 'tz').unlink()
    (seed / 'lf').unlink()
    for rel, text in (('tz/new.txt', 'tz is a directory\n'), ('q/x', 'q/x changed by target\n'),
                      ('r.txt', 'r changed by target\n'), ('lf/x.txt', 'lf is a directory\n'), ('zz/new.txt', 'new\n'), ('a/b/c/d.txt', 'deep\n'),
                      ('yy.txt', 'yy target\n')):
        (seed / rel).parent.mkdir(parents=True, exist_ok=True)
        (seed / rel).write_text(text)
    run(['add', '-A'], seed)
    run(['commit', '-q', '-m', 'two'], seed)
    run(['switch', '-q', '-c', 'local', 'main'], seed)
    (seed / 'd1/s0/f0.txt').write_text('local\n')
    run(['commit', '-q', '-am', 'local'], seed)
    gitlinks = trees / 'gitlink-seed'
    run(['init', '-q', '-b', 'main', str(gitlinks)], trees)
    (gitlinks / 'a.txt').write_text('a\n')
    for sub, text in (('sm', 'one\n'), ('same', 'same\n'), ('gone', 'gone\n')):
        run(['init', '-q', '-b', 'main', str(gitlinks / sub)], trees)
        (gitlinks / sub / 'f.txt').write_text(text)
        run(['add', 'f.txt'], gitlinks / sub)
        run(['commit', '-q', '-m', sub], gitlinks / sub)
    run(['add', 'a.txt', 'sm', 'same', 'gone'], gitlinks)
    run(['commit', '-q', '-m', 'one'], gitlinks)
    run(['switch', '-q', '-c', 'target'], gitlinks)
    (gitlinks / 'sm/f.txt').write_text('two\n')
    run(['commit', '-q', '-am', 'two'], gitlinks / 'sm')
    (gitlinks / 'a.txt').write_text('a changed by target\n')
    run(['add', 'a.txt', 'sm'], gitlinks)
    run(['rm', '-q', '--cached', 'gone'], gitlinks)
    run(['commit', '-q', '-m', 'two'], gitlinks)
    run(['switch', '-q', 'main'], gitlinks)
    run(['checkout', '-q', '--detach', 'HEAD~1'], gitlinks / 'sm')

    def cell(case, command):
        branch, argv = COMMANDS[command]
        got = {}
        for tool, exe in (('git', git), ('den', den)):
            work = trees / f'{case}.{command}.{tool}'
            shutil.copytree(gitlinks if case == 'gitlink' else seed, work, symlinks=True)
            run(['switch', '-q', branch], work)
            obstruct(work, case, run)
            before = state(work)
            p = run(argv, work, exe=exe, ok=False)
            got[tool] = (p, before, state(work))
        (gp, gb, ga), (dp, db, da) = got['git'], got['den']
        wrong = []
        if (dp.returncode, dp.stdout, dp.stderr) != (gp.returncode, gp.stdout, gp.stderr):
            wrong.append('exit/output: den %d %r, git %d %r' % (
                dp.returncode, dp.stderr.decode('utf-8', 'replace')[:120],
                gp.returncode, gp.stderr.decode('utf-8', 'replace')[:120]))
        for k in ('head', 'refs', 'pseudo', 'entries', 'tree'):
            if da[k] != ga[k]:
                wrong.append(k + ' differs from git')
        refused = all(gb[k] == ga[k] for k in ('head', 'refs', 'index', 'tree'))
        if refused:
            for k in ('index', 'tree', 'head', 'refs'):
                if db[k] != da[k]:
                    wrong.append('git refused, den changed its ' + k)
        if a.observe:
            print(f'OBSERVE {case} {command} git={gp.returncode} den={dp.returncode} refused={refused} '
                  f'wrong={wrong or "-"}', flush=True)
        return wrong

    failed, summary = 0, []
    for row, (cases, which) in ROWS.items():
        notes, cells = [], 0
        for case in cases:
            for command in COMMANDS:
                if which == 'reset' and command != 'reset' or which == 'nonreset' and command == 'reset':
                    continue
                if which == 'gitlink' and command == 'true':
                    continue
                if (case, command) in NAMED_LIMIT:
                    continue
                cells += 1
                notes += ['%s %s: %s' % (case, command, w) for w in cell(case, command)]
        line = '%s transition-obstruction-%s-%s %d cells%s' % (
            'FAIL' if notes else 'PASS', row, a.tier, cells, (': ' + '; '.join(notes)) if notes else '')
        print(line[:2000], flush=True)
        summary.append(line)
        failed += bool(notes)
    (out / 'summary.txt').write_text('\n'.join(summary) + '\n')
    print('transition-obstruction %s: %d/%d rows pass' % (a.tier, len(ROWS) - failed, len(ROWS)), flush=True)
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
