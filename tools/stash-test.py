"""vc12 stash and notes differential contract.

Git 2.56.0 git-stash(1)/git-notes(1) documentation and the pinned executable
only; no implementation source. Every fixture is built by the oracle; each
case is run by both tools from byte-identical copies, in loose and packed
storage, and every intermediate process is compared: stdout, stderr, status
and the complete .git and worktree byte/mode state (index stat words only
through the inherited six-word per-file proof, loose objects by raw bytes).
A named refusal must leave every byte unchanged and is never parity.
"""
import argparse, collections, hashlib, json, os, pathlib, runpy, shutil, subprocess

ap = argparse.ArgumentParser()
ap.add_argument('--tier', default='native')
ap.add_argument('--filter', default='')
ap.add_argument('--measure', action='store_true')
ap.add_argument('--modes', default='loose,packed')
a = ap.parse_args()
R = pathlib.Path(__file__).resolve().parent.parent
G = os.environ['DEN_GIT']
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest() == \
    'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60', 'oracle digest'
D = str(R / f'target/{a.tier}/den')
O = runpy.run_path(str(R / 'tools/oracle.py'))
pack_fixture = runpy.run_path(str(R / 'tools/packed-fixture.py'))['pack_fixture']
root = R / f'target/stash-{a.tier}'
shutil.rmtree(root, ignore_errors=True)
root.mkdir(parents=True)


def git(repo, *args, data=None):
    p = subprocess.run([G, *args], cwd=repo, input=data, capture_output=True)
    assert p.returncode == 0, (args, p.stdout, p.stderr)
    return p.stdout.decode().strip()


def write(repo, path, data):
    p = repo / path
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.is_symlink(): p.unlink()
    p.write_bytes(data if isinstance(data, bytes) else data.encode())


def oid_of(data):
    return hashlib.sha1(b'blob %d\0' % len(data) + data).hexdigest()


def fans_out(hexes):
    """The oracle's measured rule, used here only to place fixture edges."""
    groups = collections.Counter(h[0] for h in hexes)
    return len(groups) == 16 and min(groups.values()) >= 2


# ---- fixtures, all built by the pinned oracle ----
def linear(repo):
    repo.mkdir(); git(repo, 'init', '-q')
    write(repo, 'a.txt', 'alpha\n'); write(repo, 'b.txt', 'beta\n'); write(repo, 'dir/c.txt', 'gamma\n')
    write(repo, 'lines.txt', 'one\ntwo\nthree\nfour\nfive\nsix\nseven\n')
    git(repo, 'add', '.'); git(repo, 'commit', '-q', '-m', 'first subject\n\nbody line')
    git(repo, 'tag', 'first')
    write(repo, 'b.txt', 'beta two\n'); git(repo, 'commit', '-qam', 'second subject')
    return {}


def multiline(repo):
    repo.mkdir(); git(repo, 'init', '-q')
    write(repo, 'a.txt', 'alpha\n'); git(repo, 'add', '.')
    git(repo, 'commit', '-q', '-m', 'line one\nline two\n\nbody')
    return {}


def unborn(repo):
    repo.mkdir(); git(repo, 'init', '-q'); write(repo, 'a.txt', 'x\n'); git(repo, 'add', 'a.txt')
    return {}


def stashed(repo):
    linear(repo)
    write(repo, 'a.txt', 'v0\n'); git(repo, 'stash', 'push', '-q', '-m', 'm0')
    write(repo, 'a.txt', 'v1\n'); write(repo, 'new.txt', 'added\n'); git(repo, 'add', 'new.txt')
    git(repo, 'stash', 'push', '-q')
    write(repo, 'lines.txt', 'one\ntwo\nthree\nfour\nfive\nsix\nSEVEN\n'); git(repo, 'stash', 'push', '-q', '-m', 'm2')
    return {}


def noted(repo):
    linear(repo)
    git(repo, 'notes', 'add', '-m', 'oracle note on head', 'HEAD')
    git(repo, 'notes', 'add', '-m', 'oracle note on first', 'first')
    git(repo, 'notes', 'add', '-m', 'blob note', 'HEAD:a.txt')
    return {}


