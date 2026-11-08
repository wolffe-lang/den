"""vc26: identity shapes as the pinned Git and den take them.

Each shape is the value of an identity line, crafted with
`git hash-object --literally` into a commit's author and committer and an
annotated tag's tagger. Every operation runs with both tools under
tools/env; a row compares den's status, stdout and stderr with Git's, byte
for byte, and the object bytes and ids a clone receives.

  --measure    run every row and write the table (target/identity-TIER/),
               failing nothing: the lane's specification, before a change.
  (default)    the same rows; any row whose bytes differ is FAIL <row>,
               except the named refusals in REFUSED, where den must refuse
               by that name (and Git's answer is recorded).
  --family F   read, format, fsck, wire, replay or write (repeatable).
  --field      Git is not the pinned one (the macOS field leg): its digest
               is not checked; every row holds as it does for the pinned Git.
"""
import argparse
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

# (name, the identity value's bytes). Kept in the order of the prediction.
SHAPES = [
    ('control', b'A U Thor <author@example.invalid> 1700000000 +0000'),
    ('empty-email', b'walker0643 <> 1519250155 -0500'),
    ('empty-name', b' <e@example.invalid> 1700000000 +0000'),
    ('no-name', b'<e@example.invalid> 1700000000 +0000'),
    ('empty-both', b' <> 1700000000 +0000'),
    ('no-email', b'A U Thor 1700000000 +0000'),
    ('glued-email', b'A U Thor<a@example.invalid> 1700000000 +0000'),
    ('glued-date', b'A U Thor <a@example.invalid>1700000000 +0000'),
    ('two-spaces', b'A U Thor <a@example.invalid>  1700000000 +0000'),
    ('no-date', b'A U Thor <a@example.invalid>'),
    ('zero-date', b'A U Thor <a@example.invalid> 0 +0000'),
    ('zero-padded', b'A U Thor <a@example.invalid> 01700000000 +0000'),
    ('negative', b'A U Thor <a@example.invalid> -1 +0000'),
    ('over-i64', b'A U Thor <a@example.invalid> 9223372036854775808 +0000'),
    ('over-u64', b'A U Thor <a@example.invalid> 18446744073709551616 +0000'),
    ('zone-long', b'A U Thor <a@example.invalid> 1700000000 +00000'),
    ('zone-short', b'A U Thor <a@example.invalid> 1700000000 +000'),
    ('zone-unsigned', b'A U Thor <a@example.invalid> 1700000000 0000'),
    ('zone-minutes', b'A U Thor <a@example.invalid> 1700000000 +0099'),
    ('lt-in-name', b'Jo<e <a@example.invalid> 1700000000 +0000'),
    ('gt-in-name', b'Jo>e <a@example.invalid> 1700000000 +0000'),
    ('lt-in-email', b'A U Thor <a<b@example.invalid> 1700000000 +0000'),
    ('gt-in-email', b'A U Thor <a>b@example.invalid> 1700000000 +0000'),
    ('trailing', b'A U Thor <a@example.invalid> 1700000000 +0000 garbage'),
    ('latin1-name', b'Jos\xe9 <a@example.invalid> 1700000000 +0000'),
    ('cr', b'A U Thor <a@example.invalid> 1700000000 +0000\r'),
    # Beyond the prediction: the rules' edges, measured to pin the split
    # and the checks between the shapes above.
    ('name-spaces', b'A U Thor   <a@example.invalid> 1700000000 +0000'),
    ('name-leading', b'  A U Thor <a@example.invalid> 1700000000 +0000'),
    ('name-blank', b'   <a@example.invalid> 1700000000 +0000'),
    ('name-utf8', b'Jos\xc3\xa9 <a@example.invalid> 1700000000 +0000'),
    ('tab-email', b'A U Thor\t<a@example.invalid> 1700000000 +0000'),
    ('tab-date', b'A U Thor <a@example.invalid>\t1700000000 +0000'),
    ('email-open', b'A U Thor <a@example.invalid 1700000000 +0000'),
    ('email-space', b'A U Thor <a b@example.invalid> 1700000000 +0000'),
    ('email-latin1', b'A U Thor <\xe9@example.invalid> 1700000000 +0000'),
    ('email-gt-gt', b'A U Thor <a@example.invalid>> 1700000000 +0000'),
    ('bare-empty', b'<> 1700000000 +0000'),
    ('date-zone-glued', b'A U Thor <a@example.invalid> 1700000000+0000'),
    ('date-zone-spaces', b'A U Thor <a@example.invalid> 1700000000  +0000'),
    ('no-zone', b'A U Thor <a@example.invalid> 1700000000'),
    ('date-space-only', b'A U Thor <a@example.invalid> '),
    ('zone-space-after', b'A U Thor <a@example.invalid> 1700000000 +0000 '),
    ('double-zero', b'A U Thor <a@example.invalid> 00 +0000'),
    ('max-i64', b'A U Thor <a@example.invalid> 9223372036854775807 +0000'),
    ('max-u64', b'A U Thor <a@example.invalid> 18446744073709551615 +0000'),
    ('year-9999', b'A U Thor <a@example.invalid> 253402300799 +0000'),
    ('year-10000', b'A U Thor <a@example.invalid> 253402300800 +0000'),
    ('zone-max', b'A U Thor <a@example.invalid> 1700000000 +9999'),
    ('zone-west', b'A U Thor <a@example.invalid> 1700000000 -1230'),
    ('zone-negzero', b'A U Thor <a@example.invalid> 1700000000 -0000'),
    ('zone-letter', b'A U Thor <a@example.invalid> 1700000000 +00a0'),
    ('zone-five', b'A U Thor <a@example.invalid> 1700000000 +12345'),
    ('zone-one', b'A U Thor <a@example.invalid> 1700000000 +1'),
    ('zone-minus-five', b'A U Thor <a@example.invalid> 1700000000 -5'),
    ('spaces-padded', b'A U Thor <a@example.invalid>  01700000000 +0000'),
    ('space-tab-date', b'A U Thor <a@example.invalid> \t1700000000 +0000'),
    ('zero-no-zone', b'A U Thor <a@example.invalid> 0'),
    ('over-west', b'A U Thor <a@example.invalid> 18446744073709551616 -0500'),
    ('far-year', b'A U Thor <a@example.invalid> 100000000000000 +0000'),
    ('gmtime-edge', b'A U Thor <a@example.invalid> 67767976233532799 +0000'),
    ('gmtime-past', b'A U Thor <a@example.invalid> 67767976233532800 +0000'),
    ('max-i64-west', b'A U Thor <a@example.invalid> 9223372036854775807 -0500'),
    ('epoch-west', b'A U Thor <a@example.invalid> 0 -0500'),
    ('one-west', b'A U Thor <a@example.invalid> 1 -0100'),
    ('gmtime-last', b'A U Thor <a@example.invalid> 67768036191676799 +0000'),
    ('gmtime-fail', b'A U Thor <a@example.invalid> 67768036191676800 +0000'),
    ('zone-10039', b'A U Thor <a@example.invalid> 1700000000 +10039'),
    ('zone-10040', b'A U Thor <a@example.invalid> 1700000000 +10040'),
    ('zone-0960', b'A U Thor <a@example.invalid> 1700000000 +0960'),
]

