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
"""
import argparse
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
A = p.parse_args()
GIT = pathlib.Path(os.environ.get('DEN_GIT') or next((R / 'target/oracle').glob('*/root/opt/git/bin/git')))
if not A.field:
    assert hashlib.sha256(GIT.read_bytes()).hexdigest() == ORACLE_SHA, 'pinned oracle digest'
DEN = R / 'target' / A.tier / 'den'
assert DEN.is_file(), DEN
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


def own(path):
    """Hand a tree to the unprivileged user (container root only)."""
    if not DROP:
        return
    for dirpath, dirs, files in os.walk(path):
        for name in dirs + files:
            os.lchown(os.path.join(dirpath, name), 65534, 65534)
    os.lchown(path, 65534, 65534)


def reclaim(path):
    """Give every permission back and, as root, take the tree back."""
    for dirpath, dirs, files in os.walk(path):
        for name in dirs:
            full = os.path.join(dirpath, name)
            if not os.path.islink(full):
                os.chmod(full, 0o755)
    if DROP:
        for dirpath, dirs, files in os.walk(path):
            for name in dirs + files:
                os.lchown(os.path.join(dirpath, name), 0, 0)
        os.lchown(path, 0, 0)


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


def build(work, shape):
    work.mkdir(parents=True)
    g(work, 'init', '-q', '-b', 'main')
    (work / 'a.txt').write_text('hi\n')
    commit(work, 'a.txt', message='one')
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
if failures and not A.measure:
    sys.exit(1)
