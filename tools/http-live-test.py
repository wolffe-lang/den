#!/usr/bin/env python3
"""Live smart-HTTP rows against github.com: read-only, never credentials.

http-live-read: den and the pinned Git clone the same small public repository
over https, each against the distribution's root bundle; process bytes and
status, refs, HEAD, reachable canonical objects, worktree and remote config
are compared, and the pinned Git checks den's clone (fsck, status).

http-live-self: den and the pinned Git clone den's own public repository
(a pack over 300 MB, over the old 140,000,000-byte wire cap, den#61) and
compare as the read row does, within the time and the peak RSS predicted in
tests/vc23-prediction.txt; the pinned Git checks den's clone.

Others push to these repositories at any time, so the read, identity and
self rows compare what held still (pair, judge): `ls-remote --symref` before
and after the two clones names the refs that moved. If HEAD or the branch it
names moved, the clones' checkouts differ for reasons not den's, and the row
runs once more (`RETRY <row> moved=<refs>`); a second such move is a FAIL.
Any other moved branch or tag is left out of the comparison, its refs and
the objects only it reaches, and named on a `NARROWED <row> excluded=<refs>`
line and in the LIVE line's `excluded` list, so a reader sees when a row was
narrowed. tools/submodule-live-test.py's clone rows use the same judge.

http-live-identity: den and the pinned Git clone i3's public repository,
whose commit 5f453914 has an empty email (`walker0643 <>`, author and
committer), and compare as the read row does; then `log -1`, `show -s` and
the identity placeholders of that commit, byte for byte. Before vc26 den
refused the clone (`Unsupported(fsck identity diagnostics)`).

http-live-push: with DEN_LIVE_HTTPS_URL and DEN_LIVE_HTTPS_TOKEN, den fetches
that repository with the token through a remote named only in GIT_CONFIG_*
after `den init`, pushes a fresh disposable branch, the server's own ref
advertisement (read by the pinned OpenSSL client) shows it, den deletes it and
the advertisement shows it gone. The token lives only in the environments of
the processes that use it, and the request carrying it on the OpenSSL
client's stdin; the URL is never printed or recorded, and never on a child's
argv: http-live-argv reads every descendant's /proc/<pid>/cmdline while the
row runs, with a control argv it must see. Every retained output is scanned
for the token.

Every row SKIPs by name when github.com:443 is unreachable or when no
distribution root bundle exists; the push row also without its variables. Run through tools/env in the oracle
container. PEM is decoded per RFC 7468 here; no TLS library is imported.

Stalls (den#118's gate side): when a clone in the read, identity or self
row makes no progress for STALL_SECONDS (300 s, or DEN_LIVE_STALL_SECONDS),
or for half its own time bound when that is shorter, the row stops it (its
own child's pid) and runs that tool's clone once more, printing `RETRY
<row> <tool> no-progress-for=<s>s`; the LIVE line counts the retries.
Progress is growth in the clone directory's bytes or in the read bytes of
the clone's process tree (/proc/PID/io rchar). A second stall is `FAIL
<row> <tool>: the remote sent nothing for <s> s twice`. --self-url,
--self-seconds and --output aim the self row at another repository
(tools/http-live-stall-test.py's local server).

Unreachable: when a read by the pinned Git in a clone row (the listing
before, its clone, the listing after) fails because the host could not be
reached, Git's `unable to access` line naming a failed name lookup or
connect, the row waits UNREACHABLE_PAUSE (60 s, or
DEN_LIVE_UNREACHABLE_PAUSE) and runs once more, printing `RETRY <row>
unreachable=<reads>`; the LIVE line counts it. A second such failure is
`FAIL <row> pinned Git could not reach <repository> twice: <reads>`, with
no third attempt. Only the pinned Git's reads decide: a den clone that
fails while Git's reads succeed is a difference, never a reason to rerun.
tools/submodule-live-test.py's clone rows use the same rule.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import runpy
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit

GIT_SHA256 = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
READ_URL = 'https://github.com/wolffe-lang/burrow.git'
IDENTITY_URL = 'https://github.com/i3/i3.git'
IDENTITY_COMMIT = '5f453914a04c193baf5b4239d83116d33a74de62'
IDENTITY_SECONDS = 900
SELF_URL = 'https://github.com/wolffe-lang/den.git'
# tests/vc23-prediction.txt P2: 64 MiB + W (96 MiB) + 5 x den's largest object.
SELF_RSS_KIB = (160 * 1024 * 1024 + 5 * 103002444) // 1024
SELF_SECONDS = 1800
READ_SECONDS = 300
# A clone with no progress for this long is stopped and retried once
# (stall_bound); measured clean self clones took den 152-274 s and the
# pinned Git 66-176 s in total.
STALL_SECONDS = int(os.environ.get('DEN_LIVE_STALL_SECONDS') or 300)
SECRETS = ('DEN_HTTP_TOKEN', 'DEN_HTTP_USER', 'DEN_LIVE_HTTPS_URL', 'DEN_LIVE_HTTPS_TOKEN',
           'GIT_ASKPASS', 'SSH_ASKPASS', 'DEN_TLS_ROOTS', 'GIT_SSL_CAINFO', 'GIT_SSL_CAPATH')


def cloned(listing):
    """The lines of an `ls-remote` listing (hex stdout) a clone takes: HEAD,
    branches and tags (with their peeled lines)."""
    keep = []
    for line in bytes.fromhex(listing).split(b'\n'):
        name = line.split(b'\t', 1)[1] if b'\t' in line else b''
        if name == b'HEAD' or name.startswith(b'refs/heads/') or name.startswith(b'refs/tags/'):
            keep.append(line)
    return keep


def moved(before, after):
    """Whether what a clone takes moved between two `ls-remote` listings (hex
    stdout): GitHub's refs/pull/* are no clone's, and change on their own."""
    return cloned(before) != cloned(after)


def ref_table(listing):
    """An `ls-remote --symref` listing (hex stdout) as {ref: id} over what a
    clone takes (HEAD, branches, tags; a tag's peeled line is its tag's), and
    the branch HEAD names, or None."""
    refs, target = {}, None
    for line in cloned(listing):
        value, name = line.split(b'\t', 1)
        name = name.decode('utf-8', 'surrogateescape')
        if value.startswith(b'ref: '):
            target = value[5:].decode('utf-8', 'surrogateescape')
        elif not name.endswith('^{}'):
            refs[name] = value.decode()
    return refs, target


def drift(*tables):
    """The refs whose ids are not the same in every table (absent counts)."""
    return sorted(name for name in set().union(*tables) if len({table.get(name) for table in tables}) > 1)


def held(before, after):
    """Two `ls-remote --symref` listings (hex stdout) as (held, moved,
    critical) ref names: critical is the part of moved that is HEAD or the
    branch HEAD names in either listing (a changed symref moves HEAD)."""
    (first, head_before), (second, head_after) = ref_table(before), ref_table(after)
    moved = drift(first, second)
    if head_before != head_after and 'HEAD' not in moved:
        moved = sorted(moved + ['HEAD'])
    critical = {'HEAD', head_before, head_after} - {None}
    return ([name for name in sorted(set(first) | set(second)) if name not in moved], moved,
            [name for name in moved if name in critical])


# Git's words, from curl, for a host it could not reach: a failed name lookup or connect.
UNREACHABLE_WORDS = ('Could not resolve host', 'Resolving timed out', 'Failed to connect to',
                     "Couldn't connect to server", 'Connection refused', 'Connection timed out',
                     'Network is unreachable')
UNREACHABLE_PAUSE = int(os.environ.get('DEN_LIVE_UNREACHABLE_PAUSE') or 60)


def out_of_reach(reads):
    """The labels of reads, (label, exit status, stderr text) of the pinned
    Git's, that failed because the host could not be reached: a nonzero exit
    and an `unable to access` line naming a failed lookup or connect. Each
    label once, in order."""
    lost = []
    for label, code, err in reads:
        if code and 'unable to access' in err and any(words in err for words in UNREACHABLE_WORDS) \
                and label not in lost:
            lost.append(label)
    return lost


def rerun_unreachable(name, lost):
    """The one rerun after the pinned Git could not reach the host: a RETRY
    line naming its failed reads, then UNREACHABLE_PAUSE seconds."""
    print('RETRY %s unreachable=%s' % (name, ','.join(lost)), flush=True)
    time.sleep(0)


def unreachable_selftest():
    """The rule on the words Git wrote in a record's outage (2026-11-22), and
    on failures that are not the host's absence."""
    outage = [
        "fatal: unable to access 'https://github.com/i3/i3.git/': Failed to connect to github.com port 443 after "
        "19603 ms: Couldn't connect to server\n",
        "fatal: unable to access 'https://github.com/i3/i3.git/': Could not resolve host: github.com\n",
        "fatal: unable to access 'http://127.0.0.1:41835/remote.git/': Failed to connect to 127.0.0.1 port 41835 "
        "after 0 ms: Couldn't connect to server\n"]
    others = [
        "fatal: unable to access 'https://github.com/x/y.git/': The requested URL returned error: 500\n",
        "fatal: unable to access 'https://github.com/x/y.git/': SSL certificate problem: unable to get local issuer "
        "certificate\n",
        "remote: Repository not found.\nfatal: repository 'https://github.com/x/y.git/' not found\n",
        "fatal: early EOF\nfatal: fetch-pack: invalid index-pack output\n"]
    reads = [('r%d' % i, 128, err) for i, err in enumerate(outage + others)]
    reads += [('ok', 0, outage[0]), ('r0', 128, outage[1])]
    got = out_of_reach(reads)
    if got != ['r0', 'r1', 'r2']:
        raise SystemExit('FAIL http-live-unreachable-rule: %r' % got)


