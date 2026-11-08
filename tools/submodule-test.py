"""vc25 exact submodule rows: den against the pinned Git, black-box.

Every row runs one argv in an identical copy of a seeded world, at the same
physical path, once per tool, and compares the complete process result
(status, stdout, stderr) and the complete world afterwards: superproject,
.git/modules/*, submodule worktrees and the bare remotes. Loose objects are
compared by oid and inflated bytes (R4a); every index is compared byte for
byte except the six timing/identity words both tools prove against their own
lstat (tools/index-proof.py). The only named difference is den's reflog
identity (R-vc18-2): a row whose sole differences are reflog files under a
`logs/` of any gitdir is KNOWN, never counted as parity.

Sources: gitsubmodules(7), git-submodule(1), gitmodules(5),
gitrepository-layout(5), git-clone(1), git-config(1), git-status(1),
git-diff(1), git-ls-tree(1), git-ls-files(1) of Git v2.56.0. No Git source.

DEN_SUBMODULE_FIELD=1 runs against a field Git (macOS Homebrew) without the
oracle digest check, for development only; its summary says FIELD and the
gate never sets it.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import zlib

PINNED = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
p = argparse.ArgumentParser()
p.add_argument('--tier', default='native')
p.add_argument('--family', required=True)
p.add_argument('--only', default='')
a = p.parse_args()
R = Path(__file__).resolve().parent.parent
G = Path(os.environ['DEN_GIT'])
FIELD = os.environ.get('DEN_SUBMODULE_FIELD') == '1'
if not FIELD:
    assert hashlib.sha256(G.read_bytes()).hexdigest() == PINNED, 'not the pinned oracle'
D = R / 'target' / a.tier / 'den'
root = R / 'target' / ('submodule-' + a.tier + '-' + a.family)
if root.exists():
    shutil.rmtree(root)
root.mkdir(parents=True)
world = root / 'world'
proof = runpy.run_path(str(R / 'tools/index-proof.py'))
LOOSE = re.compile(r'(^|/)objects/[0-9a-f]{2}/[0-9a-f]{38}$')
LOGS = re.compile(r'(^|/)(\.git|modules/[^/]+(/modules/[^/]+)*)/logs(/|$)')
ALLOW_FILE = {'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'protocol.file.allow',
              'GIT_CONFIG_VALUE_0': 'always'}
rows = []
seeds = {}


def env_with(extra):
    e = dict(os.environ)
    e.update(extra or {})
    return e


def run(exe, args, cwd, extra=None, data=None):
    q = subprocess.run([str(exe), *args], cwd=cwd, input=data, capture_output=True,
                       timeout=300, env=env_with(extra))
    return dict(status=q.returncode, stdout=q.stdout.decode('utf-8', 'backslashreplace'),
                stderr=q.stderr.decode('utf-8', 'backslashreplace'))


def g(*args, cwd, extra=None, data=None):
    q = subprocess.run([str(G), *args], cwd=cwd, input=data, capture_output=True,
                       timeout=300, env=env_with(extra))
    assert q.returncode == 0, (args, cwd, q.stderr)
    return q.stdout.decode()


def state(path):
    result = {}
    for f in sorted(path.rglob('*')):
        rel = f.relative_to(path).as_posix()
        if f.is_symlink():
            result[rel] = ['symlink', os.readlink(f)]
        elif f.is_file():
            raw = f.read_bytes()
            if LOOSE.search(rel):
                result[rel] = ['loose', f.stat().st_mode & 0o7777, zlib.decompress(raw).hex()]
            else:
                result[rel] = [f.stat().st_mode & 0o7777, raw.hex()]
        elif f.is_dir():
            result[rel] = ['directory', f.stat().st_mode & 0o7777]
    return result


def worktree_of(index_path):
    """The worktree an index belongs to: a .git/index's parent, or a
    modules/<name>/index's core.worktree."""
    gitdir = index_path.parent
    if gitdir.name == '.git':
        return gitdir.parent
    config = gitdir / 'config'
    if config.is_file():
        m = re.search(r'^\s*worktree\s*=\s*(.+)$', config.read_text(), re.M)
        if m:
            return (gitdir / m.group(1).strip()).resolve()
    return None


def indexes(base):
    found = {}
    for f in base.rglob('index'):
        if f.is_file() and not f.is_symlink() and (f.parent.name == '.git' or f.parent.parent.name == 'modules'):
            tree = worktree_of(f)
            raw = f.read_bytes()
            found[f.relative_to(base).as_posix()] = (raw, proof['proof'](tree, raw) if tree else None)
    return found


def seed(name, build):
    """Build a seed world once (with the pinned Git) and keep a copy."""
    if name not in seeds:
        if world.exists():
            shutil.rmtree(world)
        world.mkdir()
        build(world)
        kept = root / ('seed-' + name)
        shutil.copytree(world, kept, symlinks=True)
        seeds[name] = kept
    return seeds[name]


