"""Ref command bytes and complete repository state against pinned Git."""
import argparse, json, os, pathlib, runpy, shutil, subprocess
R = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(); ap.add_argument('--tier', default='native'); a = ap.parse_args()
G = os.environ['DEN_GIT']; D = str(R / f'target/{a.tier}/den')
O = runpy.run_path(str(R / 'tools/oracle.py'))
mode = a.tier + ('-packed' if os.environ.get('DEN_PACKED_FIXTURES') == '1' else '')
pack_fixture = runpy.run_path(str(R / 'tools/packed-fixture.py'))['pack_fixture']
base = R / f'target/refs-oracle-{mode}'
if base.exists(): shutil.rmtree(base)
base.mkdir(parents=True)
seed = base / 'seed'; seed.mkdir()
def git(*args):
    p = subprocess.run([G, *args], cwd=seed, capture_output=True)
    assert p.returncode == 0, (args, p.stdout, p.stderr)
    return p.stdout.decode().strip()
git('init', '-q')
(seed / 'a').write_bytes(b'one\n'); git('add', 'a'); git('commit', '-qm', 'one')
first = git('rev-parse', 'HEAD')
git('branch', 'topic')
(seed / 'a').write_bytes(b'two\n'); git('commit', '-qam', 'two')
second = git('rev-parse', 'HEAD')
git('tag', 'light', first); git('tag', '-am', 'annotation', 'annotated', first)
tree = git('rev-parse', 'HEAD^{tree}'); blob = git('rev-parse', 'HEAD:a')
dated = subprocess.check_output([G, 'commit-tree', tree, '-m', 'first line\nsecond line'], cwd=seed,
    env=dict(os.environ, GIT_AUTHOR_DATE='946684800 +1400', GIT_COMMITTER_DATE='978307200 -1200')).decode().strip()
if mode.endswith('-packed'): pack_fixture(G, seed)
cases = []
commands = [
 ['branch'], ['branch', '--show-current'], ['branch', '--list', 'topic'],
 ['branch', 'new'], ['branch', 'new', 'HEAD'], ['branch', 'new', 'main'],
 ['branch', 'new', 'refs/heads/topic'], ['branch', 'new', 'light'],
 ['branch', 'new', 'annotated'], ['branch', 'new', first], ['branch', 'new', first[:8]],
 ['branch', '-f', 'topic', second], ['branch', '-f', 'topic', first],
 ['branch', '-d', 'topic'], ['branch', '-D', 'topic'], ['branch', '-q', '-d', 'topic'],
 ['branch', '-d', 'absent'], ['branch', '-D', 'main'], ['branch', '-f', 'main'],
 ['branch', 'topic'], ['branch', 'new', 'absent'],
 ['branch', 'nested/topic'], ['branch', 'a./b'], ['branch', 'é'],
 ['tag'], ['tag', '--list', 'light'], ['tag', 'new'], ['tag', 'new', 'light'],
 ['tag', '-a', '-m', 'annotation', 'new'], ['tag', '-m', 'one', '-m', 'two', 'new'],
 ['tag', '-a', '-m', '', 'new'], ['tag', '-m', ' #comment\nbody\n', 'new'],
 ['tag', '--cleanup=verbatim', '-m', '  body  ', 'new'],
 ['tag', '-f', 'light', second], ['tag', '-f', 'light', first],
 ['tag', '-f', '-m', 'replacement', 'light'],
 ['tag', '-d', 'light'], ['tag', '-d', 'annotated'], ['tag', '-d', 'absent'],
 ['tag', 'light'], ['tag', 'new', 'absent'], ['tag', 'nested/new'],
 ['branch', '-m', 'topic', 'other'], ['branch', '-m', 'main', 'other'],
 ['branch', '-m', 'other'], ['branch', '-M', 'topic', 'main'],
 ['branch', '-m', 'topic', 'main'], ['branch', '-m', 'absent', 'new'],
 ['branch', '-m', 'topic', 'topic'],
 ['switch', 'topic'], ['switch', 'main'], ['switch', '--detach', first],
 ['switch', '-q', '--detach', first], ['switch', '-c', 'new'],
 ['switch', '-c', 'new', first], ['checkout', 'topic'], ['checkout', '-b', 'new'],
 ['checkout', '-q', '--detach', first],
 ['reset', '--soft', first], ['reset', '--mixed', first], ['reset', '--hard', first],
 ['reset', '--soft'], ['reset', '--mixed'], ['reset', '--hard'],
 ['tag', '--create-reflog', 'new'], ['tag', '--create-reflog', '-m', 'annotation', 'new'],
 ['tag', '--create-reflog', 'new', tree], ['tag', '--create-reflog', 'new', blob],
 ['tag', '--create-reflog', 'new', 'annotated'],
 ['tag', '--create-reflog', '-m', 'nested', 'new', 'annotated'],
 ['tag', '--create-reflog', 'new', dated],
 ['checkout', '--detach', first], ['checkout', first],
 ['commit', '--allow-empty', '-m', 'third'], ['commit', '--amend', '-m', 'amended'],
 ['commit', '--amend', '--no-edit'],
 ['switch', '-C', 'topic', first], ['switch', '-C', 'main', first],
 ['checkout', '-B', 'topic', first], ['switch', '-f', 'topic'],
]
for expression in ['HEAD~1', 'HEAD^', 'annotated^0', 'HEAD^{commit}', 'HEAD@{0}', 'heads/topic']:
    commands.extend([['branch', 'grammar', expression], ['tag', 'grammar', expression],
                     ['reset', '--soft', expression], ['reset', '--mixed', expression],
                     ['reset', '--hard', expression], ['switch', '--detach', expression],
                     ['checkout', '--detach', expression], ['restore', '--source='+expression, '--', 'a']])