PLACEHOLDERS = ('%an|%ae|%al|%aN|%aE|%aL|%ad|%aD|%at|%ai|%aI|%as%n'
                '%cn|%ce|%cl|%cN|%cE|%cL|%cd|%cD|%ct|%ci|%cI|%cs')

CONTROL = b'A U Thor <author@example.invalid> 1700000000 +0000'


# Den refuses these by name, as ruled: den does not run Git's full object
# checks, so a configuration that asks for them is refused, never ignored;
# `fsck --strict` adds a file mode check den does not make; placeholders
# outside the minimal format engine are refused. (family, op) -> text that
# den's stderr must hold, with exit 2.
CHECKS = ": den does not run git's full object checks"
REFUSED = {
    ('wire', 'clone-fsck-objects'): 'transfer.fsckObjects' + CHECKS,
    ('wire', 'clone-fetch-fsck-objects'): 'fetch.fsckObjects' + CHECKS,
    ('wire', 'serve-push-fsck-objects'): 'receive.fsckObjects' + CHECKS,
    ('fsck', 'fsck-strict'): 'not yet implemented: fsck --strict',
    # Git amends a date above 9223372036854775807 that den's 64-bit dates
    # cannot hold.
    ('replay', 'amend', 'over-i64'): 'not yet implemented: commit amend date past 9223372036854775807',
}

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('--tier', default='native')
    p.add_argument('--measure', action='store_true')
    p.add_argument('--field', action='store_true')
    p.add_argument('--family', action='append',
                   choices=('read', 'format', 'fsck', 'wire', 'replay', 'write'))
    p.add_argument('--shape', action='append')
    return p.parse_args()