def compare(name, args, seed_name, cwd='.', extra=None, data=None, prepare=None):
    if a.only and not re.search(a.only, name):
        return
    outcomes = []
    for exe in [G, D]:
        if world.exists():
            shutil.rmtree(world)
        shutil.copytree(seeds[seed_name], world, symlinks=True)
        if prepare:
            prepare(world)
        q = run(exe, args, world / cwd, extra, data)
        after = state(world)
        outcomes.append(dict(result=q, after=after, indexes=indexes(world)))
    left, right = outcomes
    index_errors = []
    for key in sorted(set(left['indexes']) & set(right['indexes'])):
        (lraw, lproof), (rraw, rproof) = left['indexes'][key], right['indexes'][key]
        if lraw == rraw:
            continue
        try:
            if lproof is None or rproof is None:
                raise ValueError('no worktree for ' + key)
            lc, rc, _ = proof['canonical_pair'](lraw, rraw, lproof, rproof)
            left['after'][key] = [left['after'][key][0], lc.hex()]
            right['after'][key] = [right['after'][key][0], rc.hex()]
        except ValueError as error:
            index_errors.append(key + ': ' + str(error))
    ok = left['result'] == right['result'] and left['after'] == right['after'] and not index_errors
    differing = sorted(k for k in left['after'].keys() | right['after'].keys()
                       if left['after'].get(k) != right['after'].get(k))
    known = (not ok and left['result'] == right['result'] and not index_errors and differing
             and all(LOGS.search(k) for k in differing))
    rows.append(dict(name=name, argv=args, cwd=cwd, extra=extra or {}, equal=ok, known=known,
                     expected=dict(result=left['result']), actual=dict(result=right['result']),
                     differing_paths=differing, index_errors=index_errors))
    verdict = 'PASS' if ok else 'KNOWN' if known else 'FAIL'
    print(verdict, name + ((' reflog-paths=' + ','.join(differing)) if known else ''), flush=True)
    if verdict == 'FAIL':
        print('  argv', args, 'cwd', cwd, flush=True)
        if left['result'] != right['result']:
            print('  expected', json.dumps(left['result']), flush=True)
            print('  actual  ', json.dumps(right['result']), flush=True)
        print('  differing_paths', differing[:12], 'index_errors', index_errors, flush=True)


# ---- fixtures ---------------------------------------------------------------

def commit(repo, message):
    g('commit', '-q', '-m', message, cwd=repo)


def remotes(w):
    """leaf <- mid (relative ../leaf.git as leafsub at deps/leaf) <- top (mid
    as midname at mid, relative; leaf at abs, file://, branch = main)."""
    for r in ('leaf', 'mid', 'top'):
        g('init', '-q', '--bare', str(w / (r + '.git')), cwd=w)
    src = w / 'src'
    src.mkdir()
    g('init', '-q', 'leaf', cwd=src)
    (src / 'leaf/leaf.txt').write_text('one\n')
    g('add', 'leaf.txt', cwd=src / 'leaf')
    commit(src / 'leaf', 'leaf one')
    g('tag', '-a', '-m', 'annotated', 'v1', cwd=src / 'leaf')
    (src / 'leaf/leaf.txt').write_text('one\ntwo\n')
    g('commit', '-q', '-am', 'leaf two', cwd=src / 'leaf')
    g('push', '-q', '--tags', str(w / 'leaf.git'), 'main', cwd=src / 'leaf')
    g('init', '-q', 'mid', cwd=src)
    g('remote', 'add', 'origin', str(w / 'mid.git'), cwd=src / 'mid')
    (src / 'mid/mid.txt').write_text('mid\n')
    g('add', 'mid.txt', cwd=src / 'mid')
    g('submodule', 'add', '-q', '--name', 'leafsub', '../leaf.git', 'deps/leaf', cwd=src / 'mid', extra=ALLOW_FILE)
    commit(src / 'mid', 'mid with leaf')
    g('push', '-q', 'origin', 'main', cwd=src / 'mid')
    g('init', '-q', 'top', cwd=src)
    g('remote', 'add', 'origin', str(w / 'top.git'), cwd=src / 'top')
    (src / 'top/top.txt').write_text('top\n')
    g('add', 'top.txt', cwd=src / 'top')
    g('submodule', 'add', '-q', '--name', 'midname', '../mid.git', 'mid', cwd=src / 'top', extra=ALLOW_FILE)
    g('submodule', 'add', '-q', '-b', 'main', 'file://' + str(w / 'leaf.git'), 'abs', cwd=src / 'top', extra=ALLOW_FILE)
    commit(src / 'top', 'top with mid and abs')
    g('push', '-q', 'origin', 'main', cwd=src / 'top')
    shutil.rmtree(src)


