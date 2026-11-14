"""den#80: directories and paths the walk may not open, as the pinned Git
takes them.

Each row builds the same small repository for each tool, takes a permission
away from one directory, and runs one command as an unprivileged user (the
container's root drops to uid 65534 for both tools; an ordinary user runs as
itself). A row compares den's status, stdout and stderr with Git's, byte for
byte, and the index and HEAD tree the command leaves, except the named
refusals in REFUSED, where den must refuse by that name.

  --measure  run every row and write the table (target/denied-TIER/), failing
             nothing.
  --walk-rows-only
             run only the fixture rows below (no den build needed).

Before the matrix, two rows check the fixture code itself (den#119):
denied-own-vanish walks a tree whose maintenance.lock a hook removes after
os.walk has listed it and before its lchown; denied-fixture-maintenance
counts the automatic maintenance children of a commit in a fixture made as
build() makes them.
"""
import argparse
import errno
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys

R = pathlib.Path(__file__).resolve().parent.parent
ORACLE_SHA = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'

p = argparse.ArgumentParser()
p.add_argument('--tier', default='native')
p.add_argument('--measure', action='store_true')
p.add_argument('--field', action='store_true')
p.add_argument('--walk-rows-only', action='store_true')
A = p.parse_args()
GIT = pathlib.Path(os.environ.get('DEN_GIT') or next((R / 'target/oracle').glob('*/root/opt/git/bin/git')))
if not A.field:
    assert hashlib.sha256(GIT.read_bytes()).hexdigest() == ORACLE_SHA, 'pinned oracle digest'
DEN = R / 'target' / A.tier / 'den'
ROOT = R / 'target' / ('denied-' + A.tier + ('-field' if A.field else ''))
if ROOT.exists():
    shutil.rmtree(ROOT)
ROOT.mkdir(parents=True)
ROOT.chmod(0o755)
TOOLS = {'git': str(GIT), 'den': str(DEN)}
DROP = os.geteuid() == 0
rows = []
failures = []

# den refuses these by name: a tracked path below a directory that cannot be
# listed, whose lookup is denied, in a walk that would stage it. Git keeps
# the entry and says `PATH: Permission denied`.
REFUSED = {}
for shape, path in [('tracked-inside', 'tracked/f'), ('deep', 'src/one/two/keep')]:
    for command in ('add-all', 'add-dot', 'add-update', 'commit-all'):
        REFUSED[shape + '/' + command] = 'not yet implemented: worktree tracked path %s: Permission denied' % path


def drop():
    os.setgroups([])
    os.setgid(65534)
    os.setuid(65534)


def run(argv, cwd, unprivileged=True):
    q = subprocess.run([str(x) for x in argv], cwd=cwd, capture_output=True, timeout=120,
                       preexec_fn=drop if DROP and unprivileged else None)
    return q


def text(data):
    return data.decode('utf-8', 'backslashreplace')


def g(cwd, *args):
    q = run([GIT, *args], cwd, unprivileged=False)
    assert q.returncode == 0, (args, q.stderr)
    return text(q.stdout)


def walk(path, each, dirs_only=False):
    """Call each(full) on every entry os.walk lists below path. An entry
    gone by its turn (den#119: the pinned Git's background maintenance takes
    and drops objects/maintenance.lock) is skipped and counted; any other
    error fails the walk. Returns the count."""
    vanished = 0
    for dirpath, dirs, files in os.walk(path):
        for name in dirs if dirs_only else dirs + files:
            try:
                each(os.path.join(dirpath, name))
            except FileNotFoundError:
                vanished += 1
    return vanished


def lchown_tree(path, uid, gid, lchown=os.lchown):
    """lchown path and everything below it; lchown is the row's hook."""
    vanished = walk(path, lambda full: lchown(full, uid, gid))
    lchown(path, uid, gid)
    return vanished


def own(path):
    """Hand a tree to the unprivileged user (container root only)."""
    if not DROP:
        return
    vanished = lchown_tree(path, 65534, 65534)
    if vanished:
        print('own: vanished %d under %s' % (vanished, os.path.relpath(path, ROOT)), flush=True)


def reclaim(path):
    """Give every permission back and, as root, take the tree back."""
    def unlock(full):
        if not os.path.islink(full):
            os.chmod(full, 0o755)
    vanished = walk(path, unlock, dirs_only=True)
    if DROP:
        vanished += lchown_tree(path, 0, 0)
    if vanished:
        print('reclaim: vanished %d under %s' % (vanished, os.path.relpath(path, ROOT)), flush=True)