def fanned(repo):
    linear(repo)
    ids, hexes, extra, i = {}, [], 10, 0
    while extra > 0:
        data = f'fan {i}\n'.encode()
        ids[f'fan{i}'] = git(repo, 'hash-object', '-w', '--stdin', data=data)
        git(repo, 'notes', 'add', '-m', f'fan note {i}', ids[f'fan{i}'])
        hexes.append(ids[f'fan{i}'])
        if fans_out(hexes): extra -= 1
        i += 1
    tree = git(repo, 'ls-tree', 'refs/notes/commits')
    assert all(line.split()[1] == 'tree' for line in tree.splitlines()), 'fixture is not fanned'
    return ids


def edge(repo, full):
    """Notes up to one short of the measured fan-out edge (or exactly at it)."""
    linear(repo)
    ids, hexes, i = {}, [], 0
    while True:
        data = f'edge {i}\n'.encode(); h = oid_of(data); hexes.append(h)
        ids[f'edge{i}'] = git(repo, 'hash-object', '-w', '--stdin', data=data)
        assert ids[f'edge{i}'] == h
        if fans_out(hexes): break
        i += 1
    ids['crossing'] = ids[f'edge{i}']
    ids['previous'] = ids[f'edge{i - 1}']
    for n in range(i + (1 if full else 0)):
        git(repo, 'notes', 'add', '-m', f'edge note {n}', ids[f'edge{n}'])
    return ids


FIXTURES = {
    'linear': linear, 'multiline': multiline, 'unborn': unborn, 'stashed': stashed,
    'noted': noted, 'fanned': fanned, 'edge': lambda r: edge(r, False), 'edge-full': lambda r: edge(r, True),
}

CASES = []


def case(name, fixture, setup, steps, refusal=None):
    CASES.append(dict(name=name, fixture=fixture, setup=setup, steps=steps, refusal=refusal))


MIXED = [('write', 'a.txt', 'alpha changed\n'), ('write', 'b.txt', 'beta staged\n'), ('add', 'b.txt'),
         ('write', 'b.txt', 'beta staged then worktree\n'), ('write', 'new.txt', 'added\n'), ('add', 'new.txt'),
         ('rm', 'dir/c.txt'), ('write', 'untracked', 'u\n')]
DIRTY_A = [('write', 'a.txt', 'alpha changed\n')]

# Snapshot construction and publication.
case('push-nothing', 'linear', [], [['stash']])
case('push-nothing-untracked', 'linear', [('write', 'u.txt', 'u\n')], [['stash'], ['stash', 'list']])
case('push-unstaged', 'linear', DIRTY_A, [['stash'], ['stash', 'list'], ['stash', 'show'], ['stash', 'show', '-p'], ['status', '--porcelain']])
case('push-mixed', 'linear', MIXED, [['stash'], ['stash', 'show'], ['stash', 'show', '-p'], ['stash', 'list'],
                                     ['cat-file', '-p', 'stash@{0}'], ['cat-file', '-p', 'stash@{0}^2'], ['status', '--porcelain']])
case('push-staged-only', 'linear', [('write', 'a.txt', 'staged\n'), ('add', 'a.txt')], [['stash'], ['stash', 'show'], ['stash', 'apply'], ['status', '--porcelain']])
case('push-quiet', 'linear', DIRTY_A, [['stash', '-q'], ['stash', 'list']])
case('push-quiet-long', 'linear', DIRTY_A, [['stash', 'push', '--quiet', '--message', 'quiet long']])
for n, args in enumerate([['stash', 'push', '-m', 'my message'], ['stash', '-m', 'bare form'],
                          ['stash', 'push', '--message=long form'], ['stash', 'save', 'saved', 'words'],
                          ['stash', 'push', '-m', ''], ['stash', 'push', '-m', 'two\nlines'],
                          ['stash', 'push', '-m', 'trail\n'], ['stash', 'push', '-mjoined'],
                          ['stash', 'save'], ['stash', 'save', '-q', 'quiet save'], ['stash', 'push', '--', ]]):
    case(f'push-message-{n}', 'linear', DIRTY_A, [args, ['stash', 'list'], ['cat-file', '-p', 'stash']])