for packed in (False, True):
    for detached in (False, True):
        for i, command in enumerate(commands):
            cases.append(dict(name=f'{int(packed)}-{int(detached)}-{i}', args=command, packed=packed, detached=detached))
rows = []
for setup in ('dirty', 'staged', 'unborn', 'index.lock', 'HEAD.lock', 'refs/heads/main.lock', 'packed-refs.lock', 'MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD'):
    for i, command in enumerate([
        ['branch'], ['branch', '--show-current'], ['branch', 'new'], ['branch', '-m', 'new'],
        ['tag', 'new'], ['tag', '-m', 'annotation', 'new'],
        ['switch', 'topic'], ['switch', '-c', 'new'],
        ['reset', '--soft', first], ['reset', '--mixed', first], ['reset', '--hard', first],
    ]):
        cases.append(dict(name=f'extra-{setup.replace("/", "-")}-{i}', args=command, packed=False, detached=False, setup=setup))
for packed in (False, True):
    for force_delete in (False, True):
        cases.append(dict(name=f'divergent-{int(packed)}-{int(force_delete)}', args=['branch', '-D' if force_delete else '-d', 'topic'], packed=packed, detached=False, setup='diverged'))
for packed in (False, True):
    for command in [['switch', '@{-1}'], ['checkout', '@{-1}'], ['switch', '--detach', '@{-1}']]:
        cases.append(dict(name='previous-'+str(int(packed))+'-'+str(len(cases)), args=command, packed=packed, detached=False, setup='previous'))