def own_vanish_row():
    """den#119: an entry os.walk listed is gone when the walk reaches it (the
    pinned Git's background maintenance took and dropped
    objects/maintenance.lock). The hook removes the lock after the listing
    and before its lchown, every time; the walk must skip and count it. Any
    other error must still fail the walk."""
    name = 'denied-own-vanish'
    tree = ROOT / 'own-vanish'
    lock = tree / '.git' / 'objects' / 'maintenance.lock'
    lock.parent.mkdir(parents=True)
    (tree / 'a.txt').write_text('a\n')
    lock.write_text('')
    uid, gid = (65534, 65534) if DROP else (os.geteuid(), os.getegid())
    problems, removed = [], []

    def vanish(full, uid, gid):
        if full == str(lock):
            lock.unlink()
            removed.append(full)
        os.lchown(full, uid, gid)

    try:
        vanished = lchown_tree(tree, uid, gid, vanish)
        if not removed:
            problems.append('the walk never reached the lock')
        elif vanished != 1:
            problems.append('vanished=%d, not 1' % vanished)
        owners = {(st.st_uid, st.st_gid) for st in (os.lstat(os.path.join(d, n)) for d, ds, fs in os.walk(tree)
                                                     for n in ds + fs)}
        if owners != {(uid, gid)}:
            problems.append('owners after the walk: %r' % sorted(owners))
    except OSError as exc:
        vanished = None
        problems.append('a vanished entry failed the walk: %s: %s' % (type(exc).__name__, exc))

    def refuse(full, uid, gid):
        if full.endswith('a.txt'):
            raise PermissionError(errno.EPERM, 'planted refusal', full)
        os.lchown(full, uid, gid)

    try:
        lchown_tree(tree, uid, gid, refuse)
        problems.append('a PermissionError was swallowed')
    except PermissionError:
        pass
    shutil.rmtree(tree)
    print(('PASS ' if not problems else 'FAIL ') + name +
          (' vanished=%s' % vanished if not problems else ' ' + '; '.join(problems)), flush=True)
    return not problems


def commit(work, *paths, message='two'):
    g(work, 'add', *paths)
    g(work, 'commit', '-q', '-m', message)


def nested(work):
    (work / 'nt-locked.tmp' / 'locked').mkdir(parents=True)
    return [(work / 'nt-locked.tmp' / 'locked', 0o000)]


def top(work):
    (work / 'locked').mkdir()
    (work / 'locked' / 'x').write_text('x\n')
    return [(work / 'locked', 0o000)]


def beside_tracked(work):
    (work / 'dir').mkdir()
    (work / 'dir' / 'f').write_text('f\n')
    commit(work, 'dir/f')
    (work / 'dir' / 'locked').mkdir()
    return [(work / 'dir' / 'locked', 0o000)]


def ignored(work):
    (work / '.gitignore').write_text('locked/\n')
    (work / 'locked').mkdir()
    return [(work / 'locked', 0o000)]


def ignored_parent(work):
    (work / '.gitignore').write_text('*.tmp\n')
    (work / 'nt-locked.tmp' / 'locked').mkdir(parents=True)
    return [(work / 'nt-locked.tmp' / 'locked', 0o000)]


def tracked_inside(work):
    (work / 'tracked').mkdir()
    (work / 'tracked' / 'f').write_text('f\n')
    commit(work, 'tracked/f')
    return [(work / 'tracked', 0o000)]


def listing_only(work):
    (work / 'rdonly').mkdir()
    (work / 'rdonly' / 'x').write_text('x\n')
    return [(work / 'rdonly', 0o444)]


def search_only(work):
    (work / 'xonly').mkdir()
    (work / 'xonly' / 'y').write_text('y\n')
    commit(work, 'xonly/y')
    (work / 'xonly' / 'z').write_text('z\n')
    return [(work / 'xonly', 0o111)]


def two_locked(work):
    for name in ('b-locked', 'a-locked'):
        (work / name).mkdir()
    (work / 'new.txt').write_text('n\n')
    return [(work / 'b-locked', 0o000), (work / 'a-locked', 0o000)]


def deep(work):
    (work / 'src' / 'one' / 'two').mkdir(parents=True)
    (work / 'src' / 'one' / 'two' / 'keep').write_text('k\n')
    (work / 'src' / 'one' / 'new').write_text('n\n')
    commit(work, 'src/one/two/keep')
    (work / 'src' / 'locked').mkdir()
    return [(work / 'src' / 'one' / 'two', 0o000), (work / 'src' / 'locked', 0o000)]


SHAPES = [('nested', nested), ('top', top), ('beside-tracked', beside_tracked), ('ignored', ignored),
          ('ignored-parent', ignored_parent), ('tracked-inside', tracked_inside), ('listing-only', listing_only),
          ('search-only', search_only), ('two-locked', two_locked), ('deep', deep)]

COMMANDS = [
    ('status-short', ['status', '--short']),
    ('status-long', ['status']),
    ('status-porcelain', ['status', '--porcelain']),
    ('status-all', ['status', '-uall', '--short']),
    ('status-no', ['status', '-uno', '--short']),
    ('status-ignored', ['status', '--ignored', '--short']),
    ('add-all', ['add', '-A']),
    ('add-dot', ['add', '.']),
    ('add-update', ['add', '-u']),
    ('commit-all', ['commit', '-a', '-m', 'all']),
]