case('push-detached', 'linear', [('git', 'checkout', '-q', '--detach'), *DIRTY_A], [['stash'], ['stash', 'list'], ['cat-file', '-p', 'stash@{0}']])
case('push-multiline-subject', 'multiline', DIRTY_A, [['stash'], ['stash', 'list']])
case('push-keep-index', 'linear', [('write', 'a.txt', 'staged\n'), ('add', 'a.txt'), ('write', 'b.txt', 'worktree only\n')],
     [['stash', 'push', '--keep-index'], ['status', '--porcelain'], ['stash', 'show', '-p']])
case('push-keep-index-short', 'linear', [('write', 'a.txt', 'staged\n'), ('add', 'a.txt'), ('write', 'b.txt', 'worktree only\n')],
     [['stash', '-k', '-q'], ['stash', 'pop']])
case('push-unborn', 'unborn', [], [['stash']])
case('push-stash-lock', 'linear', [*DIRTY_A, ('lock', '.git/refs/stash.lock')], [['stash']])
case('push-index-lock', 'linear', [*DIRTY_A, ('lock', '.git/index.lock')], [['stash']])
case('push-exec', 'linear', [('chmod', 'a.txt', 0o755)], [['stash'], ['stash', 'show', '-p'], ['stash', 'apply'], ['status', '--porcelain']])
case('push-twice', 'linear', DIRTY_A, [['stash'], ['@write', 'b.txt', 'beta third\n'], ['stash', 'push', '-m', 'second'],
                                       ['stash', 'list'], ['stash', 'show', '1'], ['stash', 'show', 'stash@{1}'], ['stash', 'show', '-p', 'stash@{0}']])
case('push-subdirectory', 'linear', [('write', 'dir/c.txt', 'gamma changed\n'), ('write', 'dir/d.txt', 'new in dir\n'), ('add', 'dir/d.txt')],
     [['stash'], ['stash', 'show'], ['stash', 'pop'], ['status', '--porcelain']])
case('push-orig-head-present', 'linear', [('write', '.git/ORIG_HEAD', '0' * 40 + '\n'), *DIRTY_A], [['stash']])

# Listing and display over oracle-made entries.
case('list-oracle', 'stashed', [], [['stash', 'list'], ['stash', 'show'], ['stash', 'show', '1'], ['stash', 'show', '-p', '2'],
                                    ['stash', 'show', '--stat', '-p', 'stash@{1}'], ['stash', 'show', '--name-only', 'stash@{2}']])
case('list-empty', 'linear', [], [['stash', 'list'], ['stash', 'show'], ['stash', 'apply'], ['stash', 'pop'], ['stash', 'drop'], ['stash', 'clear']])

# Recovery, separate from construction.
case('apply-clean', 'linear', DIRTY_A, [['stash'], ['stash', 'apply'], ['status', '--porcelain'], ['stash', 'list']])
case('apply-quiet', 'linear', DIRTY_A, [['stash', '-q'], ['stash', 'apply', '-q'], ['status', '--porcelain']])
case('apply-mixed', 'linear', MIXED, [['stash'], ['stash', 'apply'], ['status', '--porcelain']])
case('pop-clean', 'linear', DIRTY_A, [['stash'], ['stash', 'pop'], ['stash', 'list'], ['status', '--porcelain']])
case('pop-mixed', 'linear', MIXED, [['stash'], ['stash', 'pop'], ['stash', 'list'], ['status', '--porcelain']])
case('pop-quiet', 'linear', DIRTY_A, [['stash', '-q'], ['stash', 'pop', '-q']])
case('apply-oracle-entries', 'stashed', [], [['stash', 'apply', 'stash@{2}'], ['status', '--porcelain'], ['@reset'], ['stash', 'apply', '1'],
                                             ['status', '--porcelain']])
case('pop-oracle-entries', 'stashed', [], [['stash', 'pop'], ['stash', 'list'], ['@reset'], ['stash', 'pop', 'stash@{1}'], ['stash', 'list']])
case('apply-oid', 'stashed', [], [['stash', 'apply', '@stash1'], ['status', '--porcelain']])
case('apply-moved-head', 'linear', DIRTY_A, [['stash', '-q'], ['@write', 'b.txt', 'beta moved\n'], ['commit', '-qam', 'move b'],
                                            ['stash', 'apply'], ['status', '--porcelain']])