A = parse_args()
FAMILIES = A.family or ['read', 'format', 'fsck', 'wire', 'replay', 'write']
GIT = pathlib.Path(os.environ.get('DEN_GIT') or next((R / 'target/oracle').glob('*/root/opt/git/bin/git')))
if not A.field:
    assert hashlib.sha256(GIT.read_bytes()).hexdigest() == ORACLE_SHA, 'pinned oracle digest'
DEN = R / 'target' / A.tier / 'den'
assert DEN.is_file(), DEN
ROOT = R / 'target' / ('identity-' + A.tier + ('-field' if A.field else ''))
if ROOT.exists():
    shutil.rmtree(ROOT)
ROOT.mkdir(parents=True)
TOOLS = {'git': str(GIT), 'den': str(DEN)}
rows = []
failures = []


def run(argv, cwd, data=None, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    q = subprocess.run([str(x) for x in argv], cwd=cwd, input=data, capture_output=True, env=e, timeout=300)
    return q


def g(cwd, *args, data=None, env=None):
    q = run([GIT, *args], cwd, data=data, env=env)
    assert q.returncode == 0, (args, q.stderr)
    return q.stdout.strip().decode()


def text(data):
    return data.decode('utf-8', 'backslashreplace')


def result(q):
    return {'status': q.returncode, 'stdout': text(q.stdout), 'stderr': text(q.stderr)}


def verdict(res):
    """A short reading of one result: ok, warn ID, or xSTATUS ID."""
    ids = re.findall(r'\b([a-z]+[A-Z][A-Za-z0-9]*): ', res['stderr'] + res['stdout'])
    named_refusal = re.findall(r'Unsupported\(([^)]*)\)', res['stderr'])
    tag = ','.join(dict.fromkeys(ids)) or (named_refusal[0] if named_refusal else '')
    if res['status'] == 0:
        return 'ok' if not res['stderr'] else 'warn ' + (tag or 'stderr')
    if not tag:
        lines = res['stderr'].strip().splitlines()
        tag = lines[-1][:60] if lines else ''
    return ('x%d %s' % (res['status'], tag)).strip()


def record(shape, family, op, git_res, den_res, extra=None):
    same = (git_res['status'], git_res['stdout'], git_res['stderr']) == \
        (den_res['status'], den_res['stdout'], den_res['stderr'])
    if extra is not None:
        same = same and extra.get('git') == extra.get('den')
    row = dict(shape=shape, family=family, op=op, git=git_res, den=den_res, same=same,
               git_verdict=verdict(git_res), den_verdict=verdict(den_res))
    if extra is not None:
        row['received'] = extra
    name = '%s/%s/%s' % (family, shape, op)
    want = REFUSED.get((family, op, shape), REFUSED.get((family, op)))
    row['refusal'] = want
    rows.append(row)
    if want is not None:
        ok = den_res['status'] != 0 and want in den_res['stderr']
        if extra is not None and family == 'wire':
            ok = ok and extra.get('den') is None
        row['passed'] = ok
        if ok:
            print('PASS', name, 'refused by name:', want, '(git: %s)' % row['git_verdict'], flush=True)
            return
    else:
        row['passed'] = same
        if same:
            print('PASS', name, flush=True)
            return
    failures.append(name)
    print(('DIFF ' if A.measure else 'FAIL ') + name, 'git=' + json.dumps(git_res), 'den=' + json.dumps(den_res),
          ('received=' + json.dumps(extra)) if extra is not None else '', flush=True)


def build_source(name, value):
    """A repository whose main holds a normal root commit, then the shaped
    commit (author and committer) changing f, and tag t (tagger)."""
    src = ROOT / 'src' / name
    src.mkdir(parents=True)
    g(src, 'init', '-q', '-b', 'main')
    first = g(src, 'hash-object', '-w', '--stdin', data=b'one\ntwo\n')
    second = g(src, 'hash-object', '-w', '--stdin', data=b'one\ntwo\nthree\n')
    t0 = g(src, 'mktree', data=('100644 blob %s\tf\n' % first).encode())
    t1 = g(src, 'mktree', data=('100644 blob %s\tf\n' % second).encode())
    c0 = g(src, 'hash-object', '--literally', '-w', '-t', 'commit', '--stdin',
           data=b'tree ' + t0.encode() + b'\nauthor ' + CONTROL + b'\ncommitter ' + CONTROL + b'\n\nroot\n')
    body = (b'tree ' + t1.encode() + b'\nparent ' + c0.encode() + b'\nauthor ' + value +
            b'\ncommitter ' + value + b'\n\nshaped\n')
    c1 = g(src, 'hash-object', '--literally', '-w', '-t', 'commit', '--stdin', data=body)
    tag = (b'object ' + c1.encode() + b'\ntype commit\ntag t\ntagger ' + value + b'\n\ntag message\n')
    t = g(src, 'hash-object', '--literally', '-w', '-t', 'tag', '--stdin', data=tag)
    g(src, 'update-ref', 'refs/heads/main', c1)
    g(src, 'update-ref', 'refs/tags/t', t)
    g(src, 'reset', '-q', '--hard', 'main')
    return src, dict(commit=c1, tag=t, root=c0, commit_bytes=body.hex(), tag_bytes=tag.hex())


def both(args, cwd):
    return {tool: result(run([TOOLS[tool], *args], cwd)) for tool in ('git', 'den')}


def read_family(name, src, ids):
    c1, t = ids['commit'], ids['tag']
    ops = [
        ('cat-file-commit', ['cat-file', '-p', c1]),
        ('cat-file-tag', ['cat-file', '-p', t]),
        ('log', ['log', '-1', c1]),
        ('log-fuller', ['log', '-1', '--pretty=fuller', c1]),
        ('log-raw-date', ['log', '-1', '--date=raw', c1]),
        ('log-iso-date', ['log', '-1', '--date=iso-strict', c1]),
        ('show', ['show', '-s', c1]),
        ('show-tag', ['show', '-s', t]),
        ('format', ['log', '-1', '--format=' + PLACEHOLDERS, c1]),
        ('format-dates', ['log', '-1', '--date=raw', '--format=%ad|%cd', c1]),
        ('blame', ['blame', c1, '--', 'f']),
        ('blame-porcelain', ['blame', '--porcelain', c1, '--', 'f']),
        ('blame-email', ['blame', '-e', c1, '--', 'f']),
    ]
    for op, args in ops:
        res = both(args, src)
        record(name, 'read', op, res['git'], res['den'])


def fsck_copy(name, src, ids, op):
    """A copy of the source for one fsck row: `fsck-packed` holds every
    object in one pack, `fsck-mixed` the shaped commit in a pack and the
    tag loose, `fsck-committer` a shaped committer under a control author."""
    work = ROOT / 'fsck' / name / op
    shutil.copytree(src, work)
    if op == 'fsck-packed':
        g(work, 'repack', '-adq')
        g(work, 'prune-packed')
    elif op == 'fsck-mixed':
        g(work, 'pack-objects', '-q', '.git/objects/pack/pack', data=(ids['commit'] + '\n').encode())
        (work / '.git/objects' / ids['commit'][:2] / ids['commit'][2:]).unlink()
    elif op == 'fsck-committer':
        value = bytes.fromhex(ids['commit_bytes']).split(b'\ncommitter ', 1)[1].split(b'\n', 1)[0]
        tree = g(work, 'rev-parse', ids['commit'] + '^{tree}')
        body = (b'tree ' + tree.encode() + b'\nparent ' + ids['root'].encode() + b'\nauthor ' + CONTROL +
                b'\ncommitter ' + value + b'\n\ncommitter only\n')
        c = g(work, 'hash-object', '--literally', '-w', '-t', 'commit', '--stdin', data=body)
        g(work, 'update-ref', 'refs/heads/main', c)
        g(work, 'update-ref', '-d', 'refs/tags/t')
        g(work, 'reflog', 'expire', '--expire=all', '--all')
        g(work, 'prune', '--expire=now')
    return work


def fsck_family(name, src, ids):
    for op, args in [('fsck', ['fsck']), ('fsck-strict', ['fsck', '--strict'])]:
        res = both(args, src)
        record(name, 'fsck', op, res['git'], res['den'])
    for op in ('fsck-packed', 'fsck-mixed', 'fsck-committer'):
        work = fsck_copy(name, src, ids, op)
        res = both(['fsck'], work)
        record(name, 'fsck', op, res['git'], res['den'])


def received(dst, ids):
    """What a destination holds of the shaped objects: their bytes, read by
    the pinned Git, and the refs it published."""
    out = {}
    for key in ('commit', 'tag'):
        q = run([GIT, 'cat-file', ('commit' if key == 'commit' else 'tag'), ids[key]], dst)
        out[key] = q.stdout.hex() if q.returncode == 0 else None
    q = run([GIT, 'for-each-ref', '--format=%(objectname) %(refname)'], dst)
    out['refs'] = text(q.stdout) if q.returncode == 0 else None
    return out


def global_config(work, extra):
    # Configuration through a copy of the pinned global config file: both
    # tools read it, and den takes no `-c`.
    conf = work / 'gitconfig'
    base = pathlib.Path(os.environ['GIT_CONFIG_GLOBAL']).read_bytes()
    conf.write_bytes(base + extra)
    return {'GIT_CONFIG_GLOBAL': str(conf)}


WIRE_OPS = ('clone', 'clone-bare', 'clone-local', 'clone-fsck-objects', 'clone-fetch-fsck-objects',
            'clone-fetch-false', 'push', 'serve-fetch', 'serve-push', 'serve-push-fsck-objects')


def wire_family(name, src, ids):
    url = src.as_uri()
    for op in WIRE_OPS:
        res, held = {}, {}
        for tool in ('git', 'den'):
            work = ROOT / 'wire' / tool / name / op
            work.mkdir(parents=True)
            dst = work / 'dst'
            if op == 'clone':
                q = run([TOOLS[tool], 'clone', '-q', url, 'dst'], work)
            elif op == 'clone-bare':
                q = run([TOOLS[tool], 'clone', '-q', '--bare', url, 'dst.git'], work)
                dst = work / 'dst.git'
            elif op == 'clone-local':
                q = run([TOOLS[tool], 'clone', '-q', str(src), 'dst'], work)
            elif op == 'clone-fsck-objects':
                env = global_config(work, b'[transfer]\n\tfsckObjects = true\n')
                q = run([TOOLS[tool], 'clone', '-q', url, 'dst'], work, env=env)
            elif op == 'clone-fetch-fsck-objects':
                env = global_config(work, b'[fetch]\n\tfsckObjects = true\n[transfer]\n\tfsckObjects = false\n')
                q = run([TOOLS[tool], 'clone', '-q', url, 'dst'], work, env=env)
            elif op == 'clone-fetch-false':
                # fetch.fsckObjects wins over transfer.fsckObjects: no checks.
                env = global_config(work, b'[fetch]\n\tfsckObjects = false\n[transfer]\n\tfsckObjects = true\n')
                q = run([TOOLS[tool], 'clone', '-q', url, 'dst'], work, env=env)
            elif op == 'push':
                dst = work / 'dst.git'
                g(work, 'init', '-q', '--bare', 'dst.git')
                q = run([TOOLS[tool], 'push', '-q', dst.as_uri(), 'refs/heads/main:refs/heads/main',
                         'refs/tags/t:refs/tags/t'], src)
            elif op == 'serve-fetch':
                # The pinned Git fetches from TOOL's upload-pack.
                q = run([GIT, '-c', 'protocol.version=2', 'clone', '-q', '--bare',
                         '--upload-pack=' + TOOLS[tool] + ' upload-pack', url, 'dst.git'], work)
                dst = work / 'dst.git'
            else:
                # The pinned Git pushes into TOOL's receive-pack.
                dst = work / 'dst.git'
                g(work, 'init', '-q', '--bare', 'dst.git')
                if op == 'serve-push-fsck-objects':
                    g(dst, 'config', 'receive.fsckObjects', 'true')
                q = run([GIT, 'push', '-q', '--receive-pack=' + TOOLS[tool] + ' receive-pack', dst.as_uri(),
                         'refs/heads/main:refs/heads/main', 'refs/tags/t:refs/tags/t'], src)
            res[tool] = result(q)
            held[tool] = received(dst, ids) if dst.exists() else None
        if op == 'serve-push-fsck-objects':
            # A refused push leaves the bare repository; what it holds is
            # compared through its refs only.
            held = {t: (None if not (held[t] or {}).get('refs') else held[t]) for t in held}
        record(name, 'wire', op, res['git'], res['den'], extra=held)


def head_bytes(work):
    q = run([GIT, 'cat-file', 'commit', 'HEAD'], work)
    return text(q.stdout) if q.returncode == 0 else None


def replay_family(name, src, ids):
    """What amend, cherry-pick and rebase keep of a shaped author."""
    for op in ('amend', 'cherry-pick', 'rebase'):
        res, made = {}, {}
        for tool in ('git', 'den'):
            work = ROOT / 'replay' / tool / name / op
            shutil.copytree(src, work)
            if op == 'amend':
                (work / 'f').write_bytes(b'one\ntwo\nthree\nfour\n')
                g(work, 'add', 'f')
                q = run([TOOLS[tool], 'commit', '-q', '--amend', '-m', 'amended'], work)
            else:
                # side: the root plus an unrelated commit touching g.
                g(work, 'checkout', '-q', '-b', 'side', ids['root'])
                (work / 'g').write_bytes(b'side\n')
                g(work, 'add', 'g')
                g(work, 'commit', '-q', '-m', 'side')
                if op == 'cherry-pick':
                    q = run([TOOLS[tool], 'cherry-pick', ids['commit']], work)
                else:
                    g(work, 'checkout', '-q', 'main')
                    q = run([TOOLS[tool], 'rebase', 'side'], work)
            res[tool] = result(q)
            made[tool] = head_bytes(work)
        record(name, 'replay', op, res['git'], res['den'], extra=made)


FORMAT_BASIC = '%H|%h|%T|%t|%P|%p|%s|%b|%B|%n|%%|lit'
FORMAT_OPS = [
    ('basic', ['log', '--format=' + FORMAT_BASIC]),
    ('format-prefix', ['log', '--pretty=format:%h %s']),
    ('tformat-prefix', ['log', '--pretty=tformat:%h %s']),
    ('format-name', ['log', '--format=format:%an']),
    ('body-raw', ['log', '-1', '--format=%B']),
    ('body', ['log', '--format=[%b]']),
    ('subject', ['log', '--format=[%s]']),
    ('empty', ['log', '--format=']),
    ('show-format', ['show', '-s', '--format=%h %an %ad']),
    ('date-style', ['log', '--date=iso', '--format=%ad|%cd']),
    ('reverse', ['log', '--reverse', '--format=%h']),
    ('max-count', ['log', '-n', '2', '--format=%h %p']),
]
# Placeholders outside the engine: den refuses each by name.
FORMAT_REFUSED = ['%ar', '%ah', '%cr', '%ch', '%d', '%D', '%e', '%x41', '%C(red)', '%Cred', '%<(10)%s',
                  '%G?', '%N', '%gd', '%m', '%w(10)', '%(trailers)', '%+s', '%-s', '% s', '%f', '%S',
                  '%z', '%']


def format_family():
    work = ROOT / 'format'
    work.mkdir(parents=True)
    g(work, 'init', '-q', '-b', 'main')
    messages = [b'subject line\n\nbody para one\nline two\n\nsecond para\n',
                b'first line\nsecond line of subject\n\nbody\n',
                b'  spaced subject  \n\n\n  indented body\t\n\n',
                b'no newline']
    parent = None
    for i, message in enumerate(messages):
        blob = g(work, 'hash-object', '-w', '--stdin', data=b'content %d\n' % i)
        tree = g(work, 'mktree', data=('100644 blob %s\tf\n' % blob).encode())
        stamp = b' %d +0%d00' % (1700000000 + i, i)
        body = b'tree ' + tree.encode() + b'\n' + (b'parent ' + parent.encode() + b'\n' if parent else b'')
        body += b'author A U Thor <author@example.invalid>' + stamp + b'\n'
        body += b'committer C O Mitter <committer@example.invalid>' + stamp + b'\n\n' + message
        parent = g(work, 'hash-object', '-w', '-t', 'commit', '--stdin', data=body)
    side = g(work, 'commit-tree', tree, '-p', parent, '-m', 'side')
    merge = g(work, 'commit-tree', tree, '-p', parent, '-p', side, '-m', 'merge')
    g(work, 'update-ref', 'refs/heads/main', merge)
    for op, args in FORMAT_OPS:
        res = both(args, work)
        record('history', 'format', op, res['git'], res['den'])
    for placeholder in FORMAT_REFUSED:
        res = both(['log', '-1', '--format=' + placeholder], work)
        REFUSED[('format', 'refuse ' + placeholder)] = 'not yet implemented: history format placeholder'
        record('history', 'format', 'refuse ' + placeholder, res['git'], res['den'])


WRITES = [
    # (case, local config pairs, environment, command after `f` is added)
    ('email-empty-config', [('user.email', '')], {}, ['commit', '-q', '-m', 'w']),
    ('name-empty-config', [('user.name', '')], {}, ['commit', '-q', '-m', 'w']),
    ('email-empty-env', [], {'GIT_AUTHOR_EMAIL': '', 'GIT_COMMITTER_EMAIL': ''}, ['commit', '-q', '-m', 'w']),
    ('name-empty-env', [], {'GIT_AUTHOR_NAME': '', 'GIT_COMMITTER_NAME': ''}, ['commit', '-q', '-m', 'w']),
    ('name-blank-env', [], {'GIT_AUTHOR_NAME': '  '}, ['commit', '-q', '-m', 'w']),
    ('email-blank-config', [('user.email', '  ')], {}, ['commit', '-q', '-m', 'w']),
    ('author-empty-email', [], {}, ['commit', '-q', '-m', 'w', '--author=Some One <>']),
    ('author-empty-name', [], {}, ['commit', '-q', '-m', 'w', '--author= <a@example.invalid>']),
    ('name-brackets-config', [('user.name', 'Jo<e> Q')], {}, ['commit', '-q', '-m', 'w']),
    ('commit-tree-email-empty', [('user.email', '')], {}, ['commit-tree', '-m', 'w', 'TREE']),
    ('commit-tree-name-empty', [('user.name', '')], {}, ['commit-tree', '-m', 'w', 'TREE']),
    ('commit-tree-name-empty-env', [], {'GIT_COMMITTER_NAME': ''}, ['commit-tree', '-m', 'w', 'TREE']),
    ('tag-email-empty', [('user.email', '')], {}, ['tag', '-a', '-m', 'w', 'v1', 'BASE']),
    ('tag-name-empty', [('user.name', '')], {}, ['tag', '-a', '-m', 'w', 'v1', 'BASE']),
]


def write_family():
    for case, config, env, command in WRITES:
        res, made = {}, {}
        for tool in ('git', 'den'):
            work = ROOT / 'write' / tool / case
            work.mkdir(parents=True)
            g(work, 'init', '-q', '-b', 'main')
            (work / 'f').write_bytes(b'one\n')
            g(work, 'add', 'f')
            g(work, 'commit', '-q', '-m', 'base')
            base = g(work, 'rev-parse', 'HEAD')
            tree = g(work, 'rev-parse', 'HEAD^{tree}')
            (work / 'f').write_bytes(b'two\n')
            g(work, 'add', 'f')
            for key, value in config:
                g(work, 'config', key, value)
            argv = [TOOLS[tool]] + [tree if x == 'TREE' else base if x == 'BASE' else x for x in command]
            q = run(argv, work, env=env)
            res[tool] = result(q)
            if command[0] == 'commit-tree':
                made_id = q.stdout.strip().decode() if q.returncode == 0 else ''
            elif command[0] == 'tag':
                made_id = g(work, 'rev-parse', 'refs/tags/v1') if q.returncode == 0 else ''
            else:
                made_id = g(work, 'rev-parse', 'HEAD')
            kind = 'tag' if command[0] == 'tag' else 'commit'
            made[tool] = text(run([GIT, 'cat-file', kind, made_id], work).stdout) if made_id and made_id != base else None
        # A commit-tree success prints its id; ids are compared through the
        # object bytes, which are equal exactly when the ids are.
        record(case, 'write', 'write', res['git'], res['den'], extra=made)


def table():
    ops = []
    for row in rows:
        key = (row['family'], row['op'])
        if key not in ops:
            ops.append(key)
    lines = []
    for family, op in ops:
        lines.append('%s/%s' % (family, op))
        for row in rows:
            if (row['family'], row['op']) != (family, op):
                continue
            mark = '=' if row['same'] else ('R' if row.get('passed') else '!')
            lines.append('  %-22s git: %-34s den: %-46s %s' % (row['shape'], row['git_verdict'][:34],
                                                              row['den_verdict'][:46], mark))
    return '\n'.join(lines) + '\n'


try:
    selected = [s for s in SHAPES if not A.shape or s[0] in A.shape]
    for name, value in selected:
        src, ids = build_source(name, value)
        if 'read' in FAMILIES:
            read_family(name, src, ids)
        if 'fsck' in FAMILIES:
            fsck_family(name, src, ids)
        if 'wire' in FAMILIES:
            wire_family(name, src, ids)
        if 'replay' in FAMILIES:
            replay_family(name, src, ids)
    if 'format' in FAMILIES:
        format_family()
    if 'write' in FAMILIES:
        write_family()
finally:
    (ROOT / 'rows.json').write_text(json.dumps(rows, indent=1))
    (ROOT / 'table.txt').write_text(table())
print(table(), end='')
print('IDENTITY rows=%d passed=%d failed=%d' % (len(rows), len(rows) - len(failures), len(failures)))
if failures and not A.measure:
    sys.exit(1)
