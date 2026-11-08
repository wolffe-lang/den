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
            found[f.relative_to(base).as_posix()] = (raw, gitlink_proof(raw, proof['proof'](tree, raw)) if tree else None)
    return found


def gitlink_proof(raw, rows):
    """R-vc25-13: a gitlink's entry keeps the stat its directory had when the
    superproject's checkout made it, before the submodule filled it, in the
    pinned Git as in den, so its time words cannot equal the directory's
    lstat afterwards. Such an entry counts as proven when its dev and ino
    equal its own directory's and its ctime and mtime are no later than the
    directory's own: the rows' proof rows are rewritten to say so, and only
    for mode-160000 entries."""
    if rows is None:
        return rows
    out = []
    for entry, row in zip(proof['entries'](raw), rows):
        row = dict(row)
        own = row['own_worktree_stat']
        words = entry['words']
        if (words[6] == 0o160000 and own is not None and not row['proven'] and words[4:6] == own[4:6]
                and (words[0], words[1]) <= (own[0], own[1]) and (words[2], words[3]) <= (own[2], own[3])):
            row['own_worktree_stat'] = list(words[:6]) + list(own[6:])
            row['proven'] = True
            row['gitlink_stale_proof'] = True
        out.append(row)
    return out


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
    if FIELD:
        # macOS only: Git probes the case-insensitive file system and writes
        # two core lines the Linux oracle never writes. Field mode drops them
        # from both sides; the gate never runs in field mode.
        drop = b'\tignorecase = true\n\tprecomposeunicode = true\n'.hex()
        for side in (left, right):
            for key, value in side['after'].items():
                if key.endswith('config') and value[0] != 'directory' and drop in value[1]:
                    side['after'][key] = [value[0], value[1].replace(drop, '')]
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
                 ['diff', '--submodule=log', 'HEAD', 'HEAD~1'], ['log', '-p', '--submodule=log'],
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


def detach(w, path, rev):
    g('-c', 'advice.detachedHead=false', 'checkout', '-q', '--detach', rev, cwd=w / 'c' / path)


SEEDS = {
    'plain-init': lambda w: (plain_clone(w), g('submodule', 'init', cwd=w / 'c', extra=ALLOW_FILE)),
    'plain-updated': lambda w: (plain_clone(w), g('submodule', 'update', '--init', cwd=w / 'c', extra=ALLOW_FILE)),
    'abs-behind': lambda w: (recursive_clone(w), detach(w, 'abs', 'HEAD~1')),
    'abs-behind-dirty': lambda w: (recursive_clone(w), detach(w, 'abs', 'HEAD~1'), write(w / 'c/abs/leaf.txt', 'mine\n')),
    'url-moved': lambda w: (recursive_clone(w), shutil.copytree(w / 'mid.git', w / 'mid-moved.git'),
                            g('config', '-f', '.gitmodules', 'submodule.midname.url', '../mid-moved.git', cwd=w / 'c')),
    'sub-dir': lambda w: (recursive_clone(w), (w / 'c/x').mkdir()),
}


def named_seed(name):
    seed(name, SEEDS[name])
    return name


