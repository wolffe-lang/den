#!/usr/bin/env python3
"""vc23: clone and fetch a pack larger than 128 MiB on every transport (den#61).

Run through tools/env in the oracle container. The fixture is a bare
repository the pinned Git builds from a seeded generator: a text file
rewritten over forty commits (so its versions deltify), three 48 MiB random
blobs added along the way, a second branch and an annotated tag. Its one pack
exceeds 134,217,728 bytes, the old 128 MiB payload cap. den and the pinned Git
clone it over a plain local path, file://, git:// (the pinned git daemon),
ssh (a local ssh stand-in that drops the client options and the host and runs
the remote command through /bin/sh, as the far side's shell would) and https
(the pinned OpenSSL terminator in front of the pinned git-http-backend,
http-git-test.py's fixture). For each clone: process bytes and status agree;
refs, HEAD, every reachable object's bytes, remote and branch configuration
and the worktree are equal; the pinned Git's fsck --full and status are clean
on den's clone. Every child's peak RSS and time are recorded beside Git's.

Rows:
  large-pack-local, large-pack-file, large-pack-git, large-pack-ssh,
  large-pack-https     clones, as above
  large-pack-fetch     an incremental fetch of the large commits into a clone
                       of an early branch (configured remote, file://):
                       remote-tracking refs, their reachable objects and fsck
  large-pack-memory    den's file:// clone under `prlimit --as` at the bound
                       predicted in tests/vc23-prediction.txt (P2)
  large-pack-object-limit
                       a pack whose one blob is one byte over den's per-object
                       cap: den refuses by name, exit 2, and leaves nothing;
                       the pinned Git indexes the same pack (it has no cap)
No row is skipped; a failed comparison is FAIL, never a review.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import runpy
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time

GIT_SHA256 = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
MIB = 1 << 20
BIG = 48 * MIB
OLD_PAYLOAD_CAP = 134217728
# R-vc23-2: den's per-object cap, and its refusal by name.
OBJECT_LIMIT = 512 * MIB
# den#100: the bound is a fatal error naming itself and its value.
LIMIT_STDERR = b'fatal: limit: a pack object larger than 536870912 bytes\n'
# tests/vc23-prediction.txt P2: 64 MiB + W (96 MiB) + 5 x L, L = 48 MiB here.
MEMORY_BOUND = 64 * MIB + 96 * MIB + 5 * BIG
CLONE_SECONDS = 1800
ROWS = ('local', 'file', 'git', 'ssh', 'https', 'fetch', 'memory', 'object-limit')

SSH_STANDIN = r'''#!/bin/sh
# A local ssh stand-in: drop the client's options and the host, then run the
# remote command's words, joined by spaces, through /bin/sh as sshd would.
while [ "$#" -gt 0 ]; do
    case "$1" in
    -o | -p | -l | -i | -F | -J) shift 2 ;;
    --) shift; break ;;
    -*) shift ;;
    *) break ;;
    esac
done
shift
exec /bin/sh -c "$*"
'''


def build_large(git, env, out, path):
    """The large fixture, built in its own process so the harness stays small:
    a child's peak RSS starts at its parent's (an exec keeps the high-water
    mark), and den's must be den's own."""

    def git_out(repo, *argv, data=None, timeout=600):
        result = subprocess.run([git, '-C', str(repo), *argv], env=env, input=data, capture_output=True,
                                timeout=timeout)
        if result.returncode:
            raise AssertionError('pinned Git ' + argv[0] + ' failed: ' +
                                 result.stderr.decode(errors='replace').strip()[-400:])
        return result.stdout

    git_out(out, 'init', '-q', '--bare', str(path))
    git_out(path, 'symbolic-ref', 'HEAD', 'refs/heads/main')
    for key, value in (('gc.auto', '0'), ('maintenance.auto', 'false')):
        git_out(path, 'config', key, value)
    rng = random.Random(61)
    words = [''.join(rng.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(rng.randint(2, 9)))
             for _ in range(4096)]
    lines = [' '.join(rng.choice(words) for _ in range(12)) for _ in range(16384)]
    big, parent, commits = [], None, []
    for i in range(40):
        for _ in range(64):
            lines[rng.randrange(len(lines))] = ' '.join(rng.choice(words) for _ in range(12))
        text = ('\n'.join(lines) + '\n').encode()
        blob = git_out(path, 'hash-object', '-w', '--stdin', data=text).strip()
        if i in (10, 25, 39):
            data = rng.randbytes(BIG)
            big.append(git_out(path, 'hash-object', '-w', '--stdin', data=data).strip())
        readme = git_out(path, 'hash-object', '-w', '--stdin', data=b'fixture %d\n' % i).strip()
        data_tree = None
        if big:
            data_tree = git_out(path, 'mktree', data=b''.join(
                b'100644 blob ' + name + b'\tbig-%d.bin\n' % k for k, name in enumerate(big))).strip()
        top = [b'100644 blob ' + readme + b'\tREADME\n']
        if data_tree:
            top.append(b'040000 tree ' + data_tree + b'\tdata\n')
        top.append(b'100644 blob ' + blob + b'\tnotes.txt\n')
        tree = git_out(path, 'mktree', data=b''.join(top)).strip().decode()
        argv = ['commit-tree', tree, '-m', 'fixture %d' % i] + (['-p', parent] if parent else [])
        parent = git_out(path, *argv).strip().decode()
        commits.append(parent)
    git_out(path, 'update-ref', 'refs/heads/main', commits[-1])
    git_out(path, 'update-ref', 'refs/heads/side', commits[20])
    git_out(path, 'update-ref', 'refs/heads/early', commits[5])
    git_out(path, 'tag', '-a', 'v1', '-m', 'fixture tag', commits[30])
    # No bitmap: den refuses one by name (a named limit outside this lane),
    # and a plain local path clone copies the object directory as it is.
    git_out(path, '-c', 'pack.threads=1', '-c', 'core.bigFileThreshold=16m', '-c', 'repack.writeBitmaps=false',
            'repack', '-a', '-d', '-f', '-q', '--depth=50', '--window=10', timeout=1200)
    packs = sorted((path / 'objects/pack').glob('*.pack'))
    assert len(packs) == 1, 'fixture: one pack'
    size = packs[0].stat().st_size
    assert size > OLD_PAYLOAD_CAP, 'fixture: pack over 128 MiB'
    verify = git_out(path, 'verify-pack', '-v', str(packs[0].with_suffix('.idx')), timeout=1200).decode()
    depths = [int(f.split()[5]) for f in verify.splitlines()
              if len(f.split()) >= 7 and f.split()[1] in ('commit', 'tree', 'blob', 'tag')]
    info = dict(pack_bytes=size, objects=git_out(path, 'count-objects', '-v').decode(),
                deltas=len(depths), deepest=max(depths) if depths else 0, largest=BIG)
    return info


def serve_https(git, env, out):
    """The pinned OpenSSL terminator in front of git-http-backend for out's
    remote.git (http-git-test.py's Server), with a fresh test CA; one JSON
    line when ready, one when stdin closes and the fixture has stopped."""
    root = Path(__file__).resolve().parent.parent
    fixture = runpy.run_path(str(root / 'tools/http-git-test.py'))
    for path, digest in fixture['OPENSSL_PINS'].items():
        for _ in range(2):
            assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, 'pinned TLS oracle digest'
    pki = root / 'target/pki' / out.name
    shutil.rmtree(pki, ignore_errors=True)
    pki.mkdir(parents=True)

    def openssl(*argv):
        result = subprocess.run(['/usr/bin/openssl', *map(str, argv)], env=env, capture_output=True, timeout=120)
        assert result.returncode == 0, 'fixture openssl ' + str(argv[0])

    openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '2',
            '-subj', '/CN=Large pack fixture root', '-addext', 'basicConstraints=critical,CA:TRUE',
            '-addext', 'keyUsage=critical,keyCertSign,cRLSign', '-keyout', pki / 'ca.key', '-out', pki / 'ca.pem')
    openssl('x509', '-in', pki / 'ca.pem', '-outform', 'DER', '-out', pki / 'ca.der')
    (pki / 'leaf.cnf').write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n'
                                  'extendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost\n')
    openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=localhost',
            '-keyout', pki / 'leaf.key', '-out', pki / 'leaf.csr')
    openssl('x509', '-req', '-in', pki / 'leaf.csr', '-CA', pki / 'ca.pem', '-CAkey', pki / 'ca.key',
            '-CAcreateserial', '-days', '1', '-sha256', '-extfile', pki / 'leaf.cnf', '-out', pki / 'leaf.pem')
    server = fixture['Server'](out, git, env, 'tls', pki, '', lambda data: None)
    try:
        print(json.dumps(dict(url=server.url, ca_pem=str(pki / 'ca.pem'), ca_der=str(pki / 'ca.der'))), flush=True)
        sys.stdin.read()
    finally:
        server.close()
        shutil.rmtree(pki, ignore_errors=True)
    print(json.dumps(dict(errors=server.errors)), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    parser.add_argument('--rows', default=','.join(ROWS))
    parser.add_argument('--build-fixture', help=argparse.SUPPRESS)
    parser.add_argument('--serve-https', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.serve_https:
        serve_https(os.environ['DEN_GIT'], dict(os.environ), Path(args.serve_https))
        return
    if args.build_fixture:
        target = Path(args.build_fixture)
        print(json.dumps(build_large(os.environ['DEN_GIT'], dict(os.environ), target.parent, target)))
        return
    rows = args.rows.split(',')
    assert rows and set(rows) <= set(ROWS), 'rows'
    root = Path(__file__).resolve().parent.parent
    git = str(Path(os.environ['DEN_GIT']).resolve())
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == GIT_SHA256, 'pinned Git digest'
    den = root / 'target' / args.tier / 'den'
    if not den.is_file():
        raise SystemExit('FAIL large-pack-input: build target/' + args.tier + '/den first')
    out = root / 'target/runs' / ('large-pack-' + args.tier)
    if out.exists():
        raise SystemExit('FAIL large-pack-fresh-output: select a fresh build directory')
    out.mkdir(parents=True)
    (out / 'bin').mkdir()
    standin = out / 'bin/ssh'
    standin.write_text(SSH_STANDIN)
    standin.chmod(0o755)
    env = dict(os.environ)
    env.update(PATH=str(out / 'bin') + ':' + env['PATH'], GIT_SSH_VARIANT='ssh', GIT_TERMINAL_PROMPT='0',
               GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='protocol.version', GIT_CONFIG_VALUE_0='2')
    captures, results, failed = [], {}, []

    def record():
        (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')
        (out / 'results.json').write_text(json.dumps(results, indent=2, sort_keys=True) + '\n')

    def run(argv, cwd, label, timeout=CLONE_SECONDS, extra=None):
        # The child is reaped by wait4, so its own peak RSS and CPU are measured.
        index = len(captures)
        paths = out / ('%03d.stdout' % index), out / ('%03d.stderr' % index)
        started = time.monotonic()
        with open(paths[0], 'wb') as stdout, open(paths[1], 'wb') as stderr:
            child = subprocess.Popen(list(map(str, argv)), cwd=cwd, env={**env, **(extra or {})},
                                     stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        terminate_at, kill_at, timed_out = started + timeout, None, False
        while True:
            pid, status, usage = os.wait4(child.pid, os.WNOHANG)
            if pid:
                break
            now = time.monotonic()
            if not timed_out and now >= terminate_at:
                timed_out, kill_at = True, now + 10
                os.kill(child.pid, signal.SIGTERM)  # This child's pid only, never a group.
            elif kill_at is not None and now >= kill_at:
                os.kill(child.pid, signal.SIGKILL)
                kill_at = None
            time.sleep(0.05)
        capture = dict(label=label, argv=list(map(str, argv)), exit=os.waitstatus_to_exitcode(status),
                       timed_out=timed_out, elapsed=round(time.monotonic() - started, 2),
                       maxrss_kib=usage.ru_maxrss, user=round(usage.ru_utime, 2), system=round(usage.ru_stime, 2),
                       stdout=paths[0].read_bytes().hex(), stderr=paths[1].read_bytes()[-4000:].hex())
        captures.append(capture)
        record()
        return capture

    def git_out(repo, *argv, data=None, timeout=600):
        result = subprocess.run([git, '-C', str(repo), *argv], env=env, input=data, capture_output=True,
                                timeout=timeout)
        if result.returncode:
            raise AssertionError('pinned Git ' + argv[0] + ' failed in ' + Path(repo).name + ': ' +
                                 result.stderr.decode(errors='replace').strip()[-400:])
        return result.stdout

    def batch_digest(repo, ids):
        # Every listed object's type, size and body, hashed as they stream.
        digest = hashlib.sha256()
        child = subprocess.Popen([git, '-C', str(repo), 'cat-file', '--batch'], env=env,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        feeder = threading.Thread(target=lambda: (child.stdin.write(b''.join(i + b'\n' for i in ids)),
                                                  child.stdin.close()))
        feeder.start()
        while True:
            chunk = child.stdout.read(MIB)
            if not chunk:
                break
            digest.update(chunk)
        feeder.join()
        assert child.wait() == 0, 'pinned Git cat-file --batch'
        return digest.hexdigest()

    def file_digest(path):
        digest = hashlib.sha256()
        with open(path, 'rb') as handle:
            while True:
                chunk = handle.read(MIB)
                if not chunk:
                    return digest.hexdigest()
                digest.update(chunk)

    def state(repo, scope=('--all',), worktree=True):
        refs = git_out(repo, 'for-each-ref', '--format=%(refname) %(objectname) %(symref)')
        ids = sorted({line.split()[0] for line in git_out(repo, 'rev-list', '--objects', *scope).splitlines()})
        config = subprocess.run([git, '-C', str(repo), 'config', '--local', '--get-regexp', r'^(remote|branch)\.'],
                                env=env, capture_output=True, timeout=60).stdout
        files = {}
        if worktree:
            for path in sorted(Path(repo).rglob('*')):
                relative = path.relative_to(repo).as_posix()
                if relative == '.git' or relative.startswith('.git/'):
                    continue
                if path.is_symlink():
                    files[relative] = 'link:' + os.readlink(path)
                elif path.is_file():
                    files[relative] = '%o:%s' % (path.stat().st_mode & 0o777, file_digest(path))
        return dict(refs=refs.decode(), head=(Path(repo) / '.git/HEAD').read_bytes().hex(), objects=len(ids),
                    objects_sha256=batch_digest(repo, ids), config=config.decode(), worktree=files)

    def compare(name, oracle, candidate, ours, theirs, problems):
        for field in ('exit', 'stdout', 'stderr'):
            if candidate[field] != oracle[field]:
                problems.append('process %s differs: den exit %d stderr %r' % (
                    field, candidate['exit'], bytes.fromhex(candidate['stderr'])[-300:]))
        if ours is not None and theirs is not None:
            differ = [key for key in theirs if ours.get(key) != theirs[key]]
            if differ:
                problems.append('state differs: ' + ', '.join(differ))

    def verdict(name, problems, measured):
        results[name] = dict(measured, problems=problems)
        record()
        print('LARGE ' + name + ' ' + json.dumps(measured, sort_keys=True), flush=True)
        # 'FAIL <row> <why>': a record reads the row's name up to the first space.
        print(('PASS ' if not problems else 'FAIL ') + name + ('' if not problems else ' ' + '; '.join(problems)),
              flush=True)
        if problems:
            failed.append(name)

    def measured_of(candidate, oracle=None):
        value = dict(den_exit=candidate['exit'], den_elapsed=candidate['elapsed'],
                     den_maxrss_kib=candidate['maxrss_kib'], den_user=candidate['user'])
        if oracle:
            value.update(git_exit=oracle['exit'], git_elapsed=oracle['elapsed'], git_maxrss_kib=oracle['maxrss_kib'],
                         git_user=oracle['user'])
        return value

    def checked_clone(repo, problems):
        if not (repo / '.git/HEAD').exists():
            problems.append('den left no repository')
            return None
        try:
            git_out(repo, 'fsck', '--full', '--no-reflogs', timeout=1200)
            dirty = git_out(repo, 'status', '--porcelain')
            if dirty:
                problems.append('den worktree dirty')
            return state(repo)
        except AssertionError as exc:
            problems.append(str(exc))
            return None

    # A child's peak RSS starts at the harness's own; record that floor.
    results['spawn_floor_kib'] = run([den, '--version'], out, 'spawn-floor', 60)['maxrss_kib']
    remote = out / 'remote.git'
    if set(rows) - {'object-limit'}:
        built = subprocess.run([sys.executable, '-I', str(Path(__file__).resolve()), '--build-fixture', str(remote)],
                               env=env, capture_output=True, timeout=1800)
        if built.returncode:
            raise AssertionError('fixture build: ' + built.stderr.decode(errors='replace')[-400:])
        results['fixture'] = json.loads(built.stdout)
        print('FIXTURE large ' + json.dumps({key: results['fixture'][key] for key in ('pack_bytes', 'deltas', 'deepest')}),
              flush=True)

    def clone_row(label, url, extra=None):
        name = 'large-pack-' + label
        problems = []
        den_dir, git_dir = out / ('den-' + label), out / ('git-' + label)
        # Git first: the TLS fixture's terminator is one byte stream, and a
        # client that stops reading early leaves the rest for the next one.
        oracle = run([git, 'clone', '-q', url, git_dir], out, name + '-git', extra=extra)
        candidate = run([den, 'clone', '-q', url, den_dir], out, name + '-den', extra=extra)
        theirs = None
        if oracle['exit']:
            problems.append('pinned Git clone exit %d' % oracle['exit'])
        else:
            theirs = state(git_dir)
        ours = checked_clone(den_dir, problems) if candidate['exit'] == 0 else None
        compare(name, oracle, candidate, ours, theirs, problems)
        measured = measured_of(candidate, oracle)
        if theirs:
            measured['objects'] = theirs['objects']
        verdict(name, problems, measured)
        for path in (den_dir, git_dir):
            shutil.rmtree(path, ignore_errors=True)

    if 'memory' in rows:
        name = 'large-pack-memory'
        problems = []
        target = out / 'den-memory'
        candidate = run(['prlimit', '--as=%d' % MEMORY_BOUND, '--', den, 'clone', '-q', remote.as_uri(), target],
                        out, name)
        if candidate['exit'] != 0:
            problems.append('den clone under a %d-byte address-space cap: exit %d, stderr %r' % (
                MEMORY_BOUND, candidate['exit'], bytes.fromhex(candidate['stderr'])[-300:]))
        else:
            checked_clone(target, problems)
        if candidate['maxrss_kib'] * 1024 > MEMORY_BOUND:
            problems.append('peak RSS %d KiB over the bound' % candidate['maxrss_kib'])
        measured = measured_of(candidate)
        measured.update(bound_bytes=MEMORY_BOUND, largest_object=BIG)
        verdict(name, problems, measured)
        shutil.rmtree(target, ignore_errors=True)
    if 'local' in rows:
        clone_row('local', str(remote))
    if 'file' in rows:
        clone_row('file', remote.as_uri())
    if 'git' in rows:
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        daemon = subprocess.Popen([git, 'daemon', '--reuseaddr', '--export-all', '--listen=127.0.0.1',
                                   '--port=' + str(port), '--base-path=' + str(out), str(out)], env=env,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                assert daemon.poll() is None, 'git daemon exited at startup'
                try:
                    with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise AssertionError('git daemon startup timeout')
            clone_row('git', 'git://127.0.0.1:%d/remote.git' % port)
        finally:
            daemon.terminate()  # This fixture's pid only.
            daemon.wait(timeout=30)
    if 'ssh' in rows:
        clone_row('ssh', 'ssh://localhost' + str(remote))
    if 'https' in rows:
        # The TLS fixture runs in its own process: it holds each response
        # whole, and a child's peak RSS starts at its parent's.
        server = subprocess.Popen([sys.executable, '-I', str(Path(__file__).resolve()), '--serve-https', str(out)],
                                  env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        try:
            ready = json.loads(server.stdout.readline())
            clone_row('https', ready['url'], dict(GIT_SSL_CAINFO=ready['ca_pem'], DEN_TLS_ROOTS=ready['ca_der']))
        finally:
            server.stdin.close()
            closing = json.loads(server.stdout.readline() or '{"errors": ["no report"]}')
            server.wait(timeout=60)
        if closing['errors']:
            failed.append('large-pack-https-fixture')
            print('FAIL large-pack-https-fixture: ' + ', '.join(closing['errors']), flush=True)
    if 'fetch' in rows:
        name = 'large-pack-fetch'
        problems = []
        seed = out / 'fetch-seed'
        git_out(out, 'clone', '-q', '--no-local', '--single-branch', '--branch=early', remote.as_uri(), str(seed))
        git_out(seed, 'config', 'remote.origin.fetch', '+refs/heads/*:refs/remotes/origin/*')
        # git-config(1): a fetch creates refs/remotes/origin/HEAD by default;
        # den's configured fetch does not (outside this lane), so neither may.
        git_out(seed, 'config', 'remote.origin.followRemoteHEAD', 'never')
        outcomes = {}
        for tool, binary in (('git', git), ('den', str(den))):
            work = out / ('fetch-' + tool)
            shutil.copytree(seed, work, symlinks=True)
            outcomes[tool] = run([binary, 'fetch', '-q', 'origin'], work, name + '-' + tool)
        candidate, oracle = outcomes['den'], outcomes['git']
        compare(name, oracle, candidate, None, None, problems)
        if candidate['exit'] == 0 and oracle['exit'] == 0:
            try:
                git_out(out / 'fetch-den', 'fsck', '--full', '--no-reflogs', timeout=1200)
                views = {}
                for tool in ('git', 'den'):
                    work = out / ('fetch-' + tool)
                    refs = git_out(work, 'for-each-ref', '--format=%(refname) %(objectname)', 'refs/remotes/')
                    ids = sorted({line.split()[0] for line in
                                  git_out(work, 'rev-list', '--objects', '--remotes').splitlines()})
                    views[tool] = dict(refs=refs.decode(), objects=len(ids), objects_sha256=batch_digest(work, ids))
                if views['git'] != views['den']:
                    problems.append('remote-tracking refs or their objects differ: git %r den %r' % (
                        {k: v for k, v in views['git'].items() if k != 'refs'} | dict(refs=views['git']['refs'].split()),
                        {k: v for k, v in views['den'].items() if k != 'refs'} | dict(refs=views['den']['refs'].split())))
            except AssertionError as exc:
                problems.append(str(exc))
        verdict(name, problems, measured_of(candidate, oracle))
        for path in (seed, out / 'fetch-git', out / 'fetch-den'):
            shutil.rmtree(path, ignore_errors=True)
    if 'object-limit' in rows:
        name = 'large-pack-object-limit'
        problems = []
        huge = out / 'huge.git'
        git_out(out, 'init', '-q', '--bare', str(huge))
        git_out(huge, 'symbolic-ref', 'HEAD', 'refs/heads/main')
        sparse = out / 'huge.bin'
        with open(sparse, 'wb') as handle:
            handle.truncate(OBJECT_LIMIT + 1)
        blob = git_out(huge, 'hash-object', '-w', str(sparse), timeout=1200).strip()
        sparse.unlink()
        tree = git_out(huge, 'mktree', data=b'100644 blob ' + blob + b'\thuge.bin\n').strip().decode()
        commit = git_out(huge, 'commit-tree', tree, '-m', 'one blob over the cap').strip().decode()
        git_out(huge, 'update-ref', 'refs/heads/main', commit)
        git_out(huge, 'repack', '-a', '-d', '-q', timeout=1200)
        size = git_out(huge, 'cat-file', '-s', blob.decode()).strip()
        if int(size) != OBJECT_LIMIT + 1:
            problems.append('fixture blob size %s' % size.decode())
        target = out / 'den-huge'
        candidate = run([den, 'clone', '-q', huge.as_uri(), target], out, name + '-den')
        stderr = bytes.fromhex(candidate['stderr'])
        if candidate['exit'] != 128:
            problems.append('exit %d, want 128' % candidate['exit'])
        if stderr != LIMIT_STDERR:
            problems.append('stderr %r, want %r' % (stderr[-300:], LIMIT_STDERR))
        if candidate['stdout']:
            problems.append('stdout not empty')
        if target.exists():
            problems.append('a partial clone was left')
        oracle_dir = out / 'git-huge.git'
        oracle = run([git, 'clone', '-q', '--bare', huge.as_uri(), oracle_dir], out, name + '-git')
        if oracle['exit']:
            problems.append('the pinned Git could not clone the fixture (exit %d)' % oracle['exit'])
        measured = measured_of(candidate, oracle)
        measured.update(object_bytes=OBJECT_LIMIT + 1)
        verdict(name, problems, measured)
        for path in (target, oracle_dir, huge):
            shutil.rmtree(path, ignore_errors=True)
    shutil.rmtree(remote, ignore_errors=True)
    record()
    if failed:
        raise SystemExit('FAIL large-pack: ' + ', '.join(failed))
    print('large-pack: ' + args.tier + ' ' + ','.join(rows) + '; zero skips', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit('FAIL large-pack-harness: ' + str(exc))