case('apply-content-merge', 'linear', [('write', 'lines.txt', 'ONE\ntwo\nthree\nfour\nfive\nsix\nseven\n')],
     [['stash', '-q'], ['@write', 'lines.txt', 'one\ntwo\nthree\nfour\nfive\nsix\nSEVEN\n'], ['commit', '-qam', 'edit seven'], ['stash', 'pop'], ['stash', 'list']])
# Dirty bytes are written once in setup, so both copies carry the same stale
# stat words; a tool-side rewrite after its own step is unprovable (vc08).
case('apply-dirty-overlap', 'stashed', [('write', 'lines.txt', 'dirty lines\n')], [['stash', 'apply'], ['stash', 'list']])
case('apply-dirty-other', 'stashed', [('write', 'b.txt', 'dirty b\n')], [['stash', 'apply'], ['status', '--porcelain']])
case('pop-dirty-overlap', 'stashed', [('write', 'lines.txt', 'dirty lines\n')], [['stash', 'pop'], ['stash', 'list']])
case('pop-dirty-other', 'stashed', [('write', 'b.txt', 'dirty b\n')], [['stash', 'pop'], ['stash', 'list'], ['status', '--porcelain']])
case('apply-staged-other', 'linear', DIRTY_A, [['stash', '-q'], ['@write', 'b.txt', 'staged b\n'], ['add', 'b.txt'],
                                              ['stash', 'apply'], ['status', '--porcelain']])
case('apply-staged-same-content', 'linear', DIRTY_A, [['stash', '-q'], ['@write', 'a.txt', 'alpha changed\n'], ['add', 'a.txt'],
                                                     ['stash', 'apply'], ['status', '--porcelain']])
case('apply-untracked-collision', 'linear', [('write', 'n.txt', 'new\n'), ('add', 'n.txt')],
     [['stash', '-q'], ['@write', 'n.txt', 'untracked collision\n'], ['stash', 'apply']])
case('apply-not-stash', 'linear', [], [['stash', 'apply', 'HEAD']])
case('apply-out-of-range', 'stashed', [], [['stash', 'apply', 'stash@{7}'], ['stash', 'show', 'stash@{7}'], ['stash', 'drop', 'stash@{7}'],
                                           ['stash', 'pop', '9']])

# Durable ref and reflog recovery state.
case('drop-middle', 'stashed', [], [['stash', 'drop', 'stash@{1}'], ['stash', 'list'], ['stash', 'drop', '1'], ['stash', 'list'],
                                    ['stash', 'drop'], ['stash', 'list'], ['stash', 'drop']])
case('drop-top', 'stashed', [], [['stash', 'drop', 'stash@{0}'], ['stash', 'list'], ['cat-file', '-p', 'stash']])
case('drop-quiet', 'stashed', [], [['stash', 'drop', '-q'], ['stash', 'drop', '--quiet', '1'], ['stash', 'list']])
case('clear', 'stashed', [], [['stash', 'clear'], ['stash', 'list'], ['stash', 'clear']])
case('push-after-drop', 'stashed', DIRTY_A, [['stash', 'drop', '2'], ['stash'], ['stash', 'list']])

case('apply-index-lock', 'stashed', [('lock', '.git/index.lock')], [['stash', 'apply'], ['stash', 'list']])
case('pop-index-lock', 'stashed', [('lock', '.git/index.lock')], [['stash', 'pop'], ['stash', 'list']])
case('drop-reflog-lock', 'stashed', [('lock', '.git/logs/refs/stash.lock')], [['stash', 'drop'], ['stash', 'list']])
case('drop-ref-lock', 'stashed', [('lock', '.git/refs/stash.lock')], [['stash', 'drop', '1'], ['stash', 'drop'], ['stash', 'list']])
case('clear-ref-lock', 'stashed', [('lock', '.git/refs/stash.lock')], [['stash', 'clear'], ['stash', 'list']])
case('notes-remove-lock', 'noted', [('lock', '.git/refs/notes/commits.lock')], [['notes', 'remove'], ['notes', 'list']])