def family_clone():
    seed('remotes', remotes)
    top = 'file://' + str(root / 'world/top.git')
    compare('clone-recurse-default-policy', ['clone', '--recurse-submodules', top, 'c'], 'remotes')
    compare('clone-recurse', ['clone', '--recurse-submodules', top, 'c'], 'remotes', extra=ALLOW_FILE)
    compare('clone-recursive-alias', ['clone', '--recursive', top, 'c'], 'remotes', extra=ALLOW_FILE)
    compare('clone-recurse-quiet', ['clone', '-q', '--recurse-submodules', top, 'c'], 'remotes', extra=ALLOW_FILE)
    compare('clone-recurse-pathspec', ['clone', '--recurse-submodules=abs', top, 'c'], 'remotes', extra=ALLOW_FILE)
    compare('clone-recurse-pathspec-none', ['clone', '--recurse-submodules=nomatch', top, 'c'], 'remotes', extra=ALLOW_FILE)
    compare('clone-plain', ['clone', top, 'c'], 'remotes', extra=ALLOW_FILE)
    compare('clone-recurse-bare', ['clone', '--bare', '--recurse-submodules', top, 'c.git'], 'remotes', extra=ALLOW_FILE)
    seed('plain', plain_clone)
    seed('clone', recursive_clone)
    for name, argv in (('status', ['submodule', 'status']), ('bare', ['submodule']), ('init', ['submodule', 'init']),
                       ('init-path', ['submodule', 'init', 'abs']), ('update', ['submodule', 'update']),
                       ('update-init', ['submodule', 'update', '--init']),
                       ('update-init-recursive', ['submodule', 'update', '--init', '--recursive']),
                       ('update-init-path', ['submodule', 'update', '--init', '--', 'mid']),
                       ('update-unknown-path', ['submodule', 'update', '--', 'nope']),
                       ('update-nonsubmodule-path', ['submodule', 'update', '--', 'top.txt']),
                       ('status-recursive', ['submodule', 'status', '--recursive']),
                       ('sync', ['submodule', 'sync']), ('foreach', ['submodule', 'foreach', 'echo $name'])):
        compare('submodule-plain-' + name, argv, 'plain', cwd='c', extra=ALLOW_FILE)
    for name, argv in (('status', ['submodule', 'status']), ('update', ['submodule', 'update']),
                       ('update-recursive', ['submodule', 'update', '--init', '--recursive']),
                       ('status-recursive', ['submodule', 'status', '--recursive'])):
        compare('submodule-init-' + name, argv, named_seed('plain-init'), cwd='c', extra=ALLOW_FILE)
        compare('submodule-updated-' + name, argv, named_seed('plain-updated'), cwd='c', extra=ALLOW_FILE)
    for name, argv in (('status', ['submodule', 'status']), ('status-cached', ['submodule', 'status', '--cached']),
                       ('status-recursive', ['submodule', 'status', '--recursive']),
                       ('status-path', ['submodule', 'status', 'mid']),
                       ('update', ['submodule', 'update']), ('update-recursive', ['submodule', 'update', '--recursive']),
                       ('sync', ['submodule', 'sync']), ('sync-recursive', ['submodule', 'sync', '--recursive']),
                       ('foreach', ['submodule', 'foreach', 'echo "$name|$sm_path|$displaypath|$sha1|$toplevel"']),
                       ('foreach-recursive', ['submodule', 'foreach', '--recursive', 'echo "$name|$sm_path|$displaypath|$sha1|$toplevel"']),
                       ('foreach-quiet', ['submodule', '--quiet', 'foreach', 'echo $name']),
                       ('foreach-fail', ['submodule', 'foreach', 'exit 3']),
                       ('foreach-path-variable', ['submodule', 'foreach', 'echo "$path"']),
                       ('foreach-two-words', ['submodule', 'foreach', 'echo', 'a', 'b'])):
        compare('submodule-clone-' + name, argv, 'clone', cwd='c', extra=ALLOW_FILE)
    compare('submodule-clone-foreach-subdirectory', ['submodule', 'foreach', 'echo "$displaypath"'], named_seed('sub-dir'), cwd='c/x')
    compare('submodule-clone-status-subdirectory', ['submodule', 'status'], named_seed('sub-dir'), cwd='c/x')
    compare('submodule-clone-foreach-inside', ['submodule', 'foreach', 'echo in $displaypath'], 'clone', cwd='c/mid')
    for state in ('new-commits', 'nested-new-commits'):
        for argv in (['submodule', 'status'], ['submodule', 'status', '--recursive'], ['submodule', 'status', '--cached']):
            compare('submodule-%s-%s' % (state, '-'.join(argv[1:])), argv, state_seed(state), cwd='c')
    for argv in (['submodule', 'status'], ['submodule', 'update'], ['submodule', 'update', '--force']):
        compare('submodule-abs-behind-' + '-'.join(argv[1:]), argv, named_seed('abs-behind'), cwd='c', extra=ALLOW_FILE)
        compare('submodule-abs-behind-dirty-' + '-'.join(argv[1:]), argv, named_seed('abs-behind-dirty'), cwd='c', extra=ALLOW_FILE)
    for argv in (['submodule', 'sync'], ['submodule', 'sync', '--recursive'], ['submodule', 'sync', 'mid']):
        compare('submodule-url-moved-' + '-'.join(argv[1:]), argv, named_seed('url-moved'), cwd='c', extra=ALLOW_FILE)
    for refused in ('add', 'deinit', 'set-url', 'set-branch', 'summary', 'absorbgitdirs'):
        pass


