"""vc12 oracle-only exploratory measurement of stash and notes.

Black-box runs of the pinned Git 2.56.0 under tools/env; not differential
parity. Each step records stdout, stderr, status and the .git/worktree files
that appeared, vanished or changed (text bodies for small non-object files).
Clean room: no Git implementation source is read; only the binary is run.
"""
import hashlib, json, os, pathlib, shutil, subprocess, sys, zlib

R = pathlib.Path(__file__).resolve().parent.parent
GIT = os.environ['DEN_GIT']
PIN = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
assert hashlib.sha256(pathlib.Path(GIT).read_bytes()).hexdigest() == PIN, 'oracle digest'
WORK = R / 'target/vc12-measure'


def files(repo):
    out = {}
    for p in sorted(repo.rglob('*')):
        if p.is_file() and not p.is_symlink():
            out[p.relative_to(repo).as_posix()] = p.read_bytes()
    return out


def show_body(key, data):
    if '/objects/' in key and len(key.split('/')[-1]) == 38:
        raw = zlib.decompress(data)
        head, body = raw.split(b'\0', 1)
        if head.startswith(b'tree'):
            entries, i = [], 0
            while i < len(body):
                sp = body.index(b' ', i); nul = body.index(b'\0', sp)
                entries.append(f"{body[i:sp].decode()} {body[sp+1:nul].decode('latin-1')} {body[nul+1:nul+21].hex()}")
                i = nul + 21
            return head.decode() + ' | ' + '; '.join(entries)
        return head.decode() + ' | ' + body.decode('latin-1')
    if key.endswith('/index') or key == '.git/index':
        return f'<index {len(data)} bytes, ext={[data[i:i+4] for i in range(12, len(data)-24) if data[i:i+4] in (b"TREE", b"REUC")]}>'
    if len(data) < 4096:
        return data.decode('latin-1')
    return f'<{len(data)} bytes>'


def step(repo, log, label, args, stdin=b''):
    before = files(repo)
    p = subprocess.run([GIT, *args], cwd=repo, input=stdin, capture_output=True, timeout=60)
    after = files(repo)
    changes = {}
    for k in sorted(set(before) | set(after)):
        if before.get(k) != after.get(k):
            changes[k] = None if k not in after else show_body(k, after[k])
    rec = {'label': label, 'args': args, 'status': p.returncode,
           'stdout': p.stdout.decode('latin-1'), 'stderr': p.stderr.decode('latin-1'),
           'changes': changes}
    log.append(rec)
    print(f'=== {label}: git {" ".join(args)} -> {p.returncode}')
    if p.stdout: print('--- stdout\n' + p.stdout.decode('latin-1'), end='' if p.stdout.endswith(b'\n') else '\n')
    if p.stderr: print('--- stderr\n' + p.stderr.decode('latin-1'), end='' if p.stderr.endswith(b'\n') else '\n')
    for k, v in changes.items():
        print(f'    {k}: {"<removed>" if v is None else v!r}'[:600])
    return p


def fresh(name):
    repo = WORK / name
    if repo.exists(): shutil.rmtree(repo)
    repo.mkdir(parents=True)
    subprocess.run([GIT, 'init', '-q'], cwd=repo, check=True)
    return repo


def write(repo, path, data):
    p = repo / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def base(name):
    repo = fresh(name)
    write(repo, 'a.txt', b'alpha\n'); write(repo, 'b.txt', b'beta\n'); write(repo, 'dir/c.txt', b'gamma\n')
    subprocess.run([GIT, 'add', '.'], cwd=repo, check=True)
    subprocess.run([GIT, 'commit', '-q', '-m', 'first subject\n\nbody line'], cwd=repo, check=True)
    return repo


