#!/usr/bin/env python3
"""Remove only completed generated fixtures, preserving evidence at its path."""
import getpass
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys

if sys.platform.startswith('linux'):
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
target = Path(sys.argv[1]).resolve()
leaf = sys.argv[2]
assert target.name == 'target' and (target.parent / 'src/den.lu').is_file()
fixed = {
 'tools/check-housekeeping': ['housekeeping-native-final','housekeeping-release-final'],
 'tools/check-blame': ['blame-native','blame-release'],
 'tools/check-refs': ['refs-oracle-native','refs-oracle-release'],
 'tools/check-merge': ['merge-native','merge-release'],
 'tools/check-replay': ['replay-native','replay-release'],
 'tools/check-pack': ['refs-oracle-native-packed','refs-oracle-release-packed',
                     'merge-native-packed','merge-release-packed','replay-native-packed',
                     'replay-release-packed','history-native-packed','history-release-packed',
                     'pack-native','pack-release'],
 'tools/check-pack-write': ['pack-write-native','pack-write-release','pack-failure-native',
                           'pack-failure-release','pack-adversarial-native','pack-adversarial-release',
                           'pack-interop-native','pack-interop-release','stash-native','stash-release'],
}
paths = [target / name for name in fixed.get(leaf, [])]
if leaf == 'tools/check-stash':
    for tier in ['native','release']:
        root = target / ('stash-' + tier)
        if root.exists():
            paths.extend(p for p in root.iterdir() if p.is_dir() and p.name != 'fixtures')
post_pack = leaf in ('tools/check-pack', 'tools/check-pack-write') or (target.parent.parent / 'packed-read.finished').exists()
if post_pack:
    # All later component gates build their own clients; corpus-only diff also
    # builds its clients. The unchanged den programs are the only carry-over.
    for tier in ['native','release']:
        root = target / tier
        if root.exists():
            paths.extend(p for p in root.iterdir() if p.name != 'den')
if not post_pack:
    # Standalone unit programs are not consumed by later gates. Keep clients
    # until packed-read has completed its inherited importing-client rows.
    for tier in ['native','release']:
        root = target / tier
        if root.exists():
            paths.extend(p for p in root.iterdir() if p.is_file() and p.name.endswith('-test'))
paths = [p for p in paths if p.exists() or p.is_symlink()]
if not paths:
    if leaf == 'tools/check-pack': (target.parent.parent / 'packed-read.finished').write_text('passed\n')
    raise SystemExit(0)
for p in paths:
    assert p.is_relative_to(target) and p != target
opened = subprocess.run(['lsof','-nP','-u',getpass.getuser(),'-Fn'], capture_output=True, text=True)
assert opened.returncode in (0,1), opened.stderr
for line in opened.stdout.splitlines():
    if not line.startswith('n'):
        continue
    name = line[1:]
    assert not any(name == str(p) or name.startswith(str(p) + '/') for p in paths), 'open workspace file: ' + name

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(1024*1024), b''):
            h.update(data)
    return h.hexdigest()

protected = {}
for p in paths:
    files = p.rglob('*') if p.is_dir() and not p.is_symlink() else [p]
    for f in files:
        if f.is_file() and not f.is_symlink() and f.suffix in {'.json','.log','.record'}:
            protected[str(f)] = digest(f)
for path in paths:
    if path.is_symlink() or path.is_file():
        if str(path) not in protected:
            path.unlink()
        continue
    for current, dirs, files in os.walk(path, topdown=False, followlinks=False):
        here = Path(current)
        for name in files:
            p = here / name
            if str(p) not in protected:
                p.unlink()
        for name in dirs:
            p = here / name
            if p.is_symlink():
                p.unlink()
            else:
                try: p.rmdir()
                except OSError: pass
    try: path.rmdir()
    except OSError: pass
for name, expected in protected.items():
    assert digest(Path(name)) == expected, name
entry = dict(leaf=leaf, finished_paths=[str(p) for p in paths], preserved_text_files=len(protected))
with (target.parent.parent / 'prune-events.jsonl').open('a') as out:
    out.write(json.dumps(entry) + '\n')
if leaf == 'tools/check-pack': (target.parent.parent / 'packed-read.finished').write_text('passed\n')
print('PRUNE finished-only ' + json.dumps(entry), flush=True)