def hostile_world(text, links, missing=False):
    """remotes plus a bare superproject h.git whose .gitmodules is TEXT and
    whose gitlinks are LINKS (paths), all at leaf's first commit (or an
    absent commit when MISSING); a plain clone of it at c."""
    def build(w):
        remotes(w)
        leaf = 'file://' + str(w / 'leaf.git')
        g('init', '-q', '--bare', str(w / 'h.git'), cwd=w)
        src = w / 'hsrc'
        g('init', '-q', str(src), cwd=w)
        write(src / 'x', 'x\n')
        g('add', 'x', cwd=src)
        if text is not None:
            write(src / '.gitmodules', text.replace('LEAF', leaf))
            g('add', '.gitmodules', cwd=src)
        first = g('rev-list', '--max-parents=0', 'main', cwd=w / 'leaf.git').strip()
        for link in links:
            g('update-index', '--add', '--cacheinfo', '160000,%s,%s' % ('1' * 40 if missing else first, link), cwd=src)
        g('commit', '-q', '-m', 'hostile', cwd=src)
        g('push', '-q', str(w / 'h.git'), 'main', cwd=src)
        shutil.rmtree(src)
        g('clone', '-q', 'file://' + str(w / 'h.git'), 'c', cwd=w)
    return build


HOSTILE = {
    'escape-path': ('[submodule "e"]\n\tpath = ../escape\n\turl = LEAF\n', ['inside']),
    'dotdot-name': ('[submodule "../evil"]\n\tpath = evil\n\turl = LEAF\n', ['evil']),
    'dotdot-name-mid': ('[submodule "a/../../evil"]\n\tpath = evil\n\turl = LEAF\n', ['evil']),
    'dotdot-name-three-keys': ('[submodule "../evil"]\n\tpath = evil\n\turl = LEAF\n\tbranch = main\n', ['evil']),
    'dotdot-name-url-only': ('[submodule "../evil"]\n\turl = LEAF\n', ['evil']),
    'dash-url': ('[submodule "d"]\n\tpath = d\n\turl = -oProxyCommand=false\n', ['d']),
    'dash-path': ('[submodule "d"]\n\tpath = -d\n\turl = LEAF\n', ['-d']),
    'no-entry': (None, ['orphan']),
    'stale-entry': ('[submodule "s"]\n\tpath = s\n\turl = LEAF\n', []),
    'invalid-config': ('[submodule "bad"\n\tpath = bad\n\turl = LEAF\n', ['bad']),
    'invalid-config-no-gitlink': ('[submodule "bad"\n\tpath = bad\n\turl = LEAF\n', []),
    'invalid-update': ('[submodule "u"]\n\tpath = u\n\turl = LEAF\n\tupdate = !echo hi\n', ['u']),
    'invalid-fetch-recurse': ('[submodule "f"]\n\tpath = f\n\turl = LEAF\n\tfetchRecurseSubmodules = maybe\n', ['f']),
    'invalid-ignore': ('[submodule "i"]\n\tpath = i\n\turl = LEAF\n\tignore = bogus\n', ['i']),
    'case-collide': ('[submodule "A"]\n\tpath = A\n\turl = LEAF\n[submodule "a"]\n\tpath = a\n\turl = LEAF\n', ['A', 'a']),
    'missing-url': ('[submodule "m"]\n\tpath = m\n', ['m']),
    'name-slash': ('[submodule "a/b"]\n\tpath = deep/b\n\turl = LEAF\n', ['deep/b']),
    'comments-and-blank': ('[submodule "s"]\n\tpath = s\n\t# a comment\n\turl = LEAF\n\n[submodule "t"]\n\tpath = t\n\turl = LEAF\n', ['s', 't']),
}