def stash_scenarios(log):
    r = base('stash-basic')
    step(r, log, 'nothing', ['stash'])
    write(r, 'a.txt', b'alpha changed\n'); write(r, 'b.txt', b'beta staged\n')
    subprocess.run([GIT, 'add', 'b.txt'], cwd=r, check=True)
    write(r, 'b.txt', b'beta staged then worktree\n')
    write(r, 'new.txt', b'added\n'); subprocess.run([GIT, 'add', 'new.txt'], cwd=r, check=True)
    (r / 'dir/c.txt').unlink()
    write(r, 'untracked', b'u\n')
    step(r, log, 'push-default', ['stash'])
    step(r, log, 'status-after', ['status', '--porcelain'])
    step(r, log, 'list-one', ['stash', 'list'])
    step(r, log, 'show-default', ['stash', 'show'])
    step(r, log, 'show-p', ['stash', 'show', '-p'])
    step(r, log, 'show-stat-name', ['stash', 'show', '--stat', 'stash@{0}'])
    step(r, log, 'cat-W', ['cat-file', '-p', 'stash@{0}'])
    step(r, log, 'cat-I', ['cat-file', '-p', 'stash@{0}^2'])
    write(r, 'a.txt', b'alpha second\n')
    step(r, log, 'push-m', ['stash', 'push', '-m', 'my message'])
    step(r, log, 'list-two', ['stash', 'list'])
    step(r, log, 'show-1', ['stash', 'show', '1'])
    step(r, log, 'apply-0', ['stash', 'apply'])
    step(r, log, 'status-apply', ['status', '--porcelain'])
    step(r, log, 'reset-hard', ['reset', '-q', '--hard'])
    step(r, log, 'apply-index-1', ['stash', 'apply', '--index', 'stash@{1}'])
    step(r, log, 'status-apply-index', ['status', '--porcelain'])
    step(r, log, 'reset-hard2', ['reset', '-q', '--hard'])
    step(r, log, 'rm-new', ['clean', '-q', '-f', 'new.txt'])
    step(r, log, 'pop', ['stash', 'pop'])
    step(r, log, 'list-after-pop', ['stash', 'list'])
    step(r, log, 'drop-dirty', ['stash', 'drop'])
    step(r, log, 'drop-empty', ['stash', 'drop'])
    step(r, log, 'list-empty', ['stash', 'list'])
    step(r, log, 'show-empty', ['stash', 'show'])
    step(r, log, 'apply-empty', ['stash', 'apply'])
    step(r, log, 'pop-empty', ['stash', 'pop'])
    step(r, log, 'clear-empty', ['stash', 'clear'])

    r = base('stash-drop')
    for i in range(3):
        write(r, 'a.txt', f'v{i}\n'.encode())
        step(r, log, f'push{i}', ['stash', 'push', '-q', '-m', f'm{i}'])
    step(r, log, 'drop-1', ['stash', 'drop', 'stash@{1}'])
    step(r, log, 'list', ['stash', 'list'])
    step(r, log, 'drop-bare-1', ['stash', 'drop', '1'])
    step(r, log, 'drop-bad', ['stash', 'drop', 'stash@{5}'])
    step(r, log, 'apply-bad', ['stash', 'apply', 'stash@{5}'])
    step(r, log, 'show-bad', ['stash', 'show', 'stash@{5}'])
    step(r, log, 'drop-q', ['stash', 'drop', '-q'])
    for i in range(2):
        write(r, 'a.txt', f'w{i}\n'.encode())
        step(r, log, f'repush{i}', ['stash', 'push', '-m', f'n{i}'])
    step(r, log, 'drop-0-of-2', ['stash', 'drop', 'stash@{0}'])
    write(r, 'a.txt', b'w9\n'); step(r, log, 'repush9', ['stash'])
    step(r, log, 'clear', ['stash', 'clear'])
    step(r, log, 'apply-HEAD', ['stash', 'apply', 'HEAD'])

    r = fresh('stash-unborn')
    write(r, 'a.txt', b'x\n'); subprocess.run([GIT, 'add', 'a.txt'], cwd=r, check=True)
    step(r, log, 'unborn', ['stash'])

    r = base('stash-detached')
    subprocess.run([GIT, 'checkout', '-q', '--detach'], cwd=r, check=True)
    write(r, 'a.txt', b'detached change\n')
    step(r, log, 'detached-push', ['stash'])
    step(r, log, 'detached-list', ['stash', 'list'])

    r = base('stash-keep')
    write(r, 'a.txt', b'staged\n'); subprocess.run([GIT, 'add', 'a.txt'], cwd=r, check=True)
    write(r, 'b.txt', b'worktree only\n')
    step(r, log, 'keep-index', ['stash', 'push', '--keep-index'])
    step(r, log, 'keep-status', ['status', '--porcelain'])
    step(r, log, 'keep-pop-dirty', ['stash', 'pop'])

    r = base('stash-moved')
    write(r, 'a.txt', b'stashed a\n')
    step(r, log, 'moved-push', ['stash', '-q'])
    write(r, 'b.txt', b'beta moved\n'); subprocess.run([GIT, 'commit', '-qam', 'move b'], cwd=r, check=True)
    step(r, log, 'moved-apply', ['stash', 'apply'])
    step(r, log, 'moved-status', ['status', '--porcelain'])
    subprocess.run([GIT, 'reset', '-q', '--hard'], cwd=r, check=True)
    write(r, 'a.txt', b'conflict a\n'); subprocess.run([GIT, 'commit', '-qam', 'conflict a'], cwd=r, check=True)
    step(r, log, 'conflict-apply', ['stash', 'apply'])
    step(r, log, 'conflict-status', ['status', '--porcelain'])

    r = base('stash-dirty-apply')
    write(r, 'a.txt', b'stashed a\n'); step(r, log, 'dirty-push', ['stash', '-q'])
    write(r, 'a.txt', b'dirty a\n')
    step(r, log, 'dirty-apply-same', ['stash', 'apply'])
    write(r, 'a.txt', b'alpha\n'); write(r, 'b.txt', b'dirty b\n')
    step(r, log, 'dirty-apply-other', ['stash', 'apply'])
    step(r, log, 'dirty-other-status', ['status', '--porcelain'])

    r = base('stash-untracked-collide')
    write(r, 'n.txt', b'new\n'); subprocess.run([GIT, 'add', 'n.txt'], cwd=r, check=True)
    step(r, log, 'collide-push', ['stash', '-q'])
    write(r, 'n.txt', b'untracked collision\n')
    step(r, log, 'collide-apply', ['stash', 'apply'])

    r = base('stash-u')
    write(r, 'u.txt', b'u\n')
    step(r, log, 'u-only-untracked', ['stash'])
    step(r, log, 'u-push', ['stash', '-u'])
    step(r, log, 'u-cat', ['cat-file', '-p', 'stash@{0}'])
    step(r, log, 'u-cat3', ['cat-file', '-p', 'stash@{0}^3'])