def init_fixture(work):
    """A fixture repository with its first commit, as every row starts."""
    work.mkdir(parents=True)
    g(work, 'init', '-q', '-b', 'main')
    (work / 'a.txt').write_text('hi\n')
    commit(work, 'a.txt', message='one')


def fixture_maintenance_row():
    """den#119's cause: a Git command in a fixture may start automatic
    maintenance (git-maintenance(1), maintenance.auto; git-config(1),
    gc.auto), which takes objects/maintenance.lock while own() walks. A commit
    in a fixture made as build() makes them must start none. The commit runs
    any maintenance joined (maintenance.autoDetach=false), so its trace2
    events are complete when it returns."""
    name = 'denied-fixture-maintenance'
    work = ROOT / 'fixture-maintenance'
    trace = ROOT / 'fixture-maintenance.trace'
    init_fixture(work)
    q = subprocess.run([str(GIT), '-c', 'maintenance.autoDetach=false', 'commit', '-q', '--allow-empty', '-m', 'probe'],
                       cwd=work, env={**os.environ, 'GIT_TRACE2_EVENT': str(trace)}, capture_output=True, timeout=120)
    events = [json.loads(line) for line in trace.read_text().splitlines() if line.strip()] if trace.exists() else []
    children = [e.get('argv', []) for e in events
                if e.get('event') == 'child_start' and {'maintenance', 'gc'} & set(e.get('argv', []))]
    problems = []
    if q.returncode:
        problems.append('commit exit %d: %r' % (q.returncode, text(q.stderr)[:200]))
    if not events:
        problems.append('the commit wrote no trace2 events')
    if children:
        problems.append('%d automatic maintenance child(ren): %s' % (len(children), ' '.join(children[0])))
    shutil.rmtree(work)
    trace.unlink(missing_ok=True)
    print(('PASS ' if not problems else 'FAIL ') + name +
          (' children=0' if not problems else ' ' + '; '.join(problems)), flush=True)
    return not problems


def build(work, shape):
    init_fixture(work)
    locks = shape(work)
    own(work)
    for path, mode in locks:
        path.chmod(mode)
    return locks


def state(work):
    index = run([GIT, 'ls-files', '-s'], work)
    tree = run([GIT, 'rev-parse', 'HEAD^{tree}'], work)
    return [text(index.stdout), text(tree.stdout)]


def record(name, git_res, den_res, extra):
    same = git_res == den_res and extra['git'] == extra['den']
    row = dict(name=name, git=git_res, den=den_res, extra=extra, same=same)
    want = REFUSED.get(name)
    row['refusal'] = want
    rows.append(row)
    if want is not None:
        ok = den_res['status'] != 0 and want in den_res['stderr'] and extra['den'] == extra['before']
        row['passed'] = ok
        if ok:
            print('PASS', name, 'refused by name (git: status %d)' % git_res['status'], flush=True)
            return
    else:
        row['passed'] = same
        if same:
            print('PASS', name, flush=True)
            return
    failures.append(name)
    print(('DIFF ' if A.measure else 'FAIL ') + name, 'git=' + json.dumps(git_res), 'den=' + json.dumps(den_res),
          'extra=' + json.dumps(extra), flush=True)


walk_failures = [row for row, ok in (('denied-own-vanish', own_vanish_row()),
                                     ('denied-fixture-maintenance', fixture_maintenance_row())) if not ok]
if A.walk_rows_only:
    sys.exit(1 if walk_failures else 0)
assert DEN.is_file(), DEN
try:
    for shape_name, shape in SHAPES:
        for command_name, argv in COMMANDS:
            name = '%s/%s' % (shape_name, command_name)
            res, after, before = {}, {}, None
            for tool in ('git', 'den'):
                work = ROOT / shape_name / command_name / tool
                build(work, shape)
                if command_name == 'commit-all':
                    (work / 'a.txt').write_text('changed\n')
                if before is None:
                    before = state(work)
                q = run([TOOLS[tool], *argv], work)
                res[tool] = {'status': q.returncode, 'stdout': text(q.stdout), 'stderr': text(q.stderr)}
                after[tool] = state(work)
                reclaim(work)
            record(name, res['git'], res['den'], {'git': after['git'], 'den': after['den'], 'before': before})
finally:
    (ROOT / 'rows.json').write_text(json.dumps(rows, indent=1))
print('DENIED rows=%d passed=%d failed=%d unprivileged=%s' % (len(rows), len(rows) - len(failures), len(failures),
                                                              'uid 65534' if DROP else 'uid %d' % os.geteuid()))
if (failures or walk_failures) and not A.measure:
    sys.exit(1)