# Named stash boundaries (each a refusal before any write).
for n, (args, feature) in enumerate([
        (['stash', '-u'], 'stash untracked snapshot (-u/-a)'),
        (['stash', 'push', '--include-untracked'], 'stash untracked snapshot (-u/-a)'),
        (['stash', 'push', '-a'], 'stash untracked snapshot (-u/-a)'),
        (['stash', 'push', '-p'], 'stash interactive patch selection'),
        (['stash', 'push', '--staged'], 'stash staged-only snapshot'),
        (['stash', 'push', '--', 'a.txt'], 'stash path-limited push'),
        (['stash', 'push', 'a.txt'], 'stash path-limited push'),
        (['stash', 'push', '--pathspec-from-file=list'], 'stash path-limited push'),
        (['stash', 'branch', 'topic'], 'stash branch'),
        (['stash', 'create'], 'stash create'),
        (['stash', 'store', 'HEAD'], 'stash store'),
        (['stash', 'export', '--print'], 'stash export'),
        (['stash', 'import', 'HEAD'], 'stash import'),
        (['stash', 'list', '--oneline'], 'stash list log options'),
        (['stash', 'show', '-u'], 'stash show untracked'),
        (['stash', 'apply', '--index'], 'stash apply --index'),
        (['stash', 'pop', '--index'], 'stash apply --index')]):
    fixture = 'stashed' if args[1] in ('list', 'show', 'apply', 'pop', 'branch') else 'linear'
    case(f'scope-stash-{n}', fixture, DIRTY_A if fixture == 'linear' else [], [args], refusal=(0, feature))
case('scope-apply-conflict', 'linear', DIRTY_A, [['stash', '-q'], ['@write', 'a.txt', 'conflict a\n'], ['commit', '-qam', 'conflict'],
                                               ['stash', 'apply']], refusal=(2, 'stash apply conflict'))
case('scope-apply-staged-overlap', 'linear', DIRTY_A, [['stash', '-q'], ['@write', 'a.txt', 'staged a\n'], ['add', 'a.txt'],
                                                     ['stash', 'apply']], refusal=(2, 'stash apply conflict'))
case('scope-untracked-entry', 'linear', [('write', 'u.txt', 'u\n'), ('git', 'stash', '-q', '-u')],
     [['stash', 'apply']], refusal=(0, 'stash untracked snapshot apply'))
case('scope-stash-config', 'linear', [('git', 'config', 'stash.showPatch', 'true'), *DIRTY_A], [['stash', '-q'], ['stash', 'show']],
     refusal=(1, 'stash configuration stash.showpatch'))
case('scope-unknown-subcommand', 'linear', DIRTY_A, [['stash', 'nosuch']])

# Notes over refs/notes/commits.
case('notes-add', 'linear', [], [['notes', 'list'], ['notes'], ['notes', 'show'], ['notes', 'add', '-m', 'first note  ', 'HEAD'],
                                 ['notes', 'list'], ['notes', 'list', 'HEAD'], ['notes', 'show'], ['notes'], ['notes', 'get-ref']])
case('notes-add-again', 'linear', [], [['notes', 'add', '-m', 'one'], ['notes', 'add', '-m', 'two'],
                                       ['notes', 'add', '-f', '-m', 'second', '-m', 'third\n\n\n'], ['notes', 'show']])
case('notes-message-forms', 'linear', [], [['notes', 'add', '--message=long form', 'first'], ['notes', 'add', '-mjoined'],
                                           ['notes', 'show', 'first'], ['notes', 'show']])
case('notes-empty', 'linear', [], [['notes', 'add', '-m', ''], ['notes', 'add', '-m', '  \n  '], ['notes', 'list'],
                                   ['notes', 'add', '-m', 'x'], ['notes', 'add', '-f', '-m', ''], ['notes', 'list']])
case('notes-allow-empty', 'linear', [], [['notes', 'add', '--allow-empty', '-m', ''], ['notes', 'show'], ['notes', 'list'],
                                         ['notes', 'add', '--allow-empty', '-m', '']])
case('notes-objects', 'linear', [], [['notes', 'add', '-m', 'on a blob', 'HEAD:a.txt'], ['notes', 'add', '-m', 'on a tree', 'HEAD^{tree}'],
                                     ['notes', 'add', '-m', 'on a tag', 'first'], ['notes', 'list'], ['notes', 'show', 'HEAD:a.txt']])
