"""vc12 independent importing client: den's public stash/notes layers against
the pinned oracle. Git 2.56.0 git-stash/git-notes documentation and black-box
runs only. Construction must write objects only (no ref, index or worktree
byte changes); every read-only mode must leave the repository byte-identical.
"""
import argparse, collections, hashlib, json, os, pathlib, runpy, shutil, subprocess

ap = argparse.ArgumentParser()
ap.add_argument('--tier', default='native')
a = ap.parse_args()
R = pathlib.Path(__file__).resolve().parent.parent
G = os.environ['DEN_GIT']
assert hashlib.sha256(pathlib.Path(G).read_bytes()).hexdigest() == \
    'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60', 'oracle digest'
C = str(R / f'target/{a.tier}/stash-client')
pack_fixture = runpy.run_path(str(R / 'tools/packed-fixture.py'))['pack_fixture']
root = R / f'target/stash-api-{a.tier}'
shutil.rmtree(root, ignore_errors=True)
root.mkdir(parents=True)


def run(exe, args, cwd, data=None):
    q = subprocess.run([exe, *args], cwd=cwd, input=data, capture_output=True)
    return dict(status=q.returncode, stdout=q.stdout, stderr=q.stderr)


def g(cwd, *args, data=None):
    q = run(G, args, cwd, data)
    assert q['status'] == 0, (args, q)
    return q['stdout'].decode().strip()


def state(cwd):
    out = {}
    for f in sorted(cwd.rglob('*')):
        if f.is_symlink(): data = ['symlink', os.fsencode(os.readlink(f)).hex()]
        elif f.is_file(): data = ['file', hashlib.sha256(f.read_bytes()).hexdigest()]
        elif f.is_dir(): data = ['directory']
        else: data = ['other']
        out[str(f.relative_to(cwd))] = [f.lstat().st_mode, *data]
    return out


def write(repo, path, data):
    p = repo / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data if isinstance(data, bytes) else data.encode())


def fans_out(hexes):
    groups = collections.Counter(h[0] for h in hexes)
    return len(groups) == 16 and min(groups.values()) >= 2


def base(repo):
    repo.mkdir(parents=True); g(repo, "init", "-q")
    write(repo, 'a.txt', 'alpha\n'); write(repo, 'b.txt', 'beta\n'); write(repo, 'dir/c.txt', 'gamma\n')
    g(repo, 'add', '.'); g(repo, 'commit', '-q', '-m', 'first subject\n\nbody line'); g(repo, 'tag', 'first')
    write(repo, 'b.txt', 'beta two\n'); g(repo, 'commit', '-qam', 'second subject')


def dirty(repo):
    base(repo)
    write(repo, 'a.txt', 'alpha changed\n'); write(repo, 'b.txt', 'beta staged\n'); g(repo, 'add', 'b.txt')
    write(repo, 'b.txt', 'beta staged then worktree\n'); write(repo, 'new.txt', 'added\n'); g(repo, 'add', 'new.txt')
    (repo / 'dir/c.txt').unlink(); write(repo, 'untracked', 'u\n')


def stashed(repo):
    base(repo)
    for n, (path, data) in enumerate([('a.txt', 'v0\n'), ('a.txt', 'v1\n'), ('b.txt', 'v2\n')]):
        write(repo, path, data); g(repo, 'stash', 'push', '-q', '-m', f'm{n}')


def noted(repo):
    base(repo)
    g(repo, 'notes', 'add', '-m', 'oracle note on head\n\nsecond paragraph', 'HEAD')
    g(repo, 'notes', 'add', '-m', 'blob note', 'HEAD:a.txt')


def fanned(repo):
    base(repo); hexes, extra, i = [], 10, 0
    while extra:
        h = g(repo, 'hash-object', '-w', '--stdin', data=f'fan {i}\n'.encode())
        g(repo, 'notes', 'add', '-m', f'fan note {i}', h); hexes.append(h); i += 1
        if fans_out(hexes): extra -= 1


def edge(repo):
    base(repo); hexes, i = [], 0
    while True:
        h = g(repo, 'hash-object', '-w', '--stdin', data=f'edge {i}\n'.encode()); hexes.append(h)
        if fans_out(hexes): break
        g(repo, 'notes', 'add', '-m', f'edge note {i}', h); i += 1
    (repo / '.git/crossing').write_text(hexes[-1])


def bad_notes(repo):
    base(repo)
    blob = g(repo, 'hash-object', '-w', '--stdin', data=b'readme\n')
    tree = g(repo, 'mktree', data=f'100644 blob {blob}\tREADME\n'.encode())
    commit = g(repo, 'commit-tree', tree, '-m', 'not a notes tree')
    g(repo, 'update-ref', 'refs/notes/commits', commit)


def raw_path(repo):
    base(repo)
    (repo / os.fsdecode(b'raw\xff')).write_bytes(b'raw\n'); g(repo, 'add', '.'); g(repo, 'commit', '-qm', 'raw')
    (repo / os.fsdecode(b'raw\xff')).write_bytes(b'raw changed\n')


FIXTURES = {'base': base, 'dirty': dirty, 'stashed': stashed, 'noted': noted, 'fanned': fanned,
            'edge': edge, 'bad-notes': bad_notes, 'raw-path': raw_path}
