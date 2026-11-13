"""Embedded repositories: Git 2.56.0 black-box command and state rows.

Git's multi-line embedded-repository advice is deliberately reduced to its one
warning line. No other process bytes are normalized. Every capture retains the
complete processes and before/after file maps; index comparisons independently
use Git's parsed mode/oid/stage/path view, not stat-word byte identity.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import zlib

p = argparse.ArgumentParser()
p.add_argument('--tier', choices=('native', 'release'), default='native')
a = p.parse_args()
ROOT = Path(__file__).resolve().parent.parent
GIT = os.environ['DEN_GIT']
assert hashlib.sha256(Path(GIT).read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
DEN = str(ROOT / 'target' / a.tier / 'den')
PROOF = runpy.run_path(str(ROOT / 'tools/index-proof.py'))
REVIEW = json.loads((ROOT / 'tests/review/embedded.json').read_text())
OUT = ROOT / 'target/runs' / ('embedded-' + a.tier)
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
rows = []
failures = []


def process(exe, repo, args):
    q = subprocess.run([exe, *args], cwd=repo, capture_output=True)
    return dict(args=args, code=q.returncode, out=q.stdout.hex(), err=q.stderr.hex())


def git(repo, *args):
    q = process(GIT, repo, list(args))
    assert q['code'] == 0, q
    return bytes.fromhex(q['out'])


def state(repo):
    result = {}
    for f in sorted(repo.rglob('*')):
        if f.is_symlink():
            result[str(f.relative_to(repo))] = ['link', os.readlink(f)]
        elif f.is_file():
            result[str(f.relative_to(repo))] = [f.stat().st_mode & 0o777, f.read_bytes().hex()]
    return result


def fixture(name, nested='nested', kind='directory', siblings=False, ignored=''):
    repo = OUT / ('seed-' + name)
    repo.mkdir()
    git(repo, 'init', '-q')
    (repo / 'tracked').write_bytes(b'old\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-qm', 'base')
    (repo / 'tracked').write_bytes(b'new\n')
    (repo / 'other').write_bytes(b'other\n')
    names = [nested] + (['peer', 'deep/peer'] if siblings else [])
    for path in names:
        child = repo / path
        child.mkdir(parents=True)
        if kind == 'empty':
            (child / '.git').mkdir()
        else:
            git(child, 'init', '-q')
        (child / 'file').write_bytes(b'inside\n')
        if kind not in ('empty', 'unborn'):
            git(child, 'add', '.')
            git(child, 'commit', '-qm', 'inner')
        if kind == 'gitfile':
            # Keep the referenced store outside the scanned worktree.
            store = repo / '.git' / ('inner-' + path.replace('/', '-'))
            shutil.move(child / '.git', store)
            rel = os.path.relpath(store, child)
            (child / '.git').write_text('gitdir: ' + rel + '\n')
    if ignored:
        (repo / '.gitignore').write_text(ignored)
    return repo


def compare(name, seed, args, *, warning=False, readonly=False, failed=False, refusal=''):
    pair = []
    states = []
    for label, exe in [('git', GIT), ('den', DEN)]:
        repo = OUT / (name + '-' + label)
        shutil.copytree(seed, repo)
        before = state(repo)
        q = process(exe, repo, args)
        after = state(repo)
        pair.append(q)
        states.append((before, after))
        q['before'] = before
        q['after'] = after
        q['index'] = git(repo, 'ls-files', '--stage').hex()
        q['head'] = git(repo, 'rev-parse', 'HEAD').hex()
        index = repo / '.git/index'
        q['index_proof'] = PROOF['proof'](repo, index.read_bytes()) if index.exists() else []
    row = dict(name=name, processes=pair)
    rows.append(row)
    try:
        left, right = pair
        if refusal:
            assert right['code'] != 0 and refusal.encode() in bytes.fromhex(right['err']), right
            assert states[1][0] == states[1][1], 'named refusal changed files'
            print('PASS ' + name + ' named-refusal', flush=True)
            return
        assert left['code'] == right['code'], (left['code'], right['code'])
        assert left['out'] == right['out'], ('stdout', bytes.fromhex(left['out']), bytes.fromhex(right['out']))
        if warning:
            binding = REVIEW['rows'][name]
            assert {key: left[key] for key in ('args', 'code', 'out', 'err')} == {key: binding[key] for key in ('args', 'code', 'out', 'err')}, 'reviewed Git command/result changed'
            assert right['err'] == binding['den_err'], 'reviewed den warning changed'
            row['review'] = REVIEW['name']
        else:
            assert left['err'] == right['err'], ('stderr', bytes.fromhex(left['err']), bytes.fromhex(right['err']))
        assert left['index'] == right['index'], 'parsed index mode/oid/stage/path'
        assert left['head'] == right['head'], 'HEAD identity'
        if readonly:
            for before, after in states:
                assert before == after, 'read-only operation changed files'
        if failed:
            assert states[1][0] == states[1][1], 'failed den add changed files'
            before, after = states[0]
            added = {k: v for k, v in after.items() if k not in before}
            changed = {k for k in before if before[k] != after.get(k)}
            assert not changed, 'failed Git add changed an existing file'
            if name in REVIEW['unborn_preflight']['rows']:
                assert added == REVIEW['unborn_preflight']['git_added'], 'unborn preflight review changed'
                row['review'] = REVIEW['unborn_preflight']['name']
            else:
                assert not added, 'failed/no-op Git add added a file'
        aa, bb = (dict(q['after']) for q in pair)
        if name in REVIEW['unborn_preflight']['rows']:
            for path in REVIEW['unborn_preflight']['git_added']:
                del aa[path]
        # Only the previously adopted six own-lstat-proven index words and
        # loose-object compression can differ. Every other file/mode is exact.
        if '.git/index' in aa and '.git/index' in bb:
            x, y, count = PROOF['canonical_pair'](
                bytes.fromhex(aa['.git/index'][1]), bytes.fromhex(bb['.git/index'][1]),
                left['index_proof'], right['index_proof'])
            aa['.git/index'] = [aa['.git/index'][0], x.hex()]
            bb['.git/index'] = [bb['.git/index'][0], y.hex()]
            row['proven_stat_words'] = count
        for files in (aa, bb):
            for path, value in files.items():
                parts = path.split('/')
                if len(parts) == 4 and parts[:2] == ['.git', 'objects'] and len(parts[2]) == 2 and len(parts[3]) == 38:
                    raw = zlib.decompress(bytes.fromhex(value[1]))
                    assert hashlib.sha1(raw).hexdigest() == parts[2] + parts[3], 'loose object identity'
                    files[path] = [value[0], raw.hex()]
        assert aa == bb, 'complete resulting file bytes/modes differ'
        # Neither command is ever allowed to touch a nested repository's files.
        for before, after in states:
            inner = lambda x: {k: v for k, v in x.items() if '/.git/' in k or k.endswith('/.git') or k.endswith('/file') or k.startswith('.git/inner-')}
            assert inner(before) == inner(after), 'embedded repository changed'
        print('PASS ' + name, flush=True)
    except AssertionError as e:
        failures.append(name)
        row['failure'] = str(e)
        print('FAIL ' + name + ' ' + str(e), flush=True)
    finally:
        for label in ('git', 'den'):
            shutil.rmtree(OUT / (name + '-' + label))


formats = [[], ['--short'], ['--porcelain=v1'], ['--porcelain=v2'], ['--short', '-z'], ['--porcelain=v2', '-z']]
for kind in ('directory', 'gitfile', 'unborn', 'empty'):
    seed = fixture(kind, kind=kind)
    for n, fmt in enumerate(formats):
        for mode in ('normal', 'all', 'no'):
            compare('embedded-status-' + kind + '-' + str(n) + '-' + mode, seed,
                    ['status', *fmt, '--untracked-files=' + mode], readonly=True)
    for n, args in enumerate([['diff'], ['diff', '--cached'], ['add', 'other'], ['add', '-u'], ['commit', '-am', 'outer']]):
        compare('embedded-other-' + kind + '-' + str(n), seed, args, readonly=args[0] == 'diff')
    for n, args in enumerate([['add', '.'], ['add', '-A'], ['add', 'nested'], ['add', 'nested/file']]):
        compare('embedded-add-' + kind + '-' + str(n), seed, args,
                warning=kind in ('directory', 'gitfile') and n < 3,
                failed=kind == 'unborn' and n < 3 or n == 3 and kind != 'empty')

for name, nested, siblings, ignored in [
    ('deep', 'test/integration/checkouts/acme/alpha', False, ''),
    ('siblings', 'nested', True, ''),
    ('wrapper', 'wrapper/nested', False, ''),
    ('ignored', 'nested', False, 'nested/\n'),
    ('ignore-child', 'nested', False, 'nested/file\n'),
    ('nested-ignore', 'wrapper/nested', False, 'wrapper/nested/\n'),
]:
    seed = fixture(name, nested=nested, siblings=siblings, ignored=ignored)
    for n, fmt in enumerate(formats):
        for mode in ('normal', 'all', 'no'):
            compare('embedded-status-' + name + '-' + str(n) + '-' + mode, seed,
                    ['status', *fmt, '--untracked-files=' + mode], readonly=True)
    compare('embedded-bulk-' + name, seed, ['add', '-A'], warning=name not in ('ignored', 'nested-ignore'))

# A newly authored gitlink is consumed by the existing vc25 command paths.
seed = fixture('consumers')
git(seed, '-c', 'advice.addEmbeddedRepo=false', 'add', 'nested')
for n, args in enumerate([
    ['status', '--porcelain=v2'], ['diff', '--cached'], ['commit', '-m', 'embedded'],
    ['add', 'nested/file'], ['rm', '-f', '--cached', 'nested'],
    ['mv', 'nested', 'moved'], ['restore', '--staged', 'nested'],
]):
    compare('embedded-consumer-' + str(n), seed, args, readonly=args[0] in ('status', 'diff'),
            refusal='submodule move' if args[0] == 'mv' else 'status --porcelain=v2 of a submodule' if n == 0 else '')

(OUT / 'captures.json').write_text(json.dumps(rows, indent=2) + '\n')
(OUT / 'summary.json').write_text(json.dumps(dict(total=len(rows), failures=failures, skips=0), indent=2) + '\n')
print('embedded: rows=' + str(len(rows)) + ' failures=' + str(len(failures)) + ' skips=0', flush=True)
raise SystemExit(bool(failures))