case('notes-remove', 'noted', [], [['notes', 'remove', 'HEAD'], ['notes', 'remove', 'HEAD'], ['notes', 'remove', '--ignore-missing', 'HEAD'],
                                   ['notes', 'list'], ['notes', 'remove', 'first', 'HEAD:a.txt'], ['notes', 'list']])
case('notes-remove-mixed', 'noted', [], [['notes', 'remove', 'HEAD', 'HEAD~1', 'first'], ['notes', 'list']])
case('notes-remove-mixed-ignore', 'noted', [], [['notes', 'remove', '--ignore-missing', 'HEAD~1', 'HEAD'], ['notes', 'list']])
case('notes-remove-noref', 'linear', [], [['notes', 'remove', 'HEAD'], ['notes', 'remove', '--ignore-missing']])
case('notes-errors', 'linear', [], [['notes', 'show', 'HEAD'], ['notes', 'list', 'HEAD'], ['notes', 'add', '-m', 'x', 'nosuch'],
                                    ['notes', 'show', 'nosuch'], ['notes', 'remove', 'nosuch']])
case('notes-unborn', 'unborn', [], [['notes', 'add', '-m', 'x'], ['notes', 'list'], ['notes', 'show']])
case('notes-oracle-read', 'noted', [], [['notes', 'list'], ['notes', 'show'], ['notes', 'show', 'first'], ['notes', 'list', 'HEAD:a.txt'],
                                        ['notes', 'add', '-m', 'over oracle', 'HEAD~1'], ['notes', 'add', '-f', '-m', 'replaced', 'HEAD'], ['notes', 'list']])
case('notes-fanned-read', 'fanned', [], [['notes', 'list'], ['notes', 'show', '@fan0'], ['notes', 'list', '@fan7']])
case('notes-fanned-write', 'fanned', [], [['notes', 'add', '-m', 'more', 'HEAD'], ['notes', 'remove', '@fan3'], ['notes', 'list']])
case('notes-fanout-cross', 'edge', [], [['notes', 'add', '-m', 'crossing', '@crossing'], ['notes', 'list'], ['notes', 'show', '@crossing']])
case('notes-fanout-uncross', 'edge-full', [], [['notes', 'remove', '@previous'], ['notes', 'list'], ['notes', 'add', '-m', 'again', '@previous']])
case('notes-lock', 'linear', [('lock', '.git/refs/notes/commits.lock')], [['notes', 'add', '-m', 'locked']])
for n, (args, feature) in enumerate([
        (['notes', 'add'], 'notes editor'), (['notes', 'add', '-F', 'msg'], 'notes add -F'),
        (['notes', 'add', '-C', 'HEAD'], 'notes add -C'), (['notes', 'add', '-e', '-m', 'x'], 'notes add -e'),
        (['notes', 'append', '-m', 'x'], 'notes append'), (['notes', 'copy', 'HEAD', 'first'], 'notes copy'),
        (['notes', 'edit'], 'notes edit'), (['notes', 'merge', 'other'], 'notes merge'), (['notes', 'prune'], 'notes prune'),
        (['notes', '--ref=other', 'list'], 'notes --ref'), (['notes', 'remove', '--stdin'], 'notes remove --stdin'),
        (['log', '--notes', '--pretty=full'], 'history notes in full format'),
        (['log', '--oneline', '--notes'], 'history notes in oneline format'),
        (['log', '-p', '--stat'], 'history notes with patch and stat'),
        (['log', '--notes=other'], 'log option --notes=other')]):
    case(f'scope-notes-{n}', 'noted', [], [args], refusal=(0, feature))
# Notes in history: the default ref in the default format (pretty-options --notes).
case('notes-history', 'noted', [], [['log'], ['log', '-1'], ['log', '-p'], ['log', '--stat'], ['show'], ['show', '--stat'], ['show', '-s'],
                                    ['log', '--no-notes'], ['log', '--pretty=medium'], ['log', '--format=medium'], ['log', '--pretty=full'],
                                    ['log', '--oneline'], ['log', '--notes'], ['show', 'first'], ['log', '--notes', '-1'], ['log', '--no-notes', '--notes', '-1']])