rows, failures = [], []
for mode in ('loose', 'packed'):
    source = root / f'fixtures-{mode}'
    for name, build in FIXTURES.items():
        build(source / name)
        if mode == 'packed':
            pack_fixture(G, source / name); g(source / name, 'pack-refs', '--all')

    def copy(name, label):
        target = root / f'{mode}-{label}'
        shutil.copytree(source / name, target, symlinks=True)
        return target

    def check(label, fixture, args, expected, mutation='none'):
        repo = copy(fixture, label)
        before = state(repo)
        actual = run(C, args, repo)
        after = state(repo)
        if mutation == 'objects':
            changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
            unchanged = all(k.startswith('.git/objects/') for k in changed) and all(k in after for k in before)
        else:
            unchanged = before == after
        ok = actual['status'] == 0 and actual['stderr'] == b'' and unchanged and (
            expected(actual['stdout']) if callable(expected) else actual['stdout'] == expected)
        rows.append(dict(mode=mode, label=label, args=args, stdout=actual['stdout'].hex(),
                         status=actual['status'], unchanged=unchanged, ok=ok))
        if not ok:
            failures.append([mode, label]); print('FAIL', mode, label, actual, flush=True)
        return actual['stdout']

    # Construction is separate from publication: the oracle's `stash create`
    # names the same W, and only new objects may appear in the client's copy.
    for label, extra in [('construct', []), ('construct-message', ['client message'])]:
        oracle = copy('dirty', label + '-oracle')
        w = g(oracle, 'stash', 'create', *extra)
        i = g(oracle, 'rev-parse', w + '^2'); h = g(oracle, 'rev-parse', w + '^1')
        check(label, 'dirty', ['construct', *extra], f'{w} {i} {h}\n'.encode(), 'objects')
    oracle = copy('base', 'construct-clean-oracle')
    assert run(G, ['stash', 'create'], oracle) == dict(status=1, stdout=b'', stderr=b'')
    check('construct-clean', 'base', ['construct'], b'unchanged\n')
    check('construct-raw-path', 'raw-path', ['construct'],
          lambda out: out.startswith(b'unsupported: ') and b'non-UTF-8' in out)
    # The durable list and the measured drop rewrite.
    oracle = copy('stashed', 'records-oracle')
    listed = g(oracle, 'log', '-g', '--format=%H %gs', 'refs/stash')
    check('records', 'stashed', ['records'], (listed + '\n').encode())
    for n in range(3):
        oracle = copy('stashed', f'without-{n}-oracle')
        g(oracle, 'stash', 'drop', '-q', f'stash@{{{n}}}')
        check(f'without-{n}', 'stashed', ['without', str(n)], (oracle / '.git/logs/refs/stash').read_bytes())
    # Notes read in any permitted fan-out, rewritten in the oracle's shape.
    for fixture, level in [('noted', 0), ('fanned', 1), ('edge', 0)]:
        oracle = copy(fixture, f'notes-{fixture}-oracle')
        listed = g(oracle, 'notes', 'list')
        check(f'notes-{fixture}', fixture, ['notes'], (listed + '\n').encode())
        tree = g(oracle, 'rev-parse', 'refs/notes/commits^{tree}')
        check(f'rewrite-{fixture}', fixture, ['rewrite'], f'{tree} {level}\n'.encode(), 'objects')
    oracle = copy('edge', 'cross-oracle')
    crossing = (oracle / '.git/crossing').read_text()
    blob = g(oracle, 'hash-object', '-w', '--stdin', data=b'client crossing\n')
    g(oracle, 'notes', 'add', '-C', blob, crossing)
    tree = g(oracle, 'rev-parse', 'refs/notes/commits^{tree}')

    def crossed(out, tree=tree):
        return out == f'{tree} 1\n'.encode()
    repo_blob = copy('edge', 'cross-blob')
    assert g(repo_blob, 'hash-object', '-w', '--stdin', data=b'client crossing\n') == blob
    check('rewrite-crossing', 'edge', ['rewrite', crossing, blob], lambda out: crossed(out), 'objects')
    # Display matches the oracle's default log block.
    for rev in ('HEAD', 'first'):
        oracle = copy('noted', f'display-{rev}-oracle')
        text = run(G, ['log', '-1', rev], oracle)['stdout']
        block = text[text.index(b'\nNotes:\n'):] if b'\nNotes:\n' in text else b''
        check(f'display-{rev}', 'noted', ['display', rev], block)
    check('limits', 'base', ['limits'], b'limits: 4 of 4 refused by name\n')
    check('bad-notes', 'bad-notes', ['notes'], b'unsupported: notes tree entry README\n')
summary = dict(rows=rows, failures=failures, zero_skips=True,
               counts={m: dict(exact=sum(r['ok'] for r in rows if r['mode'] == m),
                               total=sum(1 for r in rows if r['mode'] == m)) for m in ('loose', 'packed')})
(R / f'target/stash-api-{a.tier}.json').write_text(json.dumps(summary, indent=1) + '\n')
print('stash/notes client', json.dumps(summary['counts'], sort_keys=True), len(failures), 'failures', flush=True)
raise SystemExit(bool(failures))
