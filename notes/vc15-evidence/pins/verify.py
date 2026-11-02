"""Verify unchanged pin metadata, whole archives, staged payloads and std twice."""
import argparse
import hashlib
import json
import pathlib
import tarfile
import tomllib

parser = argparse.ArgumentParser()
parser.add_argument('--archives', type=pathlib.Path, required=True)
parser.add_argument('--staged', type=pathlib.Path, required=True)
parser.add_argument('--oracle', type=pathlib.Path, required=True)
parser.add_argument('--target', default='x86_64-unknown-linux-gnu')
parser.add_argument('--prefix', default='')
args = parser.parse_args()
root = pathlib.Path(__file__).resolve().parents[3]
metadata = pathlib.Path(__file__).resolve().parent
pin = tomllib.loads((root / 'wolf-toolchain.toml').read_text())
target = args.target
summary = {}
for repo, tool in [('wolf-lang', 'wolf'), ('wolf-interp', 'lupin')]:
    version = pin[tool]['version']
    filename = f'{tool}-{version}-{target}.tar.gz'
    archive_path = args.archives / tool / filename
    asset_ids = []
    for n in (1, 2):
        release = json.loads((metadata / f'{repo}-release-{n}.json').read_text())
        asset = next(x for x in release['assets'] if x['name'] == filename)
        assert asset['digest'] == 'sha256:' + pin[tool][target]
        asset_ids.append((asset['id'], asset['name'], asset['digest']))
        assert hashlib.sha256(archive_path.read_bytes()).hexdigest() == pin[tool][target]
    assert asset_ids[0] == asset_ids[1]
    for kind in ('ref', 'tag'):
        first = json.loads((metadata / f'{repo}-{kind}-1.json').read_text())
        second = json.loads((metadata / f'{repo}-{kind}-2.json').read_text())
        assert first == second
    tag = json.loads((metadata / f'{repo}-tag-1.json').read_text())
    ref = json.loads((metadata / f'{repo}-ref-1.json').read_text())
    assert tag['sha'] == ref['object']['sha']
    assert tag['object']['sha'] == pin[tool]['rev']
    with tarfile.open(archive_path) as archive:
        members = [m for m in archive if m.isfile()]
        member = next(m for m in members if m.name.endswith('/' + tool))
        archive_hash = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
        assert archive_hash == hashlib.sha256((args.staged / tool).read_bytes()).hexdigest()
        if tool == 'wolf':
            runtime = next(m for m in members if m.name.endswith('/libwolf_rt.a'))
            assert hashlib.sha256(archive.extractfile(runtime).read()).digest() == hashlib.sha256((args.staged / 'libwolf_rt.a').read_bytes()).digest()
    summary[tool] = dict(asset=asset_ids[0], executable_sha256=archive_hash, rev=tag['object']['sha'])
std_revision = (args.staged / 'std' / 'STD-REV').read_text().strip()
assert std_revision == pin['std']['rev']
with tarfile.open(args.archives / 'std' / 'std.tar') as archive:
    expected = {m.name[4:]: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                for m in archive if m.isfile() and m.name.startswith('std/')}
actual = {}
for path in sorted((args.staged / 'std').rglob('*')):
    assert not path.is_symlink(), path
    if path.is_file() and path.name != 'STD-REV':
        actual[str(path.relative_to(args.staged / 'std'))] = hashlib.sha256(path.read_bytes()).hexdigest()
assert actual == expected, (sorted(set(actual) - set(expected)), sorted(set(expected) - set(actual)))
for n in (1, 2):
    files = sorted(p for p in args.staged.rglob('*') if p.is_file())
    assert not any(p.is_symlink() for p in files)
    manifest = {str(p.relative_to(args.staged)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    manifest['oracle'] = hashlib.sha256(args.oracle.read_bytes()).hexdigest()
    assert manifest['oracle'] == tomllib.loads((root / 'den-oracle.toml').read_text())['oracle']['binary_sha256']
    (metadata / f'{args.prefix}staged-{n}.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
assert (metadata / f'{args.prefix}staged-1.json').read_bytes() == (metadata / f'{args.prefix}staged-2.json').read_bytes()
summary['std'] = dict(rev=std_revision, files=len(actual))
(metadata / f'{args.prefix}summary.json').write_text(json.dumps(summary, sort_keys=True, indent=2) + '\n')
print('VC15 PINS VERIFIED: twice-read metadata/archives/staged payloads; complete std matches pinned tree; unchanged oracle')
