#!/usr/bin/env python3
"""Install/control an owned, CPU-reserved pinned-Git SSH fixture endpoint."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

PIN = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'


def install(root, git, slot):
    root, git = root.resolve(), git.resolve()
    assert root.is_relative_to(Path.home() / 'lanes/vc16'), root
    assert slot in ('4-7', '8-11')
    assert hashlib.sha256(git.read_bytes()).hexdigest() == PIN
    root.mkdir(parents=True, exist_ok=True)
    for name in ('bin', 'home', 'empty-template', 'empty-hooks', 'repos', 'tmp'):
        (root / name).mkdir(exist_ok=True)
    (root / 'peer.json').write_text(json.dumps(dict(git=str(git), slot=slot)) + '\n')
    (root / 'gitconfig').write_text('[user]\n\tname = Den Tester\n\temail = den@example.invalid\n[core]\n\thooksPath = ' + str(root / 'empty-hooks') + '\n[init]\n\tdefaultBranch = main\n\ttemplateDir = ' + str(root / 'empty-template') + '\n')
    shutil.copyfile(__file__, root / 'control.py')
    fixed = dict(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=str(root / 'gitconfig'),
                 GIT_EXEC_PATH=str(git.parent.parent / 'libexec/git-core'),
                 GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
                 GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid',
                 GIT_AUTHOR_DATE='1700000000 +0000', GIT_COMMITTER_DATE='1700000000 +0000',
                 HOME=str(root / 'home'), TMPDIR=str(root / 'tmp'), LC_ALL='C', TZ='UTC',
                 PATH=str(git.parent) + ':/usr/bin:/bin')
    prelude = '#!/usr/bin/env bash\nset -eu\n'
    for name, service, v2 in (('upload', 'git-upload-pack', True), ('receive', 'git-receive-pack', True), ('upload-v0', 'git-upload-pack', False)):
        program = git.parent / service
        assert program.exists()
        text = prelude + ('export GIT_PROTOCOL=version=2\n' if v2 else 'unset GIT_PROTOCOL\n')
        assignments = dict(fixed)
        if v2:
            assignments['GIT_PROTOCOL'] = 'version=2'
        text += 'exec env -i ' + ' '.join(shlex.quote(k + '=' + v) for k, v in assignments.items())
        text += ' taskset -c ' + shlex.quote(slot) + ' ' + shlex.quote(str(program)) + ' "$@"\n'
        path = root / 'bin' / name
        path.write_text(text)
        path.chmod(0o755)
    holder = root / 'hold.py'
    holder.write_text('import json,sys\nprint(json.dumps({"ready": True}),flush=True)\nwhile sys.stdin.buffer.read(4096):\n pass\n')
    reserve = '#!/usr/bin/env bash\nset -eu\nexport TMPDIR=' + shlex.quote(str(root / 'tmp')) + '\n'
    reserve += 'exec flock -w 21600 ' + shlex.quote(str(Path.home() / ('lanes/kasumi-cores-' + slot + '.lock'))) + ' timeout --foreground 7000 taskset -c ' + slot + ' python3 -I ' + shlex.quote(str(holder)) + '\n'
    path = root / 'bin/reserve'
    path.write_text(reserve)
    path.chmod(0o755)
    print(json.dumps(dict(root=str(root), slot=slot, control_sha256=hashlib.sha256((root / 'control.py').read_bytes()).hexdigest())))


def control():
    root = Path(__file__).resolve().parent
    assert root.is_relative_to(Path.home() / 'lanes/vc16'), root
    config = json.loads((root / 'peer.json').read_text())
    git, slot = Path(config['git']), config['slot']
    assert slot in ('4-7', '8-11') and hashlib.sha256(git.read_bytes()).hexdigest() == PIN
    env = dict(PATH=str(git.parent) + ':/usr/bin:/bin')
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=str(root / 'gitconfig'),
               GIT_EXEC_PATH=str(git.parent.parent / 'libexec/git-core'),
               GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
               GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid',
               GIT_AUTHOR_DATE='1700000000 +0000', GIT_COMMITTER_DATE='1700000000 +0000',
               HOME=str(root / 'home'), TMPDIR=str(root / 'tmp'), LC_ALL='C', TZ='UTC')
    request = json.load(sys.stdin)
    if request['op'] == 'hello':
        return dict(root=str(root), slot=slot, git_sha256=PIN, control_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                    upload=str(root / 'bin/upload'), receive=str(root / 'bin/receive'), v0=str(root / 'bin/upload-v0'))
    relative = Path(request['repo'])
    assert not relative.is_absolute() and '..' not in relative.parts and relative.parts
    repo = (root / 'repos' / relative).resolve()
    assert repo.is_relative_to(root / 'repos') and repo != root / 'repos'
    def run(*args, data=b''):
        argv = ['taskset', '-c', slot, str(git), *map(str, args)]
        p = subprocess.run(argv, cwd=repo if repo.exists() else root, input=data, env=env, capture_output=True, timeout=60)
        with (root / 'control-captures.jsonl').open('a') as f:
            f.write(json.dumps(dict(argv=argv, cwd=str(repo), environment=env, stdin=data.hex(), stdout=p.stdout.hex(), stderr=p.stderr.hex(), exit=p.returncode)) + '\n')
        assert p.returncode == 0, (argv, p.stdout, p.stderr)
        return p.stdout
    if request['op'] in ('seed', 'empty'):
        if repo.exists():
            shutil.rmtree(repo)
        repo.parent.mkdir(parents=True, exist_ok=True)
        run('init', '-q', '--bare', '-b', 'main', repo)
        result = dict(path=str(repo))
        if request['op'] == 'seed':
            commits = []
            for data in (b'first\n', b'first\nsecond\n'):
                blob = run('hash-object', '-w', '--stdin', data=data).strip().decode()
                tree = run('mktree', data=f'100644 blob {blob}\ta\n'.encode()).strip().decode()
                commit = run('commit-tree', tree, *(['-p', commits[0]] if commits else []), '-m', 'second' if commits else 'first').strip().decode()
                commits.append(commit)
            run('update-ref', 'refs/heads/main', commits[0])
            result.update(first=commits[0], second=commits[1])
        return result
    if request['op'] == 'update':
        value = request['id']
        assert re.fullmatch('[0-9a-f]{40}', value)
        assert run('cat-file', '-t', value) == b'commit\n'
        run('update-ref', 'refs/heads/main', value)
        return dict(path=str(repo), id=value)
    assert request['op'] == 'state'
    references = run('for-each-ref', '--format=%(refname) %(objectname)').decode().splitlines()
    names = run('rev-list', '--objects', '--all').decode().splitlines() if references else []
    objects = {}
    for name in names:
        value = name.split(' ', 1)[0]
        kind = run('cat-file', '-t', value).strip().decode()
        objects[value] = dict(kind=kind, data=run('cat-file', kind, value).hex())
    files = {}
    for p in repo.rglob('*'):
        if p.is_symlink():
            files[str(p.relative_to(repo))] = dict(link=str(p.readlink()))
        elif p.is_file():
            files[str(p.relative_to(repo))] = dict(mode=p.stat().st_mode & 0o777, hex=p.read_bytes().hex())
    fsck = run('fsck', '--full', '--no-dangling')
    return dict(path=str(repo), refs=dict(line.split(' ', 1) for line in references), objects=objects, files=files, fsck=fsck.hex())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', type=Path)
    parser.add_argument('--git', type=Path)
    parser.add_argument('--slot', choices=('4-7', '8-11'))
    args = parser.parse_args()
    if args.install:
        assert args.git and args.slot
        install(args.install, args.git, args.slot)
    else:
        print(json.dumps(control()), flush=True)