case('notes-history-written', 'linear', [], [['notes', 'add', '-m', 'multi\n\nline note'], ['log'], ['show', '-s'],
                                             ['notes', 'remove'], ['log', '-1']])
case('notes-history-other-ref', 'noted', [('git', 'notes', '--ref=other', 'add', '-m', 'other ref', 'HEAD~1')], [['log'], ['log', '--oneline']])
case('scope-notes-history-empty', 'linear', [('git', 'notes', 'add', '--allow-empty', '-m', '')], [['log', '-1']],
     refusal=(0, 'history notes without a final newline'))
case('scope-notes-history-display-ref', 'noted', [('git', 'config', 'notes.displayRef', 'refs/notes/other')], [['log', '-1']],
     refusal=(0, 'history notes notes.displayref'))
case('scope-notes-config', 'linear', [('git', 'config', 'core.notesRef', 'refs/notes/other')], [['notes', 'list']],
     refusal=(0, 'notes core.notesRef'))

# vc09's original corpus fixtures, both storage modes.
CORPUS = [('two', 'a.txt'), ('linear', 'a.txt'), ('merge', 'a.txt'), ('rename', 'renamed.txt'), ('binary', 'raw.bin'),
          ('symlink', 'a.txt'), ('thousand', 'file-0001'), ('m2-amend', 'a.txt'), ('m2-index-v4', 'a.txt'), ('m2-edited-rename', 'a.txt')]
for name, path in CORPUS:
    case(f'corpus-stash-{name}', 'corpus:' + name, [('write', path, b'corpus change\n')],
         [['stash'], ['stash', 'list'], ['stash', 'show'], ['stash', 'show', '-p'], ['stash', 'pop'], ['stash', 'list']])
    case(f'corpus-notes-{name}', 'corpus:' + name, [],
         [['notes', 'add', '-m', f'corpus note {name}'], ['notes', 'list'], ['notes', 'show'], ['notes', 'remove'], ['notes', 'list']])


def apply_action(repo, action):
    kind = action[0]
    if kind == 'write': write(repo, action[1], action[2])
    elif kind == 'rm': (repo / action[1]).unlink()
    elif kind == 'add': git(repo, 'add', action[1])
    elif kind == 'chmod': os.chmod(repo / action[1], action[2])
    elif kind == 'lock': write(repo, action[1], b'foreign lock\n')
    elif kind == 'git': git(repo, *action[1:])
    else: raise ValueError(action)


corpus_root = root / 'corpus-source'
corpus_built = False
built = {}


def fixture_for(name, mode):
    global corpus_built
    key = (name, mode)
    if key in built: return built[key]
    path = root / 'fixtures' / f'{name.replace(":", "-")}-{mode}'
    path.parent.mkdir(parents=True, exist_ok=True)
    if name.startswith('corpus:'):
        if not corpus_built:
            runpy.run_path(str(R / 'tools/corpus.py'))['build'](corpus_root); corpus_built = True
        shutil.copytree(corpus_root / name[7:], path, symlinks=True); ids = {}
    else:
        ids = FIXTURES[name](path)
    if (path / '.git/refs/stash').exists() or name == 'stashed':
        for n, line in enumerate(reversed((path / '.git/logs/refs/stash').read_text().splitlines())):
            ids[f'stash{n}'] = line.split()[1]
    if mode == 'packed':
        pack_fixture(G, path)
        git(path, 'pack-refs', '--all')
    built[key] = (path, ids)
    return built[key]