def recursive_clone(w):
    remotes(w)
    g('clone', '-q', '--recurse-submodules', 'file://' + str(w / 'top.git'), 'c', cwd=w, extra=ALLOW_FILE)


def plain_clone(w):
    remotes(w)
    g('clone', '-q', 'file://' + str(w / 'top.git'), 'c', cwd=w)


def moved(w):
    """The recursive clone with a new commit in mid, staged and committed in
    top (a moved gitlink), then mid moved again (unstaged)."""
    recursive_clone(w)
    c = w / 'c'
    (c / 'mid/mid.txt').write_text('mid\nchanged\n')
    g('commit', '-q', '-am', 'mid two', cwd=c / 'mid')
    g('add', 'mid', cwd=c)
    commit(c, 'move mid')


# ---- families ---------------------------------------------------------------

def family_read():
    seed('moved', moved)
    for argv in (['ls-tree', 'HEAD'], ['ls-tree', '-r', 'HEAD'], ['ls-tree', 'HEAD', 'mid'],
                 ['ls-tree', '--name-only', 'HEAD'], ['ls-tree', '-d', 'HEAD'], ['ls-tree', '-t', '-r', 'HEAD'],
                 ['ls-tree', '-z', 'HEAD'], ['ls-files'], ['ls-files', '-s'], ['ls-files', '-s', 'mid'],
                 ['ls-files', '-z'], ['cat-file', '-p', 'HEAD^{tree}'], ['log', '-p', '-1'], ['log', '--stat', '-1'],
                 ['log', '--oneline'], ['show'], ['show', '--stat'],
                 ['show', '--submodule=log'], ['show', '--submodule=diff'], ['show', '--submodule=short'],
                 ['diff', 'HEAD~1', 'HEAD'], ['diff', '--submodule=log', 'HEAD~1', 'HEAD'],
                 ['diff', '--submodule=diff', 'HEAD~1', 'HEAD'], ['diff', '--stat', 'HEAD~1', 'HEAD'],
                 ['diff', '--numstat', 'HEAD~1', 'HEAD'], ['diff', '--name-status', 'HEAD~1', 'HEAD'],
                 ['diff', '--name-only', 'HEAD~1', 'HEAD'], ['diff', '--shortstat', 'HEAD~1', 'HEAD'],
                 ['diff', '--submodule=log', 'HEAD', 'HEAD~1'], ['log', '-p', '--root', '--submodule=log'],
                 ['diff', '--submodule=diff', 'HEAD', 'HEAD~1'], ['show', '--submodule=log', 'HEAD~1'],
                 ['diff', '-c', 'diff.submodule=log', 'HEAD~1', 'HEAD'],
                 ['show', 'HEAD:mid'], ['log', '-p', '--submodule=log', '-2']):
        if argv[:2] == ['diff', '-c']:
            compare('read-diff-config-log', ['diff', 'HEAD~1', 'HEAD'], 'moved', cwd='c',
                    extra={'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'diff.submodule', 'GIT_CONFIG_VALUE_0': 'log'})
            continue
        compare('read-' + '-'.join(x.strip('-').replace('^{tree}', '-tree').replace('~', '').replace(':', '-')
                                   for x in argv), argv, 'moved', cwd='c')


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def sub_commit(w, path, message):
    c = w / 'c' / path
    g('commit', '-q', '--allow-empty', '-m', message, cwd=c)


# Worktree states of the recursive clone, each applied to both copies alike.
STATES = {
    'clean': lambda w: None,
    'untracked': lambda w: write(w / 'c/mid/untracked.txt', 'u\n'),
    'modified': lambda w: write(w / 'c/mid/mid.txt', 'mid\nchanged\n'),
    'modified-untracked': lambda w: (write(w / 'c/mid/mid.txt', 'mid\nchanged\n'), write(w / 'c/mid/u', 'u\n')),
    'new-commits': lambda w: sub_commit(w, 'mid', 'mid two'),
    'new-commits-untracked': lambda w: (sub_commit(w, 'mid', 'mid two'), write(w / 'c/mid/u', 'u\n')),
    'new-commits-modified': lambda w: (sub_commit(w, 'mid', 'mid two'), write(w / 'c/mid/mid.txt', 'x\n')),
    'nested-untracked': lambda w: write(w / 'c/mid/deps/leaf/deep.txt', 'deep\n'),
    'nested-new-commits': lambda w: sub_commit(w, 'mid/deps/leaf', 'leaf moved'),
    'staged-in-sub': lambda w: (write(w / 'c/mid/s.txt', 's\n'), g('add', 's.txt', cwd=w / 'c/mid')),
    'staged-gitlink': lambda w: (sub_commit(w, 'mid', 'mid two'), g('add', 'mid', cwd=w / 'c')),
    'staged-and-dirty': lambda w: (sub_commit(w, 'mid', 'mid two'), g('add', 'mid', cwd=w / 'c'), write(w / 'c/mid/u', 'u\n')),
    'two-subs': lambda w: (sub_commit(w, 'mid', 'mid two'), write(w / 'c/abs/u', 'u\n')),
}
STATUS_FORMS = [['status'], ['status', '-s'], ['status', '--porcelain'], ['status', '--porcelain', '-z'],
                ['status', '-sb']]


def state_seed(state):
    """A seed holding the recursive clone in STATE: built once, so both tools
    start from byte-identical copies (index stat words included)."""
    name = 'clone-' + state
    seed(name, lambda w: (recursive_clone(w), STATES[state](w)))
    return name


def family_status():
    seed('clone', recursive_clone)
    seed('plain', plain_clone)
    for state in STATES:
        for argv in STATUS_FORMS:
            compare('status-%s-%s' % (state, '-'.join(x.strip('-') for x in argv[1:]) or 'long'), argv,
                    state_seed(state), cwd='c')
    for when in ('none', 'untracked', 'dirty', 'all'):
        for state in ('modified-untracked', 'new-commits-untracked', 'untracked'):
            compare('status-ignore-%s-%s' % (when, state), ['status', '-s', '--ignore-submodules=' + when],
                    state_seed(state), cwd='c')
            compare('status-config-ignore-%s-%s' % (when, state), ['status', '-s'], state_seed(state), cwd='c',
                    extra={'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'submodule.midname.ignore',
                                                  'GIT_CONFIG_VALUE_0': when})
        compare('status-gitmodules-ignore-%s' % when, ['status'], 'clone', cwd='c',
                prepare=lambda w, when=when: (STATES['modified-untracked'](w),
                                              g('config', '-f', '.gitmodules', 'submodule.midname.ignore', when, cwd=w / 'c')))
    compare('status-ignore-bare-flag', ['status', '-s', '--ignore-submodules'], state_seed('new-commits'), cwd='c')
    for argv in STATUS_FORMS:
        compare('status-unpopulated-' + ('-'.join(x.strip('-') for x in argv[1:]) or 'long'), argv, 'plain', cwd='c')
    compare('status-unpopulated-moved', ['status'], 'plain', cwd='c',
            prepare=lambda w: g('update-index', '--cacheinfo', '160000,' + '1' * 40 + ',mid', cwd=w / 'c'))
    compare('status-unpopulated-missing-dir', ['status', '-s'], 'plain', cwd='c',
            prepare=lambda w: (w / 'c/mid').rmdir())
    compare('status-from-subdirectory', ['status'], 'clone', cwd='c/mid/deps',
            prepare=STATES['nested-untracked'])
    compare('status-inside-submodule', ['status', '-s'], state_seed('nested-new-commits'), cwd='c/mid')


DIFF_FORMS = [['diff'], ['diff', '--stat'], ['diff', '--numstat'], ['diff', '--submodule=log'],
              ['diff', '--submodule=diff'], ['diff', '--cached'], ['diff', 'HEAD'], ['diff', '--ignore-submodules=dirty'],
              ['diff', '--ignore-submodules=none'], ['diff', '--ignore-submodules'], ['diff', '--name-only']]


def family_diff():
    seed('clone', recursive_clone)
    seed('plain', plain_clone)
    for state in STATES:
        for argv in DIFF_FORMS:
            compare('diff-%s-%s' % (state, '-'.join(x.strip('-') for x in argv[1:]) or 'patch'), argv,
                    state_seed(state), cwd='c')
    for argv in (['diff'], ['diff', '--cached'], ['diff', '--cached', '--submodule=log']):
        compare('diff-unpopulated-moved-' + ('-'.join(x.strip('-') for x in argv[1:]) or 'patch'), argv, 'plain',
                cwd='c', prepare=lambda w: g('update-index', '--cacheinfo', '160000,' + '1' * 40 + ',mid', cwd=w / 'c'))


FAMILIES = {'read': family_read, 'status': family_status, 'diff': family_diff}

try:
    FAMILIES[a.family]()
finally:
    output = R / 'target/runs' / ('submodule-' + a.tier + '-' + a.family + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dict(rows=rows, field=FIELD), indent=1) + '\n')
exact = sum(r['equal'] for r in rows)
known = sum(r['known'] for r in rows)
failed = len(rows) - exact - known
print('submodule %s %s exact=%d known=%d failed=%d rows=%d%s' % (
    a.tier, a.family, exact, known, failed, len(rows), ' FIELD' if FIELD else ''), flush=True)
raise SystemExit(0 if rows and failed == 0 else 1)