def notes_scenarios(log):
    r = base('notes-basic')
    step(r, log, 'list-none', ['notes', 'list'])
    step(r, log, 'bare-none', ['notes'])
    step(r, log, 'show-none', ['notes', 'show'])
    step(r, log, 'add', ['notes', 'add', '-m', 'first note  ', 'HEAD'])
    step(r, log, 'add-again', ['notes', 'add', '-m', 'second'])
    step(r, log, 'add-force', ['notes', 'add', '-f', '-m', 'second', '-m', 'third\n\n\n'])
    step(r, log, 'show', ['notes', 'show'])
    step(r, log, 'list', ['notes', 'list'])
    step(r, log, 'list-obj', ['notes', 'list', 'HEAD'])
    step(r, log, 'bare', ['notes'])
    step(r, log, 'log', ['log'])
    step(r, log, 'log-oneline', ['log', '--oneline'])
    step(r, log, 'show-commit', ['show', '-s'])
    step(r, log, 'log-format', ['log', '--format=%H %s'])
    step(r, log, 'add-blob', ['notes', 'add', '-m', 'on a blob', 'HEAD:a.txt'])
    step(r, log, 'list2', ['notes', 'list'])
    step(r, log, 'remove', ['notes', 'remove', 'HEAD'])
    step(r, log, 'remove-missing', ['notes', 'remove', 'HEAD'])
    step(r, log, 'remove-ignore', ['notes', 'remove', '--ignore-missing', 'HEAD'])
    step(r, log, 'add-empty', ['notes', 'add', '-m', '', 'HEAD'])
    step(r, log, 'add-ws', ['notes', 'add', '-m', '  \n  ', 'HEAD'])
    step(r, log, 'show-missing', ['notes', 'show', 'HEAD'])
    step(r, log, 'list-missing', ['notes', 'list', 'HEAD'])
    step(r, log, 'add-bad', ['notes', 'add', '-m', 'x', 'nosuch'])
    step(r, log, 'remove-blob', ['notes', 'remove', 'HEAD:a.txt'])
    step(r, log, 'list-after', ['notes', 'list'])
    step(r, log, 'reflog', ['reflog', 'show', 'refs/notes/commits'])

    r = base('notes-fanout')
    blobs = []
    for i in range(300):
        p = subprocess.run([GIT, 'hash-object', '-w', '--stdin'], cwd=r, input=f'blob {i}\n'.encode(), capture_output=True, check=True)
        blobs.append(p.stdout.decode().strip())
    for i, b in enumerate(blobs):
        subprocess.run([GIT, 'notes', 'add', '-m', f'n{i}', b], cwd=r, capture_output=True, check=True)
        tree = subprocess.run([GIT, 'ls-tree', 'refs/notes/commits'], cwd=r, capture_output=True, check=True).stdout.decode()
        subdirs = sum(1 for line in tree.splitlines() if line.split()[1] == 'tree')
        if subdirs:
            print(f'fanout first appears after note {i + 1}: {subdirs} subtrees')
            log.append({'label': 'fanout-threshold', 'notes': i + 1, 'subtrees': subdirs,
                        'tree': tree})
            break
    else:
        print('no fanout after 300 notes')
        log.append({'label': 'fanout-threshold', 'notes': None})