rows, failures = [], []
for mode in a.modes.split(','):
    for spec in CASES:
        if a.filter not in spec['name']: continue
        fixture, ids = fixture_for(spec['fixture'], mode)
        start = root / 'cases' / f'{spec["name"]}-{mode}'
        shutil.copytree(fixture, start / 'base', symlinks=True)
        for action in spec['setup']: apply_action(start / 'base', action)
        steps = [[ids[x[1:]] if x.startswith('@') and x[1:] in ids else x for x in step] for step in spec['steps']]

        def execute(exe):
            # One path for both tools, so absolute-path diagnostics compare.
            repo = start / 'repo'
            if repo.exists(): shutil.rmtree(repo)
            shutil.copytree(start / 'base', repo, symlinks=True)
            out, before = [], []
            for step in steps:
                if step[0] == '@write': write(repo, step[1], step[2]); continue
                if step[0] == '@reset':
                    subprocess.run([G, 'reset', '-q', '--hard'], cwd=repo, check=True, capture_output=True)
                    subprocess.run([G, 'clean', '-q', '-f'], cwd=repo, check=True, capture_output=True)
                    continue
                before.append((O['snapshot'](repo), O['worktree_snapshot'](repo)))
                out.append(O['capture']([exe, *step], repo, index_proof=True))
            return out, before

        expected, _ = execute(G)
        row = dict(name=spec['name'], mode=mode, fixture=spec['fixture'], setup=[list(map(str, x)) for x in spec['setup']],
                   steps=steps, git=expected)
        if a.measure:
            print('\nCASE', spec['name'], mode)
            for step, result in zip([s for s in steps if not s[0].startswith('@')], expected):
                print(step, result['status'], bytes.fromhex(result['stdout']), bytes.fromhex(result['stderr']))
            rows.append(row); continue
        actual, before = execute(D)
        row['den'] = actual
        checks = []
        for i, (e, d) in enumerate(zip(expected, actual)):
            if spec['refusal'] and i == spec['refusal'][0]:
                feature = spec['refusal'][1]
                good = (d['status'] == 2 and d['stdout'] == '' and
                        bytes.fromhex(d['stderr']) == f'den: not yet implemented: {feature}\n'.encode() and
                        d['repository'] == before[i][0] and d['worktree'] == before[i][1])
                row['reason'] = feature
            else:
                good = O['equivalent'](e, d, 'index-stat-proven')
            checks.append(good)
            if not good:
                ran = [s for s in steps if not s[0].startswith('@')]
                print('MISMATCH', spec['name'], mode, 'step', i, ran[i], flush=True)
                for key in ('status', 'stdout', 'stderr'):
                    if e[key] != d[key]:
                        print('   ', key, 'git', repr(bytes.fromhex(e[key]) if key != 'status' else e[key])[:400])
                        print('   ', key, 'den', repr(bytes.fromhex(d[key]) if key != 'status' else d[key])[:400])
                for part in ('repository', 'worktree'):
                    for k in sorted(set(e[part]) | set(d[part])):
                        if e[part].get(k) != d[part].get(k):
                            print('   ', part, k, 'git', str(e[part].get(k))[:160], 'den', str(d[part].get(k))[:160])
        row['processes'] = len(expected)
        row['verified'] = len(expected) == len(actual) and all(checks)
        row['disposition'] = 'named-not-yet' if spec['refusal'] else 'parity'
        if not row['verified']: failures.append([spec['name'], mode])
        print(spec['name'], mode, ('NAMED' if spec['refusal'] else 'PASS') if row['verified'] else 'FAIL', flush=True)
        rows.append(row)
assert rows, 'empty selection'
out = R / f'target/stash-{"measure" if a.measure else a.tier}.json'
summary = dict(rows=rows, failures=failures, zero_skips=True)
if not a.measure:
    parity = [r for r in rows if r['disposition'] == 'parity']
    named = [r for r in rows if r['disposition'] != 'parity']
    summary['counts'] = {
        mode: dict(
            parity_cases=sum(1 for r in parity if r['mode'] == mode and r['verified']),
            parity_total=sum(1 for r in parity if r['mode'] == mode),
            exact_processes=sum(r['processes'] for r in parity if r['mode'] == mode and r['verified']),
            named=sum(1 for r in named if r['mode'] == mode and r['verified']),
            named_total=sum(1 for r in named if r['mode'] == mode),
            corpus_cases=sum(1 for r in parity if r['mode'] == mode and r['fixture'].startswith('corpus:') and r['verified']))
        for mode in a.modes.split(',')}
    print(json.dumps(summary['counts'], sort_keys=True))
    print(f'stash/notes: {sum(r["verified"] for r in parity)}/{len(parity)} exact cases; {len(named)} named; {len(failures)} failures')
out.write_text(json.dumps(summary, indent=1) + '\n')
raise SystemExit(bool(failures) and not a.measure)
