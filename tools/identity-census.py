"""vc26: the identity census over real histories.

For each MIRROR (a bare mirror the pinned Git made, `git clone --mirror`):

  checker   every commit and tag is read; den's identity check
            (commit-format-client problems, commit_format.identity_problem)
            names the first author, committer or tagger line Git's fsck
            would report, and that per-object verdict must equal the pinned
            Git's own `fsck` on the mirror, object for object;
  receive   `den clone --bare` and `git clone --bare` of file://MIRROR both
            succeed with the same refs and the same objects;
  read      for every commit and tag with an identity line outside the
            plain canonical form (and a fixed sample of 100 others), in a
            repository holding the mirror's objects loose:
            `show -s --pretty=fuller` and `show -s` with every identity
            placeholder (--date=raw and the default), or `show -s` of the
            tag, byte for byte the pinned Git's in the same repository.

It tallies every identity line by the id Git's fsck gives it ("clean"
otherwise) and by a few byte shapes, and prints one CENSUS line per mirror:
the tallies and the three verdicts. A difference is FAIL <mirror>/<part>.
Run through tools/env with DEN_GIT, after tools/build and check-commit's
probe build (target/TIER/commit-format-client).
"""
import argparse
import collections
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

R = pathlib.Path(__file__).resolve().parent.parent
ORACLE_SHA = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
IDS = ('badDate', 'badDateOverflow', 'badEmail', 'badName', 'badTimezone', 'missingEmail',
       'missingNameBeforeEmail', 'missingSpaceBeforeDate', 'missingSpaceBeforeEmail', 'zeroPaddedDate')
PLACEHOLDERS = '%H|%an|%ae|%al|%ad|%aD|%at|%ai|%aI|%as|%cn|%ce|%cl|%cd|%cD|%ct|%ci|%cI|%cs'
# The plain canonical identity: a name without edge spaces, an email, a date
# without leading zeros and a four-digit zone.
CANONICAL = re.compile(rb'^[^<> ][^<>]*[^<> ] <[^<>]+> (0|[1-9][0-9]*) [+-][0-9]{4}$')
SAMPLE = 100

p = argparse.ArgumentParser()
p.add_argument('--tier', default='native')
p.add_argument('--out', required=True)
p.add_argument('--field', action='store_true', help='a Git other than the pinned one (digest unchecked)')
p.add_argument('mirrors', nargs='+')
A = p.parse_args()
GIT = os.environ['DEN_GIT']
if not A.field:
    assert hashlib.sha256(pathlib.Path(GIT).read_bytes()).hexdigest() == ORACLE_SHA, 'pinned oracle digest'
DEN = str(R / 'target' / A.tier / 'den')
CLIENT = str(R / 'target' / A.tier / 'commit-format-client')
OUT = pathlib.Path(A.out).resolve()
OUT.mkdir(parents=True, exist_ok=False)
failures = []


def run(argv, cwd, data=None, timeout=3600):
    return subprocess.run([str(x) for x in argv], cwd=cwd, input=data, capture_output=True, timeout=timeout)


def ok(argv, cwd, data=None):
    q = run(argv, cwd, data)
    assert q.returncode == 0, (argv, q.stderr[-400:])
    return q.stdout


def objects(mirror):
    """(id, type, body) of every commit and tag in the mirror."""
    listing = ok([GIT, 'cat-file', '--batch-all-objects', '--batch-check=%(objectname) %(objecttype)'], mirror)
    wanted = [line.split()[0] for line in listing.splitlines() if line.split()[1] in (b'commit', b'tag')]
    data = ok([GIT, 'cat-file', '--batch'], mirror, data=b''.join(i + b'\n' for i in wanted))
    out, pos = [], 0
    for name in wanted:
        end = data.index(b'\n', pos)
        oid, kind, size = data[pos:end].split()
        assert oid == name
        body = data[end + 1:end + 1 + int(size)]
        out.append((name.decode(), kind.decode(), body))
        pos = end + 1 + int(size) + 1
    return out


def identities(body):
    """The author, committer and tagger values of a commit or tag header."""
    values = []
    for line in body.split(b'\n\n', 1)[0].split(b'\n'):
        key, _, value = line.partition(b' ')
        if key in (b'author', b'committer', b'tagger'):
            values.append(value)
    return values


def shape(value):
    marks = []
    if b'<>' in value:
        marks.append('empty email')
    if value.startswith(b'<') or value.startswith(b' <'):
        marks.append('empty name')
    try:
        value.decode('utf-8')
    except UnicodeDecodeError:
        marks.append('not UTF-8')
    if value.endswith(b'\r'):
        marks.append('CR')
    return marks


def compare(label, argv, ours, theirs):
    a, b = run([DEN, *argv], ours), run([GIT, *argv], theirs)
    same = (a.returncode, a.stdout, a.stderr) == (b.returncode, b.stdout, b.stderr)
    if not same:
        (OUT / (label.replace('/', '_') + '.den')).write_bytes(a.stdout + b'\n--stderr--\n' + a.stderr)
        (OUT / (label.replace('/', '_') + '.git')).write_bytes(b.stdout + b'\n--stderr--\n' + b.stderr)
    return same, len(b.stdout)


