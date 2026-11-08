#!/usr/bin/env python3
"""vc25: a plain clone (no submodules) on every transport, held to the pinned
Git byte for byte, and the work commands in it.

Run through tools/env in the oracle container:

    tools/env python3 -I tools/clone-work-test.py --tier native [--family F]

Families (rows are named FAMILY-CASE-TRANSPORT):
  bytes     the clone itself and a bare clone: every file Git leaves, byte for
            byte (packed-refs, config and its quoting, HEAD, the pack and its
            idx and reverse index, the index, the worktree; no hooks/)
  upstream  switch, checkout (branches, detached, paths) and reset (soft,
            mixed, hard) in the clone, whose main has an upstream: each tool
            clones, then runs the same steps
  refusals  making a tracking branch, from a remote-tracking start point or
            by guessing a remote's branch: den alone, refused by name (exit 2,
            nothing changed)

Transports: a plain local path, file://, git:// (the pinned git daemon), ssh
(a local stand-in that drops the client's options and the host and runs the
remote command through /bin/sh) and https (the pinned OpenSSL terminator in
front of the pinned git-http-backend, tools/http-git-test.py's fixture).
These fixtures are vc24's (tools/wire-gaps-test.py), by value.

Every row runs Git's steps in a fresh copy of the world, then den's in another
copy at the same path, and compares every step's exit status, stdout and
stderr and the complete world afterwards. Loose objects compare by inflated
bytes; an index compares byte for byte except the timing and identity words
each tool proves against its own lstat (tools/index-proof.py). The only named
difference is den's reflog identity: a row whose only differences are reflog
files under logs/ is KNOWN, never counted as parity.

--field runs against a Git that is not the pinned one (the macOS leg); https
needs the Linux container's pinned OpenSSL and is excluded there by name.
Sources: git-clone(1), git-switch(1), git-checkout(1), git-reset(1),
git-config(1), gitrepository-layout(5) of Git v2.56.0. No Git source.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import socket
import subprocess
import time
import zlib

PINNED = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
TRANSPORTS = ('local', 'file', 'git', 'ssh', 'https')
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
LOOSE = re.compile(r'(^|/)objects/[0-9a-f]{2}/[0-9a-f]{38}$')
LOGS = re.compile(r'(^|/)(\.git|[^/]+\.git)/logs(/|$)')

p = argparse.ArgumentParser()
p.add_argument('--tier', choices=('native', 'release'), default='native')
p.add_argument('--family', default='bytes,upstream,refusals')
p.add_argument('--field', action='store_true')
p.add_argument('--only', default='')
a = p.parse_args()
R = Path(__file__).resolve().parent.parent
G = Path(os.environ['DEN_GIT']).resolve()
if not a.field:
    assert hashlib.sha256(G.read_bytes()).hexdigest() == PINNED, 'not the pinned oracle'
D = R / 'target' / a.tier / 'den'
assert D.is_file(), 'build target/%s/den first' % a.tier
out = R / 'target/runs' / ('clone-work-' + a.tier)
if out.exists():
    shutil.rmtree(out)
(out / 'bin').mkdir(parents=True)
(out / 'bin/ssh').write_text(SSH_STANDIN)
(out / 'bin/ssh').chmod(0o755)
srv = out / 'srv'
srv.mkdir()
world = out / 'world'
proof = runpy.run_path(str(R / 'tools/index-proof.py'))
env = dict(os.environ)
env.update(PATH=str(out / 'bin') + ':' + env['PATH'], GIT_SSH_VARIANT='ssh', GIT_TERMINAL_PROMPT='0',
           GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='protocol.version', GIT_CONFIG_VALUE_0='2')
rows = []
daemon = https = None
port = 0


def g(*argv, cwd):
    q = subprocess.run([str(G), *map(str, argv)], cwd=str(cwd), env=env, capture_output=True, timeout=300)
    assert q.returncode == 0, (argv, q.stderr[-300:])
    return q.stdout.decode()


def run(exe, argv, cwd):
    q = subprocess.run([str(exe), *map(str, argv)], cwd=str(cwd), env=env, capture_output=True, timeout=300,
                       stdin=subprocess.DEVNULL)
    return dict(status=q.returncode, stdout=q.stdout.decode('utf-8', 'backslashreplace'),
                stderr=q.stderr.decode('utf-8', 'backslashreplace'))


def state(path):
    result = {}
    for f in sorted(path.rglob('*')):
        rel = f.relative_to(path).as_posix()
        if f.is_symlink():
            result[rel] = ['symlink', os.readlink(f)]
        elif f.is_file():
            raw = f.read_bytes()
            if LOOSE.search(rel):
                result[rel] = ['loose', f.stat().st_mode & 0o7777, zlib.decompress(raw).hex()]
            else:
                result[rel] = [f.stat().st_mode & 0o7777, raw.hex()]
        elif f.is_dir():
            result[rel] = ['directory', f.stat().st_mode & 0o7777]
    return result


def indexes(base):
    found = {}
    for f in base.rglob('index'):
        if f.is_file() and f.parent.name == '.git':
            raw = f.read_bytes()
            found[f.relative_to(base).as_posix()] = (raw, proof['proof'](f.parent.parent, raw))
    return found


def shown(value):
    if value is None or value[0] in ('directory', 'symlink'):
        return value
    raw = bytes.fromhex(value[-1])
    try:
        return [value[0], raw.decode('utf-8')[:1500]]
    except UnicodeDecodeError:
        return [value[0], raw.hex()[:1500]]


def compare(name, steps):
    """STEPS: (argv, cwd relative to the world) pairs, run by each tool in a
    fresh empty world."""
    if a.only and not re.search(a.only, name):
        return
    outcomes = []
    for exe in (G, D):
        if world.exists():
            shutil.rmtree(world)
        world.mkdir()
        results = [run(exe, argv, world / cwd) for argv, cwd in steps]
        outcomes.append(dict(results=results, after=state(world), indexes=indexes(world)))
    left, right = outcomes
    if a.field:
        # macOS only: Git probes the case-insensitive file system and writes
        # two core lines the Linux oracle never writes; field mode drops them
        # from both sides (as tools/submodule-test.py does).
        drop = b'\tignorecase = true\n\tprecomposeunicode = true\n'.hex()
        for side in (left, right):
            for key, value in side['after'].items():
                if key.endswith('config') and value[0] != 'directory' and drop in value[1]:
                    side['after'][key] = [value[0], value[1].replace(drop, '')]
    index_errors = []
    for key in sorted(set(left['indexes']) & set(right['indexes'])):
        (lraw, lproof), (rraw, rproof) = left['indexes'][key], right['indexes'][key]
        if lraw == rraw:
            continue
        try:
            lc, rc, _ = proof['canonical_pair'](lraw, rraw, lproof, rproof)
            left['after'][key] = [left['after'][key][0], lc.hex()]
            right['after'][key] = [right['after'][key][0], rc.hex()]
        except ValueError as error:
            index_errors.append(key + ': ' + str(error))
    same_results = left['results'] == right['results']
    differing = sorted(k for k in left['after'].keys() | right['after'].keys()
                       if left['after'].get(k) != right['after'].get(k))
    ok = same_results and not differing and not index_errors
    known = (not ok and same_results and not index_errors and differing
             and all(LOGS.search(k) for k in differing))
    details = {} if ok or known else {
        k: [shown(left['after'].get(k)), shown(right['after'].get(k))]
        for k in [k for k in differing if not LOGS.search(k)][:4]}
    rows.append(dict(name=name, steps=[s[0] for s in steps], equal=ok, known=known,
                     expected=left['results'], actual=right['results'], differing_paths=differing,
                     index_errors=index_errors, details=details))
    verdict = 'PASS' if ok else 'KNOWN' if known else 'FAIL'
    print(verdict, name + ((' reflog-paths=' + ','.join(differing)) if known else ''), flush=True)
    if verdict == 'FAIL':
        for i, (l, r) in enumerate(zip(left['results'], right['results'])):
            if l != r:
                print('  step', i, steps[i][0], flush=True)
                print('  expected', json.dumps(l), flush=True)
                print('  actual  ', json.dumps(r), flush=True)
        print('  differing_paths', differing[:12], 'index_errors', index_errors, flush=True)
        for k, (l, r) in details.items():
            print('  git', k, l, flush=True)
            print('  den', k, r, flush=True)


def exclude(name, reason):
    if a.only and not re.search(a.only, name):
        return
    rows.append(dict(name=name, equal=False, known=False, excluded=reason))
    print('EXCLUDED', name, 'reason=' + reason, flush=True)


# ---- fixtures ------------------------------------------------------------

def remote(name):
    """A bare remote: main with three commits (the last two change a.txt),
    a branch feature, an annotated tag v1."""
    path = srv / name
    src = out / ('src-' + name)
    g('init', '-q', '--bare', '-b', 'main', str(path), cwd=out)
    g('init', '-q', '-b', 'main', str(src), cwd=out)
    for i, text in enumerate(('one\n', 'one\ntwo\n', 'one\ntwo\nthree\n')):
        (src / 'a.txt').write_text(text)
        if i == 0:
            (src / 'b.txt').write_text('b\n')
            g('add', 'a.txt', 'b.txt', cwd=src)
        else:
            g('add', 'a.txt', cwd=src)
        g('commit', '-q', '-m', 'commit %d' % (i + 1), cwd=src)
        if i == 0:
            g('tag', '-a', '-m', 'first', 'v1', cwd=src)
            g('branch', 'feature', cwd=src)
    g('push', '-q', '--tags', str(path), 'main', 'feature', cwd=src)
    for key, value in (('gc.auto', '0'), ('maintenance.auto', 'false')):
        g('config', key, value, cwd=path)
    return path


def start_daemon():
    global daemon, port
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    daemon = subprocess.Popen([str(G), 'daemon', '--reuseaddr', '--export-all', '--listen=127.0.0.1',
                               '--port=' + str(port), '--base-path=' + str(srv), str(srv)], env=env,
                              stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        assert daemon.poll() is None, 'git daemon exited at startup'
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise AssertionError('git daemon startup timeout')


def start_https():
    global https
    fixture = runpy.run_path(str(R / 'tools/http-git-test.py'))
    for path, digest in fixture['OPENSSL_PINS'].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest, 'pinned TLS oracle digest'
    pki = out / 'pki'
    pki.mkdir()

    def openssl(*argv):
        q = subprocess.run(['/usr/bin/openssl', *map(str, argv)], env=env, capture_output=True, timeout=120)
        assert q.returncode == 0, 'fixture openssl ' + str(argv[0])

    openssl('req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-sha256', '-days', '2',
            '-subj', '/CN=Clone work fixture root', '-addext', 'basicConstraints=critical,CA:TRUE',
            '-addext', 'keyUsage=critical,keyCertSign,cRLSign', '-keyout', pki / 'ca.key', '-out', pki / 'ca.pem')
    openssl('x509', '-in', pki / 'ca.pem', '-outform', 'DER', '-out', pki / 'ca.der')
    (pki / 'leaf.cnf').write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n'
                                  'extendedKeyUsage=serverAuth\nsubjectAltName=DNS:localhost\n')
    openssl('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=localhost',
            '-keyout', pki / 'leaf.key', '-out', pki / 'leaf.csr')
    openssl('x509', '-req', '-in', pki / 'leaf.csr', '-CA', pki / 'ca.pem', '-CAkey', pki / 'ca.key',
            '-CAcreateserial', '-days', '1', '-sha256', '-extfile', pki / 'leaf.cnf', '-out', pki / 'leaf.pem')
    root = out / 'https-root'
    root.mkdir()
    (root / 'remote.git').symlink_to(srv / 'name.git')
    https = fixture['Server'](root, str(G), env, 'tls', pki, '', lambda data: None)
    env.update(GIT_SSL_CAINFO=str(pki / 'ca.pem'), DEN_TLS_ROOTS=str(pki / 'ca.der'))


def url(transport, repo):
    if transport == 'local':
        return str(repo)
    if transport == 'file':
        return repo.as_uri()
    if transport == 'git':
        return 'git://127.0.0.1:%d/%s' % (port, repo.relative_to(srv).as_posix())
    if transport == 'ssh':
        return 'ssh://localhost' + str(repo)
    return https.url


def transports():
    return TRANSPORTS


# ---- families ------------------------------------------------------------

def family_bytes():
    for t in transports():
        if t == 'https' and a.field:
            for case in ('clone', 'clone-bare'):
                exclude('bytes-%s-%s' % (case, t), 'field leg: no pinned OpenSSL')
            continue
        u = url(t, srv / 'name.git')
        compare('bytes-clone-' + t, [(['clone', u, 'c'], '.')])
        compare('bytes-clone-bare-' + t, [(['clone', '--bare', u, 'c.git'], '.')])
    # A URL that config must quote: a path holding '#' and ';'.
    odd = srv / 'odd#name;x.git'
    if not odd.exists():
        shutil.copytree(srv / 'name.git', odd, symlinks=True)
    compare('bytes-clone-quoted-local', [(['clone', str(odd), 'c'], '.')])


UPSTREAM = {
    'switch-create': [['switch', '-c', 'topic', 'HEAD~1']],
    'switch-back': [['switch', '-c', 'topic', 'HEAD~1'], ['switch', 'main']],
    'switch-detach': [['switch', '--detach', 'HEAD~1'], ['switch', 'main']],
    'switch-behind': [['reset', '-q', '--hard', 'HEAD~1'], ['switch', '-c', 'topic'], ['switch', 'main']],
    'switch-ahead': [['switch', '-c', 'topic', 'HEAD~1'], ['switch', 'main'], ['commit', '-q', '--allow-empty', '-m', 'local'],
                     ['switch', 'topic'], ['switch', 'main']],
    'checkout-branch': [['checkout', '-b', 'topic', 'HEAD~1'], ['checkout', 'main']],
    'checkout-same': [['checkout', 'main']],
    'checkout-detach': [['checkout', 'HEAD~1'], ['checkout', 'main']],
    'checkout-behind': [['reset', '-q', '--hard', 'HEAD~2'], ['checkout', 'main']],
    'checkout-paths': [['checkout', 'HEAD~1', '--', 'a.txt'], ['status'], ['checkout', 'HEAD', '--', 'a.txt'],
                       ['status', '--porcelain']],
    'checkout-path-dot': [['checkout', 'HEAD~2', '--', '.'], ['status', '-s']],
    'reset-soft': [['reset', '--soft', 'HEAD~1'], ['status']],
    'reset-mixed': [['reset', 'HEAD~1'], ['status']],
    'reset-hard': [['reset', '--hard', 'HEAD~1'], ['status']],
    'reset-hard-back': [['reset', '--hard', 'HEAD~1'], ['reset', '--hard', 'origin/main'], ['status']],
}


def family_upstream():
    for t in transports():
        for case in UPSTREAM:
            name = 'upstream-%s-%s' % (case, t)
            if t == 'https' and a.field:
                exclude(name, 'field leg: no pinned OpenSSL')
                continue
            steps = [(['clone', '-q', url(t, srv / 'name.git'), 'c'], '.')]
            steps += [(argv, 'c') for argv in UPSTREAM[case]]
            compare(name, steps)


REFUSALS = {
    'checkout-b-remote': ['checkout', '-b', 'x', 'origin/main'],
    'checkout-b-remote-full': ['checkout', '-b', 'x', 'refs/remotes/origin/feature'],
    'switch-c-remote': ['switch', '-c', 'x', 'origin/feature'],
    'checkout-guess': ['checkout', 'feature'],
    'switch-guess': ['switch', 'feature'],
}


def family_refusals():
    for t in transports():
        for case, argv in REFUSALS.items():
            name = 'refusal-%s-%s' % (case, t)
            if a.only and not re.search(a.only, name):
                continue
            if t == 'https' and a.field:
                exclude(name, 'field leg: no pinned OpenSSL')
                continue
            if world.exists():
                shutil.rmtree(world)
            world.mkdir()
            g('clone', '-q', url(t, srv / 'name.git'), 'c', cwd=world)
            before = state(world)
            q = run(D, argv, world / 'c')
            ok = q['status'] == 2 and 'not yet implemented' in q['stderr'] and state(world) == before
            rows.append(dict(name=name, steps=[argv], equal=ok, known=False, refusal=True, actual=[q]))
            print('PASS' if ok else 'FAIL', name, '' if ok else json.dumps(q), flush=True)


FAMILIES = {'bytes': family_bytes, 'upstream': family_upstream, 'refusals': family_refusals}
families = a.family.split(',')
assert families and set(families) <= set(FAMILIES), 'families'
try:
    remote('name.git')
    start_daemon()
    if not a.field:
        start_https()
    for family in families:
        FAMILIES[family]()
finally:
    if daemon:
        daemon.terminate()  # this fixture's pid only
        daemon.wait(timeout=30)
    if https:
        https.close()
    (R / 'target/runs').mkdir(parents=True, exist_ok=True)
    (R / 'target/runs' / ('clone-work-' + a.tier + '.json')).write_text(
        json.dumps(dict(rows=rows, field=a.field), indent=1) + '\n')
if https and https.errors:
    print('FAIL clone-work-https-fixture ' + ', '.join(https.errors), flush=True)
    raise SystemExit(1)
exact = sum(r['equal'] for r in rows)
known = sum(r['known'] for r in rows)
excluded = sum(bool(r.get('excluded')) for r in rows)
failed = len(rows) - exact - known - excluded
print('clone-work %s %s exact=%d known=%d failed=%d rows=%d%s%s' % (
    a.tier, a.family, exact, known, failed, len(rows), ' excluded=%d' % excluded if excluded else '',
    ' FIELD' if a.field else ''), flush=True)
raise SystemExit(0 if rows and failed == 0 else 1)