def family_hostile():
    for name, (text, links) in HOSTILE.items():
        seed('hostile-' + name, hostile_world(text, links))
        h = 'file://' + str(root / 'world/h.git')
        compare('hostile-%s-clone' % name, ['clone', '--recurse-submodules', h, 'd'], 'hostile-' + name, extra=ALLOW_FILE)
        for argv in (['submodule', 'update', '--init'], ['status', '--porcelain'], ['submodule', 'status'],
                     ['submodule', 'init'], ['diff'], ['status']):
            compare('hostile-%s-%s' % (name, '-'.join(x.strip('-') for x in argv)), argv, 'hostile-' + name,
                    cwd='c', extra=ALLOW_FILE)
    seed('hostile-missing', hostile_world('[submodule "m"]\n\tpath = m\n\turl = LEAF\n', ['m'], missing=True))
    compare('hostile-missing-commit-clone', ['clone', '--recurse-submodules', 'file://' + str(root / 'world/h.git'), 'd'],
            'hostile-missing', extra=ALLOW_FILE)
    compare('hostile-missing-commit-update', ['submodule', 'update', '--init'], 'hostile-missing', cwd='c', extra=ALLOW_FILE)


def family_transport():
    seed('remotes', remotes)
    top = 'file://' + str(root / 'world/top.git')
    rewrite = dict(ALLOW_FILE)
    rewrite.update({'GIT_CONFIG_COUNT': '2', 'GIT_CONFIG_KEY_1': 'url.file://%s/.insteadOf' % (root / 'world'),
                    'GIT_CONFIG_VALUE_1': 'https://forge.example/o/'})
    def https_urls(w):
        recursive_clone(w)
        c = w / 'c'
        g('config', '-f', '.gitmodules', 'submodule.abs.url', 'https://forge.example/o/leaf.git', cwd=c)
        g('commit', '-q', '-am', 'https url', cwd=c)
        g('push', '-q', 'origin', 'HEAD:main', cwd=c)
        shutil.rmtree(c)
    seed('https-urls', https_urls)
    compare('transport-insteadof-clone', ['clone', '--recurse-submodules', top, 'c'], 'https-urls', extra=rewrite)
    compare('transport-insteadof-unrewritten', ['clone', '-q', '--recurse-submodules', top, 'c'], 'https-urls',
            extra=dict(ALLOW_FILE, GIT_CONFIG_COUNT='2', GIT_CONFIG_KEY_1='url.zzz://never/.insteadOf',
                       GIT_CONFIG_VALUE_1='https://nomatch.example/'))
    compare('transport-file-never', ['clone', '--recurse-submodules', top, 'c'], 'remotes',
            extra={'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'protocol.file.allow', 'GIT_CONFIG_VALUE_0': 'never'})
    compare('transport-file-user-from-user-0', ['clone', '-q', top, 'c'], 'remotes', extra={'GIT_PROTOCOL_FROM_USER': '0'})
    compare('transport-file-user-top-level', ['clone', '-q', top, 'c'], 'remotes')
    compare('transport-protocol-allow-always', ['clone', '-q', '--recurse-submodules', top, 'c'], 'remotes',
            extra={'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'protocol.allow', 'GIT_CONFIG_VALUE_0': 'always'})
    compare('transport-local-path-recurse', ['clone', '-q', '--recurse-submodules', str(root / 'world/top.git'), 'c'],
            'remotes', extra=ALLOW_FILE)


def nosub_branch(w):
    """moved, plus a branch nosub (submodule abs removed) pushed and fetched."""
    moved(w)
    c = w / 'c'
    g('checkout', '-q', '-b', 'nosub', cwd=c)
    g('rm', '-q', 'abs', cwd=c)
    commit(c, 'remove abs')
    g('push', '-q', 'origin', 'nosub', cwd=c)
    g('checkout', '-q', 'main', cwd=c)
    g('submodule', 'update', '-q', '--init', '--recursive', cwd=c, extra=ALLOW_FILE)


SEEDS.update({
    'moved': moved,
    'nosub': nosub_branch,
})


def family_work():
    for state in ('new-commits', 'modified', 'untracked', 'staged-gitlink', 'clean'):
        s = state_seed(state)
        for argv in (['add', 'mid'], ['add', '-A'], ['add', '.'], ['add', '-u'], ['commit', '-q', '-a', '-m', 'all'],
                     ['commit', '-a', '-m', 'all'], ['reset', '--hard'], ['reset'], ['reset', '-q', 'HEAD', '--', 'mid'],
                     ['rm', 'mid'], ['rm', '--cached', 'mid'], ['rm', '-f', 'mid'], ['rm', '-n', 'mid'],
                     ['checkout', '-q', '--detach', 'HEAD'], ['switch', '-q', '--detach', 'HEAD']):
            compare('work-%s-%s' % (state, '-'.join(x.strip('-') for x in argv if x not in ('-m', 'all'))), argv, s, cwd='c')
    compare('work-staged-commit', ['commit', '-m', 'move mid'], state_seed('staged-gitlink'), cwd='c')
    compare('work-add-inside-submodule', ['add', 'mid/mid.txt'], state_seed('modified'), cwd='c')
    compare('work-rm-recursive-all', ['rm', '-r', '-q', '.'], 'clone', cwd='c')
    s = named_seed('moved')
    for argv in (['checkout', 'HEAD~1'], ['checkout', '-q', 'HEAD~1'], ['switch', '--detach', 'HEAD~1'],
                 ['reset', '--hard', 'HEAD~1'], ['reset', 'HEAD~1'], ['reset', '--soft', 'HEAD~1'],
                 ['log', '--oneline'], ['status']):
        compare('work-moved-' + '-'.join(x.strip('-').replace('~', '') for x in argv), argv, s, cwd='c')
    s = named_seed('nosub')
    for argv in (['checkout', 'nosub'], ['switch', 'nosub'], ['checkout', '-q', 'nosub']):
        compare('work-nosub-' + '-'.join(x.strip('-') for x in argv), argv, s, cwd='c')


REFUSALS = [
    ['submodule', 'add', '../x.git', 'x'], ['submodule', 'deinit', 'abs'], ['submodule', 'set-url', 'abs', '../x'],
    ['submodule', 'set-branch', '-b', 'main', 'abs'], ['submodule', 'summary'], ['submodule', 'absorbgitdirs'],
    ['submodule', 'update', '--remote'], ['submodule', 'update', '--merge'], ['submodule', 'update', '--rebase'],
    ['clone', '--shallow-submodules', '--recurse-submodules', 'x', 'y'], ['clone', '--remote-submodules', 'x', 'y'],
    ['mv', 'abs', 'abs2'], ['restore', 'abs'], ['stash'],
    ['push', '--recurse-submodules=check', 'origin', 'main'], ['push', '--recurse-submodules=on-demand', 'origin', 'main'],
]
RECURSE = {'GIT_CONFIG_COUNT': '2', 'GIT_CONFIG_KEY_0': 'protocol.file.allow', 'GIT_CONFIG_VALUE_0': 'always',
           'GIT_CONFIG_KEY_1': 'submodule.recurse', 'GIT_CONFIG_VALUE_1': 'true'}


def family_refusals():
    """Named refusals that remain (vc25b and later): den alone, each must
    refuse by name with exit 2 and change nothing."""
    seed('clone', recursive_clone)
    cases = [(argv, ALLOW_FILE, 'refusal-' + '-'.join(x.strip('-') for x in argv[:3])) for argv in REFUSALS]
    cases.append((['push', 'origin', 'main'], RECURSE, 'refusal-push-submodule-recurse-true'))
    for argv, extra, name in cases:
        if a.only and not re.search(a.only, name):
            continue
        if world.exists():
            shutil.rmtree(world)
        shutil.copytree(seeds['clone'], world, symlinks=True)
        before = state(world)
        q = run(D, argv, world / 'c', extra)
        ok = q['status'] == 2 and 'not yet implemented' in q['stderr'] and state(world) == before
        rows.append(dict(name=name, argv=argv, equal=ok, known=False, refusal=True, actual=dict(result=q)))
        print('PASS' if ok else 'FAIL', name, '' if ok else json.dumps(q), flush=True)


FAMILIES = {'read': family_read, 'status': family_status, 'diff': family_diff, 'clone': family_clone, 'hostile': family_hostile, 'transport': family_transport, 'work': family_work, 'refusals': family_refusals}

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
