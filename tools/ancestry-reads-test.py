#!/usr/bin/env python3
"""The merge base a pull and a merge walk for, the commits that walk reads, and
its answer where history is incomplete.

A pull asks two questions before it merges: is HEAD an ancestor of upstream (a
fast-forward), and is upstream an ancestor of HEAD (already up to date). Both
answers follow from the merge base of the two: it is HEAD alone, or upstream
alone. The merge command then needs that base itself. The walk that finds it
reads commits; this counts them.

The fixture is made with Git alone: a linear history of BASE commits with
ascending committer dates, then MOVED more on the remote, as a bare origin; a
clone of it with HEAD reset MOVED commits back and one local commit on top
(the merge shape), and HEAD MOVED behind with no local commit (the
fast-forward shape). probes/ancestry-reads-client prints a walk's bases and the
commits it read (mergetree.bases_counted), or the pull's two answers and its
reads (wiregit.pull_ancestry), or the refusal.

Rows:

  ancestry-reads-merge   the merge shape's bases equal `git merge-base --all`,
                         read in at most 2 * MOVED + 8 commits;
  ancestry-reads-ff      the fast-forward shape's, in at most MOVED + 8;
  ancestry-reads-pull    the pull's two answers equal `git merge-base
                         --is-ancestor` both ways, for the merge, fast-forward
                         and equal-tips shapes, in at most 2 * MOVED + 8,
                         MOVED + 8 and 0 commits.

Incomplete and shallow history. The walk reads every commit from each tip down
to the base, and the base's parents for their dates, and nothing below them:

  ancestry-incomplete-path   one upstream commit (upstream~9) removed from the
                             object store: the walk and the pull's answers
                             refuse not_found, and `den merge` prints what
                             trunk printed, with trunk's exit, byte for byte;
  ancestry-shallow-at-base   a `git clone --depth MOVED+1`, whose boundary is
                             the base, so the base's parent is absent: `den
                             merge` prints what trunk printed (den reads no
                             .git/shallow here, before or after);
  ancestry-incomplete-deep   a commit 300 below the base removed: the bases
                             equal `git merge-base --all` in that repository;
  ancestry-shallow-bases     a `git clone --depth MOVED+40` with HEAD reset
                             MOVED back and one local commit: the bases equal
                             Git's;
  ancestry-shallow-merge     that shallow clone, copied twice: `den merge` and
                             `git merge`, with the same message, identities and
                             dates, both exit 0 with the same tree and parents.

Every id is fixed: fast-import with fixed dates and fixed identities.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

BASE = 400
MOVED = 20
DEEP = 300
SHALLOW = MOVED + 40
MESSAGE = 'Merge upstream into main'
IDENTITY = {
    'GIT_AUTHOR_NAME': 'Den Tester', 'GIT_AUTHOR_EMAIL': 'den@example.invalid',
    'GIT_AUTHOR_DATE': '1800000000 +0000',
    'GIT_COMMITTER_NAME': 'Den Tester', 'GIT_COMMITTER_EMAIL': 'den@example.invalid',
    'GIT_COMMITTER_DATE': '1800000000 +0000',
}
# What trunk 90d0e1e exits with and prints (stdout, stderr) for `den merge --no-edit -m MESSAGE origin/main` where
# its walk meets an absent commit, read with that build on the two repositories below; the change must match.
TRUNK_PATH_MERGE = (128, '', 'fatal: not_found\n')
TRUNK_AT_BASE_MERGE = (128, '', 'fatal: not_found\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    parser.add_argument('--wolf', required=True, help="the pinned wolf (tools/lib-toolchain.sh's $WOLF)")
    parser.add_argument('--den', help='the den to run (default target/<tier>/den)')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target' / 'runs' / ('ancestry-reads-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    den = a.den or str(root / 'target' / a.tier / 'den')
    env = {**os.environ, **IDENTITY, 'GIT_MERGE_AUTOEDIT': 'no'}

    def run(args, cwd, data=None, ok=True):
        p = subprocess.run([str(x) for x in args], cwd=cwd, input=data, capture_output=True, env=env, timeout=300)
        if ok:
            assert p.returncode == 0, (args, p.stdout[-300:], p.stderr[-300:])
        return p

    def text(args, cwd):
        return run(args, cwd).stdout.decode().strip()

    probe = root / 'target' / a.tier / 'ancestry-reads-client'
    probe.parent.mkdir(parents=True, exist_ok=True)
    flags = ['--release'] if a.tier == 'release' else []
    run([a.wolf, 'build', *flags, '--deny-warnings', root / 'probes/ancestry-reads-client/main.lu', '-o', probe], root)

    origin = out / 'origin.git'
    run([git, 'init', '-q', '--bare', '-b', 'main', origin], out)
    stream = []
    for c in range(BASE + MOVED):
        body = 'revision %d\n' % c
        stream.append('commit refs/heads/main\n')
        stream.append('committer Den Tester <den@example.invalid> %d +0000\n' % (1700000000 + c))
        stream.append('data %d\nchange %d\n' % (len('change %d\n' % c), c))
        stream.append('M 100644 inline f%d.txt\ndata %d\n%s\n' % (c % 10, len(body), body))
    run([git, 'fast-import', '--quiet'], origin, ''.join(stream).encode())
    tip = text([git, 'rev-parse', 'main'], origin)

    def clone(name, depth=None):
        work = out / name
        extra = ['--depth', str(depth), origin.as_uri()] if depth else [origin]
        run([git, 'clone', '-q', '--no-local', *extra, work], out)
        for key, value in (('gc.auto', '0'), ('maintenance.auto', 'false')):
            run([git, 'config', key, value], work)
        return work

    def local_commit(work):
        run([git, 'reset', '-q', '--hard', 'origin/main~%d' % MOVED], work)
        (work / 'local.txt').write_text('a local change\n')
        run([git, 'add', 'local.txt'], work)
        run([git, 'commit', '-q', '-m', 'A local change'], work)
        return text([git, 'rev-parse', 'HEAD'], work)

    def without(work, victim):
        """The repository's objects repacked without one commit."""
        names = text([git, 'cat-file', '--batch-all-objects', '--batch-check=%(objectname)'], work).split()
        assert victim in names, victim
        pack = work / '.git/objects/pack'
        old = list(pack.glob('pack-*'))
        run([git, 'pack-objects', '-q', '.git/objects/pack/pack'], work,
            ('\n'.join(n for n in names if n != victim) + '\n').encode())
        for p in old:
            p.unlink()
        for loose in (work / '.git/objects').glob('[0-9a-f][0-9a-f]'):
            shutil.rmtree(loose)
        assert run([git, 'cat-file', '-e', victim], work, ok=False).returncode != 0, victim

    def client(mode, work, left, right):
        p = run([probe, mode, work / '.git', left, right], work, ok=False)
        assert p.returncode == 0 and p.stderr == b'', (mode, left, right, p.stdout[-300:], p.stderr[-300:])
        lines = p.stdout.decode().splitlines()
        refused = [line[len('refused='):] for line in lines if line.startswith('refused=')]
        if refused:
            return dict(refused=refused[0])
        if mode == 'bases':
            reads = [int(line[len('read='):]) for line in lines if line.startswith('read=')]
            return dict(bases=sorted(line[len('base='):] for line in lines if line.startswith('base=')), read=reads[0])
        fields = dict(word.split('=', 1) for word in lines[0].split())
        return dict(forward=fields['forward'], up_to_date=fields['up_to_date'], read=int(fields['read']))

    def git_bases(work, left, right):
        p = run([git, 'merge-base', '--all', left, right], work, ok=False)
        assert p.returncode in (0, 1), (left, right, p.stderr[-300:])
        return sorted(p.stdout.decode().split())

    def ancestor(work, older, newer):
        p = run([git, 'merge-base', '--is-ancestor', older, newer], work, ok=False)
        assert p.returncode in (0, 1), (older, newer, p.stderr[-300:])
        return 'true' if p.returncode == 0 else 'false'

    def den_merge(work):
        p = run([den, 'merge', '--no-edit', '-m', MESSAGE, 'origin/main'], work, ok=False)
        return (p.returncode, p.stdout.decode('utf-8', 'replace'), p.stderr.decode('utf-8', 'replace'))

    rows = []

    def row(name, ok, words):
        rows.append((name, ok, words))

    work = clone('merge')
    head = local_commit(work)
    behind = text([git, 'rev-parse', 'origin/main~%d' % MOVED], work)

    merge = client('bases', work, head, tip)
    want = git_bases(work, head, tip)
    row('reads-merge', merge.get('bases') == want and merge.get('read', 1 << 30) <= 2 * MOVED + 8,
        'bases %s (Git %s), read %s commits (at most %d)' % (merge.get('bases', merge), want, merge.get('read'),
                                                              2 * MOVED + 8))
    ff = client('bases', work, behind, tip)
    want_ff = git_bases(work, behind, tip)
    row('reads-ff', ff.get('bases') == want_ff and ff.get('read', 1 << 30) <= MOVED + 8,
        'bases %s (Git %s), read %s commits (at most %d)' % (ff.get('bases', ff), want_ff, ff.get('read'), MOVED + 8))
    answers = []
    good = True
    for current, bound in ((head, 2 * MOVED + 8), (behind, MOVED + 8), (tip, 0)):
        got = client('pull', work, current, tip)
        expected = dict(forward=ancestor(work, current, tip), up_to_date=ancestor(work, tip, current))
        good = good and 'refused' not in got and got['forward'] == expected['forward'] \
            and got['up_to_date'] == expected['up_to_date'] and got['read'] <= bound
        answers.append('%s/%s read %s (Git %s/%s, at most %d)' % (
            got.get('forward'), got.get('up_to_date'), got.get('read', got.get('refused')),
            expected['forward'], expected['up_to_date'], bound))
    row('reads-pull', good, 'forward/up to date for merge, fast-forward, equal tips: ' + '; '.join(answers))

    # An absent commit on the walked path: the same refusal as trunk.
    path = out / 'incomplete-path'
    shutil.copytree(work, path, symlinks=True)
    without(path, text([git, 'rev-parse', 'origin/main~9'], path))
    refused = (client('bases', path, head, tip), client('pull', path, head, tip))
    merged = den_merge(path)
    row('incomplete-path',
        refused[0].get('refused') == 'not_found' and refused[1].get('refused') == 'not_found'
        and merged == TRUNK_PATH_MERGE,
        'walk %s, pull %s; den merge exit %d stderr %r (trunk: %r)' % (
            refused[0], refused[1], merged[0], merged[2], TRUNK_PATH_MERGE))

    at_base = clone('shallow-at-base', MOVED + 1)
    local_commit(at_base)
    merged = den_merge(at_base)
    row('shallow-at-base', merged == TRUNK_AT_BASE_MERGE,
        'boundary at the base: den merge exit %d stderr %r (trunk: %r)' % (merged[0], merged[2], TRUNK_AT_BASE_MERGE))

    # An absent commit deeper than the base's parents: Git's answer.
    deep = out / 'incomplete-deep'
    shutil.copytree(work, deep, symlinks=True)
    without(deep, text([git, 'rev-parse', 'origin/main~%d' % (MOVED + DEEP)], deep))
    found = client('bases', deep, head, tip)
    want_deep = git_bases(deep, head, tip)
    row('incomplete-deep', found.get('bases') == want_deep and want_deep == want,
        'a commit %d below the base absent: bases %s (Git %s)' % (DEEP, found.get('bases', found), want_deep))

    shallow = clone('shallow', SHALLOW)
    shallow_head = local_commit(shallow)
    assert (shallow / '.git/shallow').exists()
    found = client('bases', shallow, shallow_head, tip)
    want_shallow = git_bases(shallow, shallow_head, tip)
    row('shallow-bases', found.get('bases') == want_shallow and len(want_shallow) == 1,
        'depth %d: bases %s (Git %s)' % (SHALLOW, found.get('bases', found), want_shallow))

    by_den, by_git = out / 'shallow-den', out / 'shallow-git'
    shutil.copytree(shallow, by_den, symlinks=True)
    shutil.copytree(shallow, by_git, symlinks=True)
    merged = den_merge(by_den)
    gitted = run([git, 'merge', '--no-edit', '-m', MESSAGE, 'origin/main'], by_git, ok=False)

    def result(work):
        tree = run([git, 'rev-parse', 'HEAD^{tree}'], work, ok=False).stdout.decode().strip()
        parents = run([git, 'rev-list', '--parents', '-n', '1', 'HEAD'], work, ok=False).stdout.decode().split()[1:]
        return tree, parents

    row('shallow-merge', merged[0] == 0 and gitted.returncode == 0 and result(by_den) == result(by_git),
        'den merge exit %d %r, git merge exit %d; tree and parents den %s, Git %s' % (
            merged[0], merged[2][-200:], gitted.returncode, result(by_den), result(by_git)))

    failed = 0
    for name, ok, words in rows:
        print(('PASS' if ok else 'FAIL'), 'ancestry-%s-%s' % (name, a.tier), words, flush=True)
        failed += not ok
    print('ancestry-reads %s: %d/%d rows pass' % (a.tier, len(rows) - failed, len(rows)), flush=True)
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
