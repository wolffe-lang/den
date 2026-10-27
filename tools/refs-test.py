"""Ref command bytes and complete repository state against pinned Git."""
import argparse, json, os, pathlib, runpy, shutil, subprocess
R = pathlib.Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser(); ap.add_argument('--tier', default='native'); a = ap.parse_args()
G = os.environ['DEN_GIT']; D = str(R / f'target/{a.tier}/den')
O = runpy.run_path(str(R / 'tools/oracle.py'))
base = R / f'target/refs-oracle-{a.tier}'
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
]
for packed in (False, True):
    for detached in (False, True):
        for i, command in enumerate(commands):
            cases.append(dict(name=f'{int(packed)}-{int(detached)}-{i}', args=command, packed=packed, detached=detached))
rows = []
for case in cases:
    root = base / case['name']; root.mkdir(); repo = root / 'repo'
    fixture = root / 'fixture'
    shutil.copytree(seed, fixture, symlinks=True)
    if case['packed']:
        subprocess.run([G, 'pack-refs', '--all'], cwd=fixture, check=True, capture_output=True)
    if case['detached']:
        subprocess.run([G, 'switch', '--detach', '-q', second], cwd=fixture, check=True, capture_output=True)
    def restore():
        if repo.exists(): shutil.rmtree(repo)
        shutil.copytree(fixture, repo, symlinks=True)
    restore(); expected = O['capture']([G, *case['args']], repo)
    restore(); actual = O['capture']([D, *case['args']], repo)
    good = O['equivalent'](expected, actual)
    rows.append(dict(case=case, git=expected, den=actual, equal=good))
    print(('parity' if good else 'FAIL') + ': ' + case['name'], flush=True)
    if not good:
        print(' git', expected['status'], bytes.fromhex(expected['stdout']), bytes.fromhex(expected['stderr']))
        print(' den', actual['status'], bytes.fromhex(actual['stdout']), bytes.fromhex(actual['stderr']))
(R / f'target/refs-oracle-{a.tier}.json').write_text(json.dumps(rows, indent=2) + '\n')
failed = sum(not row['equal'] for row in rows)
print(f'refs: {len(rows)-failed}/{len(rows)} exact; {failed} mismatches', flush=True)
raise SystemExit(bool(failed))