def judge(name, moved, critical, attempt):
    """What a clone row does about the refs that moved while it ran:
    'retry' when HEAD or its branch moved on the first attempt (a RETRY
    line), 'fail' when they moved again, else 'compare' over what held still,
    naming the rest on a NARROWED line."""
    if critical:
        if attempt == 0:
            print('RETRY %s moved=%s' % (name, ','.join(critical)), flush=True)
            return 'retry'
        return 'fail'
    if moved:
        print('NARROWED %s excluded=%s' % (name, ','.join(moved)), flush=True)
    return 'compare'


def guard_selftest():
    """The guard holds what a clone takes. A change GitHub makes outside it
    (refs/pull/*, which no clone fetches) must not count as moved; a branch or
    tag that moves must."""
    base = b'1111111111111111111111111111111111111111\tHEAD\n' \
        b'1111111111111111111111111111111111111111\trefs/heads/main\n' \
        b'2222222222222222222222222222222222222222\trefs/pull/1/head\n' \
        b'3333333333333333333333333333333333333333\trefs/tags/v1\n'
    pull = base.replace(b'2222222222222222222222222222222222222222', b'4444444444444444444444444444444444444444') + \
        b'5555555555555555555555555555555555555555\trefs/pull/2/head\n'
    branch = base + b'6666666666666666666666666666666666666666\trefs/heads/lane\n'
    tag = base.replace(b'3333333333333333333333333333333333333333', b'7777777777777777777777777777777777777777')
    problems = []
    if moved(base.hex(), pull.hex()):
        problems.append('a refs/pull change counts as moved')
    if not moved(base.hex(), branch.hex()):
        problems.append('a new branch does not count as moved')
    if not moved(base.hex(), tag.hex()):
        problems.append('a moved tag does not count as moved')
    symref = b'ref: refs/heads/main\tHEAD\n' + base
    cases = (
        ('nothing moved', symref, ([], [])),
        ('a pull ref', symref.replace(b'2222222222222222222222222222222222222222', b'4444444444444444444444444444444444444444'),
         ([], [])),
        ('a new branch', symref + b'6666666666666666666666666666666666666666\trefs/heads/lane\n', (['refs/heads/lane'], [])),
        ('a deleted tag beside a new branch', symref.replace(b'3333333333333333333333333333333333333333\trefs/tags/v1\n', b'')
         + b'8888888888888888888888888888888888888888\trefs/heads/gone\n', (['refs/heads/gone', 'refs/tags/v1'], [])),
        ('a moved tag', symref.replace(b'3333333333333333333333333333333333333333', b'7777777777777777777777777777777777777777'),
         (['refs/tags/v1'], [])),
        ('the default branch', symref.replace(b'1111111111111111111111111111111111111111\trefs/heads/main',
                                              b'9999999999999999999999999999999999999999\trefs/heads/main'),
         (['refs/heads/main'], ['refs/heads/main'])),
    )
    for label, after, want in cases:
        _, gone, critical = held(symref.hex(), after.hex())
        if (gone, critical) != want:
            problems.append('%s: moved %r critical %r, not %r' % (label, gone, critical, want))
    took = {'refs/heads/main': '1' * 40, 'refs/heads/side': '2' * 40}
    later = {'refs/heads/main': '1' * 40, 'refs/heads/side': '3' * 40, 'refs/heads/fresh': '3' * 40}
    if drift(took, later, later) != ['refs/heads/fresh', 'refs/heads/side']:
        problems.append('a clone that took an older side and no fresh does not drift from later listings')
    if drift(took, dict(took), dict(took)):
        problems.append('identical tables drift')
    print(('PASS ' if not problems else 'FAIL ') + 'http-live-guard' + ('' if not problems else ' ' + '; '.join(problems)),
          flush=True)
    if problems:
        raise SystemExit(1)