for case in cases:
    root = base / case['name']; root.mkdir(); repo = root / 'repo'
    fixture = root / 'fixture'
    shutil.copytree(seed, fixture, symlinks=True)
    if case['packed']:
        subprocess.run([G, 'pack-refs', '--all'], cwd=fixture, check=True, capture_output=True)
    if case['detached']:
        subprocess.run([G, 'switch', '--detach', '-q', second], cwd=fixture, check=True, capture_output=True)
    setup = case.get('setup', '')
    if setup == 'previous':
        for branch in ['topic', 'main']:
            subprocess.run([G, 'switch', '-q', branch], cwd=fixture, check=True, capture_output=True)
    elif setup == 'diverged':
        subprocess.run([G, 'update-ref', 'refs/heads/topic', dated], cwd=fixture, check=True, capture_output=True)
    elif setup == 'dirty' or setup == 'staged':
        (fixture / 'a').write_bytes(b'local change\n')
        if setup == 'staged':
            subprocess.run([G, 'add', 'a'], cwd=fixture, check=True, capture_output=True)
    elif setup == 'unborn':
        # Keep the objects available, but make HEAD genuinely unborn with no index.
        (fixture / '.git/refs/heads/main').unlink()
        (fixture / '.git/index').unlink()
        shutil.rmtree(fixture / '.git/logs')
    elif setup in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD'):
        (fixture / '.git' / setup).write_bytes((first + '\n').encode())
    elif setup:
        p = fixture / '.git' / setup
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'foreign lock\n')
    if mode.endswith('-packed'): pack_fixture(G, fixture)
    def restore():
        if repo.exists(): shutil.rmtree(repo)
        shutil.copytree(fixture, repo, symlinks=True)
    restore(); expected = O['capture']([G, *case['args']], repo, index_proof=True)
    restore(); actual = O['capture']([D, *case['args']], repo, index_proof=True)
    good = O['equivalent'](expected, actual, 'index-stat-proven')
    rows.append(dict(case=case, git=expected, den=actual, equal=good))
    print(('parity' if good else 'FAIL') + ': ' + case['name'], flush=True)
    if not good:
        print(' git', expected['status'], bytes.fromhex(expected['stdout']), bytes.fromhex(expected['stderr']))
        print(' den', actual['status'], bytes.fromhex(actual['stdout']), bytes.fromhex(actual['stderr']))
(R / f'target/refs-oracle-{mode}.json').write_text(json.dumps(rows, indent=2) + '\n')
failed = sum(not row['equal'] for row in rows)
print(f'refs: {len(rows)-failed}/{len(rows)} exact; {failed} mismatches', flush=True)
unsupported = []
for i, (args, feature) in enumerate([
    (['branch', '--list', '*'], 'branch list patterns'),
    (['tag', '--list', '*'], 'tag list patterns'),
    (['branch', '--track', 'new'], 'branch --track'),
    (['tag', '--sort=version:refname'], 'tag --sort=version:refname'),
    (['switch', '--orphan', 'new'], 'switch --orphan'),
    (['checkout', '-m', 'topic'], 'checkout -m'),
    (['reset', '--merge', 'HEAD'], 'reset --merge'),
    *[(args, 'revision set in single-object consumer') for args in (
        ['branch','grammar','main..HEAD'], ['tag','grammar','main..HEAD'],
        ['reset','--soft','main..HEAD'], ['switch','--detach','main..HEAD'],
        ['checkout','--detach','main..HEAD'], ['merge','--no-edit','main..HEAD'],
        ['revert','--no-edit','main..HEAD'], ['cherry-pick','main..HEAD'],
        ['rebase','main..HEAD'], ['restore','--source=main..HEAD','--','a'])],
]):
    repo = base / f'unsupported-{i}'
    shutil.copytree(seed, repo)
    expected = O['capture']([G, *args], repo)
    shutil.rmtree(repo); shutil.copytree(seed, repo)
    before = O['snapshot'](repo); work = O['worktree_snapshot'](repo)
    actual = O['capture']([D, *args], repo)
    assert actual['status'] == 2 and actual['stdout'] == '' and bytes.fromhex(actual['stderr']) == f'den: not yet implemented: {feature}\n'.encode(), (args, actual)
    assert actual['repository'] == before and actual['worktree'] == work, args
    unsupported.append(dict(args=args, feature=feature, git=expected, den=actual))
(R / f'target/refs-unsupported-{mode}.json').write_text(json.dumps(unsupported, indent=2) + '\n')
print(f'refs named unsupported: {len(unsupported)}; not parity', flush=True)
raise SystemExit(bool(failed))