def index_dump(repo, log, label):
    data = (repo / '.git/index').read_bytes()
    count = int.from_bytes(data[8:12], 'big'); pos = 12; rows = []
    for _ in range(count):
        words = [int.from_bytes(data[pos + 4 * i:pos + 4 * i + 4], 'big') for i in range(10)]
        oid = data[pos + 40:pos + 60].hex(); flags = int.from_bytes(data[pos + 60:pos + 62], 'big')
        nul = data.index(b'\0', pos + 62); path = data[pos + 62:nul].decode()
        size = 62 + len(path) + 1; size += (-size) % 8 or 0
        if (62 + len(path)) % 8 == 0: size = 62 + len(path) + 8
        pos += ((62 + len(path) + 8) // 8) * 8
        st = os.lstat(repo / path) if (repo / path).exists() else None
        live = None if st is None else [int(st.st_ctime), st.st_ctime_ns % 10**9, int(st.st_mtime), st.st_mtime_ns % 10**9, st.st_dev & 0xffffffff, st.st_ino & 0xffffffff]
        rows.append({'path': path, 'mode': oct(words[6]), 'oid': oid[:12], 'flags': flags,
                     'ctime_mtime_dev_ino': words[0:6], 'size': words[9], 'stat_matches_lstat': live == words[0:6]})
    ext = data[pos:-20]
    print(f'--- index {label}:')
    for r in rows: print('    ', r)
    print('     extensions:', ext.hex())
    log.append({'label': 'index-' + label, 'entries': rows, 'extensions': ext.hex()})


def round_two(log):
    r = base('r2-apply-mixed')
    write(r, 'a.txt', b'alpha changed\n'); write(r, 'b.txt', b'beta staged\n')
    subprocess.run([GIT, 'add', 'b.txt'], cwd=r, check=True)
    write(r, 'new.txt', b'added\n'); subprocess.run([GIT, 'add', 'new.txt'], cwd=r, check=True)
    (r / 'dir/c.txt').unlink()
    index_dump(r, log, 'before-push')
    step(r, log, 'mixed-push', ['stash'])
    index_dump(r, log, 'after-push')
    step(r, log, 'mixed-apply', ['stash', 'apply'])
    index_dump(r, log, 'after-apply')
    step(r, log, 'mixed-apply-status', ['status', '--porcelain'])
    subprocess.run([GIT, 'reset', '-q', '--hard'], cwd=r, check=True)
    (r / 'new.txt').unlink(missing_ok=True)
    step(r, log, 'mixed-apply-index', ['stash', 'apply', '--index'])
    index_dump(r, log, 'after-apply-index')
    subprocess.run([GIT, 'reset', '-q', '--hard'], cwd=r, check=True)
    (r / 'new.txt').unlink(missing_ok=True)
    write(r, 'b.txt', b'staged before apply\n'); subprocess.run([GIT, 'add', 'b.txt'], cwd=r, check=True)
    step(r, log, 'apply-on-staged-same', ['stash', 'apply'])
    step(r, log, 'apply-index-on-staged', ['stash', 'apply', '--index'])
    subprocess.run([GIT, 'reset', '-q', '--hard'], cwd=r, check=True)
    write(r, 'dir/c.txt', b'staged other\n'); subprocess.run([GIT, 'add', 'dir/c.txt'], cwd=r, check=True)
    step(r, log, 'apply-on-staged-other', ['stash', 'apply'])
    step(r, log, 'status-staged-other', ['status', '--porcelain'])
    subprocess.run([GIT, 'reset', '-q', '--hard'], cwd=r, check=True)
    for f in ('new.txt',):
        if (r / f).exists(): (r / f).unlink()
    step(r, log, 'pop-mixed', ['stash', 'pop'])
    index_dump(r, log, 'after-pop')

    r = base('r2-keep')
    write(r, 'a.txt', b'staged\n'); subprocess.run([GIT, 'add', 'a.txt'], cwd=r, check=True)
    write(r, 'b.txt', b'worktree only\n')
    step(r, log, 'keep-push', ['stash', 'push', '--keep-index'])
    index_dump(r, log, 'after-keep')

    r = base('r2-staged-only')
    write(r, 'a.txt', b'staged\n'); subprocess.run([GIT, 'add', 'a.txt'], cwd=r, check=True)
    step(r, log, 'staged-only-push', ['stash'])
    step(r, log, 'staged-only-show', ['stash', 'show'])
    step(r, log, 'staged-only-apply', ['stash', 'apply'])
    step(r, log, 'staged-only-status', ['status', '--porcelain'])

    r = base('r2-messages')
    for i, args in enumerate([['stash', 'push', '-m', 'two\nlines'], ['stash', 'push', '-m', 'trail\n'],
                              ['stash', '-m', 'bare form'], ['stash', 'save', 'saved', 'words'],
                              ['stash', 'push', '--message=long form'], ['stash', 'push', '-m', ''],
                              ['stash', 'push', '-q'], ['stash', 'push', '--', 'a.txt'],
                              ['stash', 'push', 'a.txt'], ['stash', 'nosuch'], ['stash', 'push', '-p'],
                              ['stash', 'push', '--staged'], ['stash', 'list', '--oneline'],
                              ['stash', 'show', '--name-only'], ['stash', 'show', '-p', '1'],
                              ['stash', 'show', '--stat', '-p']]):
        write(r, 'a.txt', f'v{i}\n'.encode())
        step(r, log, f'msg-{i}', args)
    step(r, log, 'msg-list', ['stash', 'list'])
    step(r, log, 'msg-reflog', ['reflog', 'show', 'refs/stash'])

    r = base('r2-show-width')
    write(r, 'a-very-long-file-name-that-goes-on-and-on-and-on-forever-and-ever.txt', b'x\n' * 50)
    subprocess.run([GIT, 'add', '.'], cwd=r, check=True)
    write(r, 'bin.dat', b'\0\1\2'); subprocess.run([GIT, 'add', 'bin.dat'], cwd=r, check=True)
    step(r, log, 'width-push', ['stash', '-q'])
    step(r, log, 'width-show', ['stash', 'show'])
    step(r, log, 'width-show-p', ['stash', 'show', '-p'])

    r = base('r2-rename')
    subprocess.run([GIT, 'mv', 'a.txt', 'moved.txt'], cwd=r, check=True)
    step(r, log, 'rename-push', ['stash', '-q'])
    step(r, log, 'rename-show', ['stash', 'show'])
    step(r, log, 'rename-apply', ['stash', 'apply'])
    step(r, log, 'rename-status', ['status', '--porcelain'])

    r = base('r2-exec')
    os.chmod(r / 'a.txt', 0o755)
    step(r, log, 'exec-push', ['stash'])
    step(r, log, 'exec-show', ['stash', 'show', '-p'])
    step(r, log, 'exec-apply', ['stash', 'apply'])

    r = base('r2-lock')
    write(r, 'a.txt', b'locked\n'); write(r, '.git/refs/stash.lock', b'')
    step(r, log, 'stash-lock-push', ['stash'])
    (r / '.git/refs/stash.lock').unlink()
    write(r, '.git/index.lock', b'')
    step(r, log, 'index-lock-push', ['stash'])
    (r / '.git/index.lock').unlink()

    # Notes in history formats.
    r = base('r2-notes-history')
    subprocess.run([GIT, 'notes', 'add', '-m', 'note one\n\nsecond paragraph'], cwd=r, check=True)
    for args in (['log'], ['log', '--pretty=medium'], ['log', '--format=medium'], ['log', '--pretty=full'],
                 ['log', '--pretty=fuller'], ['log', '--pretty=short'], ['log', '-p'], ['log', '--stat'],
                 ['show'], ['show', '--stat'], ['log', '--no-notes'], ['log', '--notes']):
        step(r, log, 'hist-' + '_'.join(args), args)
    subprocess.run([GIT, 'pack-refs', '--all'], cwd=r, check=True)
    step(r, log, 'hist-packed-notes-ref', ['log', '-1'])
    print('refs/notes dir exists after pack-refs:', (r / '.git/refs/notes').exists(),
          list((r / '.git/refs/notes').iterdir()) if (r / '.git/refs/notes').exists() else None)

    r = fresh('r2-notes-unborn')
    step(r, log, 'notes-unborn-add', ['notes', 'add', '-m', 'x'])
    step(r, log, 'notes-unborn-list', ['notes', 'list'])
    r = base('r2-notes-misc')
    step(r, log, 'notes-remove-noref', ['notes', 'remove', 'HEAD'])
    step(r, log, 'notes-tree', ['notes', 'add', '-m', 'tree note', 'HEAD^{tree}'])
    step(r, log, 'notes-two', ['notes', 'add', '-m', 'commit note'])
    step(r, log, 'notes-remove-two', ['notes', 'remove', 'HEAD', 'HEAD^{tree}'])
    step(r, log, 'notes-add-F', ['notes', 'add', '-F', '/dev/null'])
    step(r, log, 'notes-append', ['notes', 'append', '-m', 'x'])
    step(r, log, 'notes-ref', ['notes', '--ref=other', 'add', '-m', 'x'])
    step(r, log, 'notes-get-ref', ['notes', 'get-ref'])
    step(r, log, 'notes-allow-empty', ['notes', 'add', '--allow-empty', '-m', ''])
    step(r, log, 'notes-show-empty', ['notes', 'show'])

    # Fan-out threshold across independent object sets.
    for seed in range(4):
        r = base(f'r2-fanout-{seed}')
        ids = []
        for i in range(200):
            p = subprocess.run([GIT, 'hash-object', '-w', '--stdin'], cwd=r, input=f'seed {seed} blob {i}\n'.encode(), capture_output=True, check=True)
            ids.append(p.stdout.decode().strip())
        found = None
        for i, b in enumerate(ids):
            subprocess.run([GIT, 'notes', 'add', '-m', f'n{i}', b], cwd=r, capture_output=True, check=True)
            tree = subprocess.run([GIT, 'ls-tree', 'refs/notes/commits'], cwd=r, capture_output=True, check=True).stdout.decode()
            if any(line.split()[1] == 'tree' for line in tree.splitlines()):
                found = i + 1; break
        lens = [len(line.split('\t')[1]) for line in tree.splitlines()]
        print(f'fanout seed {seed}: first fan-out after {found} notes; top-level name lengths {sorted(set(lens))}')
        log.append({'label': f'fanout-seed-{seed}', 'notes': found})
        if seed == 0:
            step(r, log, 'fanned-show', ['notes', 'show', ids[0]])
            step(r, log, 'fanned-list-head', ['notes', 'list'])
            step(r, log, 'fanned-add', ['notes', 'add', '-m', 'more', 'HEAD'])
            step(r, log, 'fanned-remove', ['notes', 'remove', ids[1]])
            subprocess.run([GIT, 'notes', 'remove'] + ids[2:found], cwd=r, capture_output=True)
            tree = subprocess.run([GIT, 'ls-tree', 'refs/notes/commits'], cwd=r, capture_output=True, check=True).stdout.decode()
            print('after removing down to', len(tree.splitlines()), 'top entries:', tree[:300])


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    log = []
    if sys.argv[1:] == ['--round-two']:
        round_two(log)
        out = R / 'notes/vc12-evidence/round-two-observations.json'
        out.write_text(json.dumps({'oracle_sha256': PIN, 'parity': False,
                                   'kind': 'oracle-only exploratory measurement', 'steps': log},
                                  indent=1, sort_keys=True) + '\n')
        print(f'wrote {out} with {len(log)} records')
        return
    stash_scenarios(log)
    notes_scenarios(log)
    out = R / 'notes/vc12-evidence/initial-observations.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'oracle_sha256': PIN, 'parity': False,
                               'kind': 'oracle-only exploratory measurement', 'steps': log},
                              indent=1, sort_keys=True) + '\n')
    print(f'wrote {out} with {len(log)} records')


if __name__ == '__main__':
    main()