def pem_roots(path):
    """Concatenated DER from a PEM bundle, strictly per RFC 7468 section 2."""
    text = path.read_bytes()
    begin, end = b'-----BEGIN CERTIFICATE-----', b'-----END CERTIFICATE-----'
    out, count, pos = bytearray(), 0, 0
    while True:
        start = text.find(begin, pos)
        if start < 0:
            break
        stop = text.find(end, start)
        if stop < 0:
            raise ValueError('unterminated PEM certificate')
        body = b''.join(text[start + len(begin):stop].split())
        der = base64.b64decode(body, validate=True)
        if len(der) < 2 or der[0] != 0x30:
            raise ValueError('PEM block is not a DER SEQUENCE')
        out.extend(der)
        count += 1
        pos = stop + len(end)
    if not count:
        raise ValueError('no certificates in bundle')
    return bytes(out), count


def stall_bound(timeout):
    """den#118's gate side: a clone that receives nothing for this long has
    stalled. STALL_SECONDS, or half the clone's own time bound when that is
    shorter, so the stall is seen before the bound ends the clone."""
    return min(STALL_SECONDS, max(1, timeout // 2))


def stall_problem(tool, bound):
    return '%s: the remote sent nothing for %d s twice' % (tool, bound)


def descendants(root):
    """root and every live process below it (proc(5) stat, field 4)."""
    parents = {}
    for entry in os.listdir('/proc') if os.path.isdir('/proc') else ():
        if entry.isdigit():
            try:
                with open('/proc/' + entry + '/stat', 'rb') as handle:
                    stat = handle.read()
            except OSError:
                continue
            parents[int(entry)] = int(stat[stat.rfind(b')') + 2:].split()[1])
    found, frontier = [root], [root]
    while frontier:
        frontier = [pid for pid, parent in parents.items() if parent in frontier and pid not in found]
        found.extend(frontier)
    return found


def read_bytes(root):
    """Bytes the read calls of root and its live descendants returned
    (proc(5) /proc/PID/io rchar; a reaped child's count is its parent's).
    0 where there is no /proc."""
    total = 0
    for pid in descendants(root):
        try:
            with open('/proc/%d/io' % pid, 'rb') as handle:
                for line in handle:
                    if line.startswith(b'rchar:'):
                        total += int(line.split()[1])
        except (OSError, ValueError):
            continue
    return total


def tree_bytes(path):
    """The sizes of every file below path (0 before the clone makes it)."""
    total = 0
    for dirpath, dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(dirpath, name)).st_size
            except OSError:
                pass
    return total


def reap(child, timeout, target=None):
    """Wait for child by wait4 and stop it (SIGTERM, then SIGKILL 10 s later;
    this child's pid only, never a group) when its time bound ends or, with a
    target (a clone's destination), when neither the target's bytes nor the
    child's read bytes have grown for stall_bound(timeout) seconds. Returns
    the wait4 status and rusage, whether it timed out or stalled, and the
    longest time it went without growth."""
    started = time.monotonic()
    stall, deadline, kill_at = stall_bound(timeout), started + timeout, None
    timed_out = stalled = False
    last, grew, sampled, quiet = None, started, 0.0, 0.0
    while True:
        pid, status, usage = os.wait4(child.pid, os.WNOHANG)
        if pid:
            return status, usage, timed_out, stalled, round(quiet, 1)
        now = time.monotonic()
        if target is not None and kill_at is None and now - sampled >= min(1.0, stall / 4):
            sampled = now
            mark = (tree_bytes(target), read_bytes(child.pid))
            if last is None or mark[0] > last[0] or mark[1] > last[1]:
                grew = now
            last = mark
            quiet = max(quiet, now - grew)
            stalled = now - grew >= stall
        if kill_at is None and (stalled or now >= deadline):
            timed_out = not stalled
            kill_at = now + 10
            os.kill(child.pid, signal.SIGTERM)  # This child's pid only, never a group.
        elif kill_at is not None and now >= kill_at:
            os.kill(child.pid, signal.SIGKILL)
            kill_at = float('inf')
        time.sleep(0.05)


def watched(attempt, target, timeout, row, tool):
    """attempt(suffix) runs one clone into target and returns its capture.
    After a stall the row stops it, removes what it left, prints RETRY and
    runs that tool's clone once more. The capture carries retries (0 or 1)
    and stalls (0, 1 or 2)."""
    capture = attempt('')
    capture.update(retries=0, stalls=int(capture['stalled']))
    if not capture['stalled']:
        return capture
    print('RETRY %s %s no-progress-for=%ds' % (row, tool, stall_bound(timeout)), flush=True)
    shutil.rmtree(target, ignore_errors=True)
    second = attempt('-retry')
    second.update(retries=1, stalls=1 + int(second['stalled']))
    return second


def endpoint(url):
    """The host and port a URL's requests connect to."""
    parts = urlsplit(url)
    return parts.hostname, parts.port or (443 if parts.scheme == 'https' else 80)


def reachable(host, port, timeout=10):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return ''
    except OSError as exc:
        return type(exc).__name__


class ArgvWatch:
    """R-vc22b-1 (a): read /proc/<pid>/cmdline of every descendant of this
    process while a row runs, and count each argv holding a secret needle (the
    fixture's URL, its path or the token). Needles are never printed. A
    synthetic control child proves the watcher sees an argv it should."""
    CONTROL = b'den-live-argv-control-' + secrets.token_hex(8).encode()

    def __init__(self, needles):
        self.needles = [needle for needle in needles if needle] + [self.CONTROL]
        self.stop = threading.Event()
        self.seen, self.hits, self.control = set(), set(), False
        self.thread = threading.Thread(target=self.loop, name='argv-watch', daemon=True)

    def descendants(self):
        me, parents = os.getpid(), {}
        for entry in os.listdir('/proc'):
            if not entry.isdigit():
                continue
            try:
                with open('/proc/' + entry + '/stat', 'rb') as handle:
                    stat = handle.read()
            except OSError:
                continue
            parents[int(entry)] = int(stat[stat.rfind(b')') + 2:].split()[1])
        out = []
        for pid in parents:
            node = pid
            for _ in range(64):
                node = parents.get(node)
                if node is None:
                    break
                if node == me:
                    out.append(pid)
                    break
        return out

    def loop(self):
        while not self.stop.is_set():
            for pid in self.descendants():
                try:
                    with open('/proc/%d/cmdline' % pid, 'rb') as handle:
                        argv = handle.read()
                except OSError:
                    continue
                if not argv:
                    continue
                self.seen.add(pid)
                for needle in self.needles:
                    if needle in argv:
                        if needle == self.CONTROL:
                            self.control = True
                        else:
                            self.hits.add(pid)
            self.stop.wait(0.005)

    def __enter__(self):
        self.thread.start()
        control = subprocess.Popen([sys.executable, '-I', '-c', 'import time; time.sleep(0.5)',
                                    self.CONTROL.decode()], stdin=subprocess.DEVNULL)
        control.wait(timeout=30)
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    parser.add_argument('--rows', default='read,identity,self,push')
    # tools/http-live-stall-test.py aims the self row at its local server.
    parser.add_argument('--self-url', default=SELF_URL)
    parser.add_argument('--self-seconds', type=int, default=SELF_SECONDS)
    parser.add_argument('--output', default='', help='a fresh directory (default target/runs/http-live-TIER)')
    args = parser.parse_args()
    rows = args.rows.split(',')
    assert set(rows) <= {'read', 'identity', 'self', 'push'} and rows, 'rows'
    guard_selftest()
    unreachable_selftest()
    root = Path(__file__).resolve().parent.parent
    git = str(Path(os.environ['DEN_GIT']).resolve())
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == GIT_SHA256, 'pinned Git digest'
    den = root / 'target' / args.tier / 'den'
    if not den.is_file():
        raise SystemExit('FAIL http-live-input: build target/' + args.tier + '/den first')
    names = {'read': 'http-live-read', 'identity': 'http-live-identity', 'self': 'http-live-self',
             'push': 'http-live-push'}
    live_url = os.environ.get('DEN_LIVE_HTTPS_URL', '')
    live_token = os.environ.get('DEN_LIVE_HTTPS_TOKEN', '')
    if 'push' in rows and not (live_url and live_token):
        print('SKIP http-live-push reason=DEN_LIVE_HTTPS_URL and DEN_LIVE_HTTPS_TOKEN not both set', flush=True)
        rows = [row for row in rows if row != 'push']
        if not rows:
            return
    if 'push' in rows and not live_url.startswith('https://'):
        raise SystemExit('FAIL http-live-push: DEN_LIVE_HTTPS_URL must be an https URL (value withheld)')
    pem = Path(os.environ.get('DEN_LIVE_ROOTS_PEM', '/etc/ssl/certs/ca-certificates.crt'))
    if not pem.is_file():
        for row in rows:
            print('SKIP ' + names[row] + ' reason=no distribution root bundle', flush=True)
        return
    urls = {'read': READ_URL, 'identity': IDENTITY_URL, 'self': args.self_url, 'push': live_url}
    for host, port in sorted({endpoint(urls[row]) for row in rows}):
        unreachable = reachable(host, port)
        if unreachable:
            for row in rows:
                print('SKIP ' + names[row] + ' reason=no network (%s:%d %s)' % (host, port, unreachable), flush=True)
            return
    out = Path(args.output) if args.output else root / 'target/runs' / ('http-live-' + args.tier)
    if out.exists():
        raise SystemExit('FAIL http-live-fresh-output: select a fresh build directory')
    out.mkdir(parents=True)
    der, count = pem_roots(pem)
    roots = out / 'roots.der'
    roots.write_bytes(der)
    print('ROOTS certificates=%d bytes=%d sha256=%s' % (count, len(der), hashlib.sha256(der).hexdigest()), flush=True)

    env = {key: value for key, value in os.environ.items() if key not in SECRETS}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_CONFIG_COUNT='1',
               GIT_CONFIG_KEY_0='protocol.version', GIT_CONFIG_VALUE_0='2')
    tools = {'git': dict(GIT_SSL_CAINFO=str(pem)), 'den': dict(DEN_TLS_ROOTS=str(roots))}
    captures = []
    user = os.environ.get('DEN_LIVE_HTTPS_USER', 'x-access-token')
    basic = base64.b64encode((user + ':' + live_token).encode()) if live_token else b''
    forbidden = [live_token.encode(), basic, live_token.encode().hex().encode(), basic.hex().encode()] if live_token else []

    def hidden(data):
        # The fixture is never named in a retained output, and the token never
        # reaches one: replace the URL, then refuse any trace of the token.
        if live_url:
            data = data.replace(live_url.encode(), b'<DEN_LIVE_HTTPS_URL>')
            data = data.replace(live_url.rstrip('/').removesuffix('.git').encode(), b'<DEN_LIVE_HTTPS_URL>')
        if any(secret and secret in data for secret in forbidden):
            raise SecretLeak()
        return data

    def record():
        (out / 'captures.json').write_text(json.dumps(captures, indent=2) + '\n')

    def run(argv, cwd, label, timeout, tool='git', extra=None, target=None, row=None):
        # Output goes to files and the child is reaped by wait4, so its own
        # rusage (max RSS, CPU) is measured and no pipe can stall it. With a
        # target, a clone: watched for progress and retried once after a
        # stall (den#118's gate side).
        def attempt(suffix):
            index = len(captures)
            paths = out / ('%03d.stdout' % index), out / ('%03d.stderr' % index)
            started = time.monotonic()
            with open(paths[0], 'wb') as stdout, open(paths[1], 'wb') as stderr:
                child = subprocess.Popen(list(map(str, argv)), cwd=cwd, env={**env, **tools[tool], **(extra or {})},
                                         stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
            status, usage, timed_out, stalled, quiet = reap(child, timeout, target)
            child.returncode = os.waitstatus_to_exitcode(status)
            elapsed = time.monotonic() - started
            outputs = [hidden(path.read_bytes()) for path in paths]
            for path, data in zip(paths, outputs):
                path.write_bytes(data)
            capture = dict(label=label + suffix, argv=[hidden(str(a).encode()).decode() for a in argv],
                           exit=child.returncode, timed_out=timed_out, stalled=stalled, quiet=quiet,
                           elapsed=round(elapsed, 2), maxrss_kib=usage.ru_maxrss,
                           user=round(usage.ru_utime, 2), system=round(usage.ru_stime, 2),
                           stdout=outputs[0].hex(), stderr=outputs[1].hex())
            captures.append(capture)
            record()
            return capture

        if target is None:
            return attempt('')
        capture = watched(attempt, target, timeout, row, tool)
        record()
        return capture

    def stalls(candidate, oracle, bound):
        """The row's problems when a tool's clone stalled twice: nothing else
        about such a clone can be compared."""
        return [stall_problem(tool, bound) for tool, capture in (('den', candidate), ('git', oracle))
                if capture['stalls'] == 2]

    def git_out(repo, *argv, data=None):
        result = subprocess.run([git, '-C', str(repo), *argv], env=env, input=data, capture_output=True, timeout=120)
        if result.returncode:
            raise AssertionError('pinned Git ' + argv[0] + ' failed in ' + repo.name + ': ' +
                                 result.stderr.decode(errors='replace').strip())
        return result.stdout

    def state(repo, keep=None):
        """A clone's refs, objects, HEAD, config and worktree. With keep (the
        remote's refs that held still), only the clone's refs for those, and
        only the objects they reach."""
        refs = git_out(repo, 'for-each-ref', '--format=%(refname) %(objectname) %(symref)')
        if keep is None:
            listed = git_out(repo, 'rev-list', '--objects', '--all')
        else:
            held_names = set(keep)

            def kept(refname):
                if refname.startswith('refs/remotes/origin/'):
                    rest = refname[len('refs/remotes/origin/'):]
                    return rest == 'HEAD' or 'refs/heads/' + rest in held_names
                if refname.startswith(('refs/heads/', 'refs/tags/')):
                    return refname in held_names
                return True
            lines = [line for line in refs.decode().splitlines() if kept(line.split(' ', 1)[0])]
            refs = ('\n'.join(lines) + '\n').encode() if lines else b''
            tips = ''.join(line.split(' ', 1)[0] + '\n' for line in lines)
            listed = git_out(repo, 'rev-list', '--objects', '--stdin', data=tips.encode())
        ids = sorted({line.split()[0] for line in listed.splitlines()})
        # Streamed: den's own repository's objects are hundreds of megabytes.
        digest = hashlib.sha256()
        batch = subprocess.Popen([git, '-C', str(repo), 'cat-file', '--batch'], env=env,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        feeder = threading.Thread(target=lambda: (batch.stdin.write(b''.join(i + b'\n' for i in ids)),
                                                  batch.stdin.close()))
        feeder.start()
        while True:
            chunk = batch.stdout.read(1 << 20)
            if not chunk:
                break
            digest.update(chunk)
        feeder.join()
        if batch.wait(timeout=600):
            raise AssertionError('pinned Git cat-file --batch failed in ' + repo.name)
        config = subprocess.run([git, '-C', str(repo), 'config', '--local', '--get-regexp', r'^(remote|branch)\.'],
                                env=env, capture_output=True, timeout=60).stdout
        files = {}
        for path in sorted(repo.rglob('*')):
            relative = path.relative_to(repo).as_posix()
            if relative == '.git' or relative.startswith('.git/'):
                continue
            if path.is_symlink():
                files[relative] = 'link:' + os.readlink(path)
            elif path.is_file():
                files[relative] = '%o:%s' % (path.stat().st_mode & 0o777, hashlib.sha256(path.read_bytes()).hexdigest())
        return dict(refs=refs.decode(), head=(repo / '.git/HEAD').read_bytes().hex(), objects=len(ids),
                    objects_sha256=digest.hexdigest(), config=config.decode(), worktree=files)

    def pair(name, url, seconds, prefix, what):
        """den, then the pinned Git, clone url into out/PREFIX-den and -git
        between two `ls-remote --symref` listings, as judge says: rerun once
        when HEAD or its branch moved, else compare what held still. Returns
        problems (why the row cannot compare; [] when it can), the captures,
        the directories, keep (the held refs, or None when nothing moved),
        excluded, moved_retries and unreachable_retries. A read the pinned
        Git could not make for want of the host reruns the pair once, after
        UNREACHABLE_PAUSE."""
        den_dir, git_dir = out / (prefix + '-den'), out / (prefix + '-git')
        moved_tries = unreachable_tries = 0
        while True:
            for path in (den_dir, git_dir):
                if path.exists():
                    shutil.rmtree(path)
            before = run([git, 'ls-remote', '--symref', url], out, name + '-ls-remote-before', 120)
            candidate = run([den, 'clone', '-q', url, den_dir], out, name + '-den', seconds, 'den',
                            target=den_dir, row=name)
            oracle = run([git, 'clone', '-q', url, git_dir], out, name + '-git', seconds, target=git_dir, row=name)
            after = run([git, 'ls-remote', '--symref', url], out, name + '-ls-remote-after', 120)
            got = dict(candidate=candidate, oracle=oracle, den_dir=den_dir, git_dir=git_dir, keep=None, excluded=[],
                       moved_retries=moved_tries, unreachable_retries=unreachable_tries,
                       problems=stalls(candidate, oracle, stall_bound(seconds)))
            if got['problems']:
                return got
            if before['exit'] or after['exit'] or oracle['exit']:
                # Only the pinned Git's reads decide whether the host was out of reach.
                reads = (('ls-remote-before', before), ('git', oracle), ('ls-remote-after', after))
                lost = out_of_reach([(label, capture['exit'],
                                      bytes.fromhex(capture['stderr']).decode('utf-8', 'replace'))
                                     for label, capture in reads])
                if lost and not unreachable_tries:
                    rerun_unreachable(name, lost)
                    unreachable_tries += 1
                    continue
                got['problems'] = [('pinned Git could not reach %s twice: %s' % (what, ','.join(lost))) if lost
                                   else 'pinned Git could not read ' + what]
                return got
            kept, moved_refs, critical = held(before['stdout'], after['stdout'])
            action = judge(name, moved_refs, critical, moved_tries)
            if action == 'retry':
                moved_tries += 1
                continue
            if action == 'fail':
                got['problems'] = ['refs moved during the row: ' + ','.join(critical or moved_refs)]
                return got
            got['excluded'] = moved_refs
            got['keep'] = kept if moved_refs else None
            return got

    failed = []
    results = {}
    if 'read' in rows:
        name = names['read']
        got = pair(name, READ_URL, READ_SECONDS, 'read', 'the public repository')
        problems = list(got['problems'])
        candidate, oracle, den_dir, git_dir = got['candidate'], got['oracle'], got['den_dir'], got['git_dir']
        if not problems:
            fields = [field for field in ('exit', 'stdout', 'stderr') if candidate[field] != oracle[field]]
            if fields:
                problems.append('process ' + '/'.join(fields) + ' differ: den exit %d stderr %r' % (
                    candidate['exit'], bytes.fromhex(candidate['stderr'])[:400]))
        if not problems:
            ours, theirs = state(den_dir, got['keep']), state(git_dir, got['keep'])
            differ = [key for key in ours if ours[key] != theirs[key]]
            git_out(den_dir, 'fsck', '--full', '--no-reflogs')
            dirty = git_out(den_dir, 'status', '--porcelain')
            results[name] = dict(den=ours, git=theirs, differ=differ, status=dirty.decode(),
                                 den_elapsed=candidate['elapsed'], den_maxrss_kib=candidate['maxrss_kib'],
                                 git_elapsed=oracle['elapsed'], git_maxrss_kib=oracle['maxrss_kib'],
                                 den_retries=candidate['retries'], git_retries=oracle['retries'],
                                 excluded=got['excluded'], moved_retries=got['moved_retries'],
                                 unreachable_retries=got['unreachable_retries'])
            if differ or dirty:
                problems.append('state differs: ' + ', '.join(differ) + (' (den worktree dirty)' if dirty else ''))
            else:
                print('LIVE %s head=%s objects=%d den=%.2fs/%sKiB git=%.2fs/%sKiB retries=den:%d,git:%d '
                      'quiet=den:%.1fs,git:%.1fs moved_retries=%d excluded=%s unreachable_retries=%d' % (
                          name, ours['refs'].split('\n')[0], ours['objects'], candidate['elapsed'],
                          candidate['maxrss_kib'], oracle['elapsed'], oracle['maxrss_kib'], candidate['retries'],
                          oracle['retries'], candidate['quiet'], oracle['quiet'], got['moved_retries'],
                          ','.join(got['excluded']) or '-', got['unreachable_retries']), flush=True)
        print(('PASS ' if not problems else 'FAIL ') + name + ('' if not problems else ' ' + '; '.join(problems)),
              flush=True)
        if problems:
            failed.append(name)

    if 'identity' in rows:
        name = names['identity']
        got = pair(name, IDENTITY_URL, IDENTITY_SECONDS, 'identity', 'the public repository')
        problems = list(got['problems'])
        candidate, oracle, den_dir, git_dir = got['candidate'], got['oracle'], got['den_dir'], got['git_dir']
        if not problems:
            fields = [field for field in ('exit', 'stdout', 'stderr') if candidate[field] != oracle[field]]
            if fields:
                problems.append('process ' + '/'.join(fields) + ' differ: den exit %d stderr %r' % (
                    candidate['exit'], bytes.fromhex(candidate['stderr'])[:400]))
        if not problems:
            ours, theirs = state(den_dir, got['keep']), state(git_dir, got['keep'])
            differ = [key for key in ours if ours[key] != theirs[key]]
            git_out(den_dir, 'fsck', '--full', '--no-reflogs')
            dirty = git_out(den_dir, 'status', '--porcelain')
            reads = []
            for argv in (['log', '-1', IDENTITY_COMMIT], ['show', '-s', IDENTITY_COMMIT],
                         ['log', '-1', '--format=%an|%ae|%al|%ad|%at|%cn|%ce|%cd', IDENTITY_COMMIT]):
                mine = run([den, *argv], den_dir, name + '-den-' + argv[0], 120, 'den')
                gits = run([git, *argv], git_dir, name + '-git-' + argv[0], 120)
                if (mine['exit'], mine['stdout'], mine['stderr']) != (gits['exit'], gits['stdout'], gits['stderr']):
                    reads.append(' '.join(argv[:-1]))
            results[name] = dict(den=ours, git=theirs, differ=differ, status=dirty.decode(), reads=reads,
                                 den_elapsed=candidate['elapsed'], den_maxrss_kib=candidate['maxrss_kib'],
                                 git_elapsed=oracle['elapsed'], git_maxrss_kib=oracle['maxrss_kib'],
                                 den_retries=candidate['retries'], git_retries=oracle['retries'],
                                 excluded=got['excluded'], moved_retries=got['moved_retries'],
                                 unreachable_retries=got['unreachable_retries'])
            if differ or dirty or reads:
                problems.append('state differs: ' + ', '.join(differ + reads) +
                                (' (den worktree dirty)' if dirty else ''))
            else:
                print('LIVE %s objects=%d den=%.2fs/%sKiB git=%.2fs/%sKiB retries=den:%d,git:%d '
                      'quiet=den:%.1fs,git:%.1fs moved_retries=%d excluded=%s unreachable_retries=%d' % (
                          name, ours['objects'], candidate['elapsed'], candidate['maxrss_kib'], oracle['elapsed'],
                          oracle['maxrss_kib'], candidate['retries'], oracle['retries'], candidate['quiet'],
                          oracle['quiet'], got['moved_retries'], ','.join(got['excluded']) or '-',
                          got['unreachable_retries']), flush=True)
        print(('PASS ' if not problems else 'FAIL ') + name + ('' if not problems else ' ' + '; '.join(problems)),
              flush=True)
        if problems:
            failed.append(name)

    if 'self' in rows:
        name = names['self']
        got = pair(name, args.self_url, args.self_seconds, 'self', 'den\'s repository')
        problems = list(got['problems'])
        candidate, oracle, den_dir, git_dir = got['candidate'], got['oracle'], got['den_dir'], got['git_dir']
        measured = dict(den_exit=candidate['exit'], den_elapsed=candidate['elapsed'],
                        den_maxrss_kib=candidate['maxrss_kib'], den_user=candidate['user'],
                        git_exit=oracle['exit'], git_elapsed=oracle['elapsed'], git_maxrss_kib=oracle['maxrss_kib'],
                        git_user=oracle['user'], bound_kib=SELF_RSS_KIB, stall_s=stall_bound(args.self_seconds),
                        den_retries=candidate['retries'], git_retries=oracle['retries'],
                        den_quiet_s=candidate['quiet'], git_quiet_s=oracle['quiet'],
                        moved_retries=got['moved_retries'], excluded=got['excluded'],
                        unreachable_retries=got['unreachable_retries'])
        # A clone that stalled twice, or a remote that moved twice, has nothing else to compare.
        if not problems:
            for field in ('exit', 'stdout', 'stderr'):
                if candidate[field] != oracle[field]:
                    problems.append('process %s differs: den exit %d stderr %r' % (
                        field, candidate['exit'], bytes.fromhex(candidate['stderr'])[:400]))
            if candidate['timed_out']:
                problems.append('den did not finish within %d s' % args.self_seconds)
            if candidate['maxrss_kib'] > SELF_RSS_KIB:
                problems.append('den peak RSS %d KiB over the predicted %d' % (candidate['maxrss_kib'], SELF_RSS_KIB))
            if not problems:
                packs = sorted((git_dir / '.git/objects/pack').glob('*.pack'))
                measured['git_pack_bytes'] = [path.stat().st_size for path in packs]
                ours, theirs = state(den_dir, got['keep']), state(git_dir, got['keep'])
                differ = [key for key in ours if ours[key] != theirs[key]]
                git_out(den_dir, 'fsck', '--full', '--no-reflogs')
                dirty = git_out(den_dir, 'status', '--porcelain')
                measured.update(objects=theirs['objects'], differ=differ, status=dirty.decode()[:400])
                if differ or dirty:
                    problems.append('state differs: ' + ', '.join(differ) + (' (den worktree dirty)' if dirty else ''))
        results[name] = measured
        print('LIVE ' + name + ' ' + json.dumps(measured, sort_keys=True), flush=True)
        print(('PASS ' if not problems else 'FAIL ') + name + ('' if not problems else ' ' + '; '.join(problems)),
              flush=True)
        if problems:
            failed.append(name)
        for path in (den_dir, git_dir):
            if path.exists():
                shutil.rmtree(path)

    if 'push' in rows:
        name = names['push']
        # R-vc22b-1 (a), R-vc23-3: the fixture's URL never reaches a child's
        # argv. den takes it from a remote named in GIT_CONFIG_* after `den
        # init`; Git would pass it to git-remote-https on argv
        # (gitremote-helpers(7), measured), so the pushed branch is read from
        # the server's own ref advertisement by the pinned OpenSSL client,
        # the request and its credential written on that client's stdin.
        den_auth = {'DEN_HTTP_TOKEN': live_token, 'DEN_HTTP_USER': user,
                    'GIT_CONFIG_COUNT': '3', 'GIT_CONFIG_KEY_1': 'remote.live.url', 'GIT_CONFIG_VALUE_1': live_url,
                    'GIT_CONFIG_KEY_2': 'remote.live.fetch', 'GIT_CONFIG_VALUE_2': '+refs/heads/*:refs/remotes/live/*'}
        work = out / 'push-den'
        branch = 'refs/heads/den-live-push-' + secrets.token_hex(6)
        problems, pushed = [], False
        pins = runpy.run_path(str(root / 'tools/http-git-test.py'))['OPENSSL_PINS']
        assert hashlib.sha256(Path('/usr/bin/openssl').read_bytes()).hexdigest() == pins['/usr/bin/openssl'], \
            'pinned OpenSSL digest'
        target = live_url.removeprefix('https://github.com')

        def advertisement():
            """The server's upload-pack refs (v0 discovery) through `openssl s_client`."""
            request = ('GET ' + target + '/info/refs?service=git-upload-pack HTTP/1.1\r\nHost: github.com\r\n'
                       'User-Agent: git/den-live-row\r\nAccept: */*\r\nAuthorization: Basic ' + basic.decode() +
                       '\r\nConnection: close\r\n\r\n').encode()
            result = subprocess.run(['/usr/bin/openssl', 's_client', '-quiet', '-verify_return_error',
                                     '-CAfile', str(pem), '-servername', 'github.com', '-connect', 'github.com:443'],
                                    env=env, input=request, capture_output=True, timeout=120)
            response = hidden(result.stdout)
            hidden(result.stderr)
            head, _, body = response.partition(b'\r\n\r\n')
            if not head.startswith(b'HTTP/1.1 200 '):
                raise AssertionError('server advertisement status %r' % head.split(b'\r\n')[0][:40])
            if b'transfer-encoding: chunked' in head.lower():
                joined, pos = bytearray(), 0
                while True:
                    eol = body.index(b'\r\n', pos)
                    size = int(body[pos:eol].split(b';')[0], 16)
                    if size == 0:
                        break
                    joined += body[eol + 2:eol + 2 + size]
                    pos = eol + 2 + size + 2
                body = bytes(joined)
            refs, pos = {}, 0
            while pos < len(body):
                length = int(body[pos:pos + 4], 16)
                if length < 4:
                    pos += 4
                    continue
                line = body[pos + 4:pos + length].split(b'\0')[0].rstrip(b'\n')
                pos += length
                if line.startswith(b'#'):
                    continue
                oid, _, ref = line.partition(b' ')
                refs[ref.decode()] = oid.decode()
            return refs

        def remote_ref():
            return advertisement().get(branch, '')

        fixture_path = live_url.removeprefix('https://github.com').removesuffix('.git').encode()
        watch = ArgvWatch([live_url.encode(), live_url.removesuffix('.git').encode(), fixture_path,
                           live_token.encode(), basic]).__enter__()
        init = run([den, 'init', '-q', work], out, name + '-init', 60, 'den')
        fetched = run([den, 'fetch', '-q', 'live'], work, name + '-fetch', READ_SECONDS, 'den', den_auth) \
            if init['exit'] == 0 else init
        if fetched['exit']:
            problems.append('den init or fetch exit %d: %r' % (fetched['exit'], bytes.fromhex(fetched['stderr'])[:300]))
        else:
            # The server's HEAD as the parent, when den's fetch brought it.
            head = advertisement().get('HEAD', '')
            if head and subprocess.run([git, '-C', str(work), 'cat-file', '-e', head + '^{commit}'], env=env,
                                       capture_output=True, timeout=60).returncode:
                head = ''
            blob = git_out(work, 'hash-object', '-w', '--stdin', data=secrets.token_hex(8).encode()).strip()
            tree = git_out(work, 'mktree', data=b'100644 blob ' + blob + b'\tden-live-push\n').strip().decode()
            commit = git_out(work, 'commit-tree', tree, *(['-p', head] if head else []), '-m', 'den live push row').strip().decode()
            git_out(work, 'update-ref', 'refs/heads/den-live-push', commit)
            try:
                push = run([den, 'push', '-q', 'live', 'refs/heads/den-live-push:' + branch], work, name + '-push',
                           READ_SECONDS, 'den', den_auth)
                pushed = push['exit'] == 0
                if not pushed:
                    problems.append('den push exit %d: %r' % (push['exit'], bytes.fromhex(push['stderr'])[:300]))
                elif remote_ref() != commit:
                    problems.append('the server does not advertise the pushed branch at the pushed commit')
            finally:
                if pushed:
                    delete = run([den, 'push', '-q', 'live', ':' + branch], work, name + '-delete', READ_SECONDS,
                                 'den', den_auth)
                    if delete['exit']:
                        problems.append('den delete exit %d: %r' % (delete['exit'], bytes.fromhex(delete['stderr'])[:300]))
                    elif remote_ref():
                        problems.append('the disposable branch is still on the remote')
        watch.__exit__()
        argv_problems = []
        if not watch.control:
            argv_problems.append('the watcher did not see its control argv')
        if not watch.seen:
            argv_problems.append('the watcher saw no child')
        if watch.hits:
            argv_problems.append('%d of %d children held the fixture URL or token on argv (values withheld)' % (
                len(watch.hits), len(watch.seen)))
        print('LIVE http-live-argv children=%d hits=%d control=%s' % (len(watch.seen), len(watch.hits), watch.control),
              flush=True)
        print(('PASS ' if not argv_problems else 'FAIL ') + 'http-live-argv' +
              ('' if not argv_problems else ' ' + '; '.join(argv_problems)), flush=True)
        if argv_problems:
            failed.append('http-live-argv')
        for path in out.rglob('*'):
            if path.is_file():
                hidden(path.read_bytes())
        print('PASS http-token-secrecy-live', flush=True)
        print(('PASS ' if not problems else 'FAIL ') + name + ('' if not problems else ' ' + '; '.join(problems)),
              flush=True)
        if problems:
            failed.append(name)
        if work.exists():
            shutil.rmtree(work)

    (out / 'results.json').write_text(json.dumps(results, indent=2, sort_keys=True) + '\n')
    for path in out.glob('read-*'):
        shutil.rmtree(path)
    if failed:
        raise SystemExit('FAIL http-live: ' + ', '.join(failed))
    print('http-live: ' + args.tier + ' ' + ','.join(rows) + '; zero skips', flush=True)


class SecretLeak(Exception):
    pass


if __name__ == '__main__':
    try:
        main()
    except SecretLeak:
        raise SystemExit('FAIL http-token-secrecy-live: output withheld')
    except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as exc:
        raise SystemExit('FAIL http-live-harness: ' + str(exc))
