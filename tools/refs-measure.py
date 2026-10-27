"""Pinned executable measurements only; no VCS implementation source."""
import json, os, pathlib, shutil, subprocess
R = pathlib.Path(__file__).resolve().parent.parent
base = R / 'target/vc06-measure'
base.mkdir(parents=True, exist_ok=True)
repo = base / 'repo'
if repo.exists():
    shutil.rmtree(repo)
repo.mkdir()
git = os.environ.get('DEN_GIT', '/opt/git/bin/git')
rows = []
def command(*args, check=True):
    p = subprocess.run([git, *args], cwd=repo, capture_output=True)
    rows.append({'args': args, 'status': p.returncode, 'out': p.stdout.hex(), 'err': p.stderr.hex()})
    if check and p.returncode:
        raise RuntimeError(rows[-1])
    return p.stdout.decode().strip()
def state(label):
    files = {}
    for p in sorted((repo / '.git').rglob('*')):
        if p.is_file() and 'objects' not in p.relative_to(repo / '.git').parts:
            files[str(p.relative_to(repo))] = p.read_bytes().hex()
    rows.append({'state': label, 'files': files})
command('init', '-q')
state('unborn')
command('branch')
command('branch', 'topic', check=False)
(repo / 'a').write_text('first\n')
command('add', 'a')
command('commit', '-qm', 'first')
first = command('rev-parse', 'HEAD')
command('branch', 'topic')
command('tag', 'light')
command('tag', '-am', 'annotation', 'annotated')
command('pack-refs', '--all')
state('packed')
command('branch', '-m', 'topic', 'other')
state('renamed-packed')
command('branch', '-f', 'other', 'HEAD')
state('same-id-forced')
command('branch', '-d', 'other')
state('deleted-packed')
command('switch', '--detach', first)
state('detached')
command('branch')
command('switch', 'main')
(repo / 'a').write_text('second\n')
command('commit', '-qam', 'second')
command('reset', '--soft', first)
state('soft')
command('reset', '--mixed', first)
state('mixed')
(repo / '.git/refs/heads/main.lock').write_text('foreign')
command('reset', '--hard', first, check=False)
state('hard-foreign-lock')
(repo / '.git/refs/heads/main.lock').unlink()
command('reset', '--hard', first)
state('hard')
output = R / 'notes/vc06-evidence/oracle-measure.json'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(rows, indent=2) + '\n')
for row in rows:
    if 'args' in row:
        print(row['args'], row['status'], bytes.fromhex(row['out']), bytes.fromhex(row['err']), flush=True)
    else:
        print('STATE', row['state'])
        for path, data in row['files'].items():
            if '/logs/' in path or path.endswith('packed-refs'):
                print(path, bytes.fromhex(data))