summary = []
for mirror_arg in A.mirrors:
    mirror = pathlib.Path(mirror_arg).resolve()
    name = mirror.name.removesuffix('.git')
    work = OUT / name
    work.mkdir()
    found = objects(mirror)
    # The checker: den's verdict per object against Git's fsck.
    values, owners = [], []
    for oid, kind, body in found:
        for value in identities(body):
            assert b'\n' not in value
            values.append(value)
            owners.append((oid, kind))
    (work / 'values').write_bytes(b''.join(v + b'\n' for v in values))
    verdicts = ok([CLIENT, 'problems', work / 'values'], work).decode().split('\n')[:-1]
    assert len(verdicts) == len(values)
    den_ids = {}
    for (oid, kind), verdict in zip(owners, verdicts):
        if verdict != '-' and oid not in den_ids:
            den_ids[oid] = verdict
    fsck = run([GIT, 'fsck', '--no-dangling', '--no-progress', '--no-reflogs'], mirror)
    git_ids = {}
    for line in fsck.stderr.decode('utf-8', 'replace').splitlines():
        m = re.match(r'error in (commit|tag) ([0-9a-f]{40}): (\w+): ', line)
        if m and m[3] in IDS:
            git_ids[m[2]] = m[3]
    checker = den_ids == git_ids
    if not checker:
        failures.append(name + '/checker')
        (work / 'checker.json').write_text(json.dumps(dict(den=den_ids, git=git_ids), indent=1))
    tally = collections.Counter(v if v != '-' else 'clean' for v in verdicts)
    marks = collections.Counter(m for v in values for m in shape(v))
    # Receive: both tools clone the mirror over file://.
    ours, theirs = work / 'den.git', work / 'git.git'
    a = run([DEN, 'clone', '-q', '--bare', mirror.as_uri(), ours], work)
    b = run([GIT, 'clone', '-q', '--bare', mirror.as_uri(), theirs], work)
    receive = a.returncode == 0 and b.returncode == 0 and (a.stdout, a.stderr) == (b.stdout, b.stderr)
    if receive:
        refs = [ok([GIT, 'for-each-ref', '--format=%(objectname) %(refname)'], r) for r in (ours, theirs)]
        sets = [ok([GIT, 'cat-file', '--batch-all-objects', '--batch-check'], r) for r in (ours, theirs)]
        receive = refs[0] == refs[1] and sets[0] == sets[1]
    if not receive:
        failures.append(name + '/receive')
        (work / 'receive.txt').write_bytes(b'den %d\n' % a.returncode + a.stderr + b'\ngit %d\n' % b.returncode + b.stderr)
    # Read: every commit and tag with an identity line outside the plain
    # canonical form, and a fixed sample of the rest, shown one at a time,
    # from a repository holding the mirror's objects loose: den reads a
    # pack's index again for each object it reads from that pack, which is
    # a cost question, not this census's.
    read, read_bytes, compared, unusual = True, 0, 0, 0
    if receive:
        chosen, plain = [], []
        for oid, kind, body in found:
            odd = any(not CANONICAL.match(v) for v in identities(body))
            (chosen if odd else plain).append((oid, kind))
        unusual = len(chosen)
        chosen += plain[::max(1, len(plain) // SAMPLE)][:SAMPLE]
        # Every object of the mirror, unpacked loose (`git show -s` reads
        # trees and blobs to settle its diff even when it prints none).
        mini = work / 'loose'
        ok([GIT, 'init', '-q', '--bare', mini], work)
        pack = ok([GIT, 'pack-objects', '--all', '--stdout', '-q'], mirror, data=b'')
        ok([GIT, 'unpack-objects', '-q'], mini, data=pack)
        del pack
        for oid, kind in chosen:
            if kind == 'commit':
                checks = [('fuller', ['show', '-s', '--pretty=fuller', oid]),
                          ('raw-dates', ['show', '-s', '--date=raw', '--format=' + PLACEHOLDERS, oid]),
                          ('default-dates', ['show', '-s', '--format=' + PLACEHOLDERS, oid])]
            else:
                checks = [('show', ['show', '-s', oid])]
            for label, argv in checks:
                same, size = compare(name + '/' + oid + '-' + label, argv, mini, mini)
                read_bytes += size
                compared += 1
                if not same:
                    read = False
                    failures.append(name + '/read ' + oid + ' ' + label)
        shutil.rmtree(mini)
    row = dict(mirror=name, objects=len(found), identities=len(values), fsck_ids=dict(tally), shapes=dict(marks),
               objects_reported=len(git_ids), checker=checker, receive=receive, read=read,
               unusual_objects=unusual, read_commands=compared, read_bytes=read_bytes)
    summary.append(row)
    print('CENSUS %s objects=%d identities=%d ids=%s shapes=%s checker=%s receive=%s read=%s '
          '(%d unusual objects, %d commands, %d bytes)' % (
              name, len(found), len(values), json.dumps(dict(tally), sort_keys=True),
              json.dumps(dict(marks), sort_keys=True), 'equal' if checker else 'DIFF',
              'equal' if receive else 'DIFF', 'equal' if read else 'DIFF', unusual, compared, read_bytes), flush=True)
    shutil.rmtree(ours, ignore_errors=True)
    shutil.rmtree(theirs, ignore_errors=True)
(OUT / 'census.json').write_text(json.dumps(summary, indent=1) + '\n')
for failure in failures:
    print('FAIL ' + failure)
print('CENSUS COMPLETE mirrors=%d failed=%d' % (len(summary), len(failures)))
sys.exit(1 if failures else 0)
