#!/usr/bin/env python3
"""The index file's trailing checksum, beside the pinned Git (black-box; no Git source consulted).

Git reads an index without checking its trailing SHA-1, and writes twenty zero bytes in its place when
`index.skipHash` is set (`feature.manyFiles` sets it). Git's fsck checks the trailer: it accepts the zeros and the
content's SHA-1, and refuses anything else with `error: bad index file sha1 signature` and
`fatal: index file corrupt`, exit 128. den reads an index as Git does, and its fsck checks the trailer as Git's
fsck does. Every structural check of a read stays, so a structurally broken index is still refused.

  skiphash-read-*          an index Git wrote with index.skipHash=true (its trailer all zeros): status --porcelain,
                           diff --quiet, diff --cached --quiet and ls-files, each with Git's output and exit, and
                           the index left as it was
  skiphash-add             den's add on that index: Git's add's exit; then Git's status beside the index den wrote
                           equals Git's beside the index Git wrote, and Git's fsck accepts den's (den computes the
                           trailer where Git writes zeros: a stated difference; Git reads either)
  skiphash-fsck            den's fsck on the zero trailer: Git's exit and output
  wrong-trailer-read-*     a sound index with its last trailer byte flipped: the same four reads, each with Git's
                           output and exit, and the index left as it was
  wrong-trailer-fsck       fsck refuses it with Git's two lines and Git's exit
  broken-index-ls-files    an index whose signature is not DIRC, trailer re-signed: ls-files exits as Git's does
                           and names the cause as den's status does, not `den: invalid`
  broken-index-read-*      the same index (a guard, the structural checks stay): status and diff --quiet exit as
                           Git's do, refused by name
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

READS = [['status', '--porcelain'], ['diff', '--quiet'], ['diff', '--cached', '--quiet'], ['ls-files']]
GIT_FSCK_BAD = b'error: bad index file sha1 signature\nfatal: index file corrupt\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', default='native')
    parser.add_argument('--dev-oracle', action='store_true', help='Darwin development evidence only; not the pinned Linux oracle')
    a = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target' / ('index-trailer-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    digest = hashlib.sha256(Path(git).read_bytes()).hexdigest()
    if a.dev_oracle:
        assert os.uname().sysname == 'Darwin', 'development oracle is Darwin-only'
        print('DEV ORACLE (not pinned Linux evidence):', digest, flush=True)
    else:
        assert digest == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
    den = str(root / 'target' / a.tier / 'den')
    home = out / 'home'
    home.mkdir()
    env = dict(os.environ, HOME=str(home), GIT_CONFIG_NOSYSTEM='1', GIT_OPTIONAL_LOCKS='0', LC_ALL='C', TZ='UTC',
               GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
               GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid',
               GIT_AUTHOR_DATE='1700000000 +0000', GIT_COMMITTER_DATE='1700000000 +0000')
    rows = []

    def row(name, ok, detail):
        rows.append(ok)
        print(('PASS ' if ok else 'FAIL ') + name + ': ' + detail, flush=True)

    def run(tool, argv, cwd):
        p = subprocess.run([tool, *argv], cwd=cwd, capture_output=True, env=env, timeout=60)
        return p.returncode, p.stdout, p.stderr

    def setup(cwd):
        subprocess.run([git, *cwd[1]], cwd=cwd[0], check=True, capture_output=True, env=env)

    def seed(name, skip):
        repo = out / name
        subprocess.run([git, 'init', '-q', '-b', 'main', str(repo)], check=True, capture_output=True, env=env)
        if skip:
            setup((repo, ['config', 'index.skipHash', 'true']))
        (repo / 'a.txt').write_text('hello\n')
        (repo / 'dir').mkdir()
        (repo / 'dir' / 'b.txt').write_text('two\n')
        setup((repo, ['add', '-A']))
        setup((repo, ['commit', '-q', '-m', 'one']))
        return repo

    def label(argv):
        return '-'.join(x.lstrip('-') for x in argv)

    def reads(prefix, repo):
        index = repo / '.git' / 'index'
        before = index.read_bytes()
        for argv in READS:
            d = run(den, argv, repo)
            g = run(git, argv, repo)
            same = d == g
            kept = index.read_bytes() == before
            row(f'{prefix}-read-{label(argv)}', same and kept,
                f'git {g[0]} den {d[0]}; same output {same}; index left as it was {kept}' +
                ('' if same else f'; git {g[1][-80:]!r} {g[2][-120:]!r} den {d[1][-80:]!r} {d[2][-120:]!r}'))

    # An index Git wrote with index.skipHash: its trailer is twenty zero bytes.
    skip = seed('skiphash', True)
    assert (skip / '.git' / 'index').read_bytes()[-20:] == bytes(20), 'Git did not write the zero trailer'
    reads('skiphash', skip)
    by_den, by_git = out / 'skiphash-den-add', out / 'skiphash-git-add'
    shutil.copytree(skip, by_den)
    shutil.copytree(skip, by_git)
    for repo in (by_den, by_git):
        (repo / 'a.txt').write_text('hello again\n')
    d = run(den, ['add', 'a.txt'], by_den)
    g = run(git, ['add', 'a.txt'], by_git)
    after_den, after_git = run(git, ['status', '--porcelain'], by_den), run(git, ['status', '--porcelain'], by_git)
    fsck_den = run(git, ['fsck'], by_den)
    row('skiphash-add', d[0] == g[0] == 0 and after_den == after_git and fsck_den[0] == 0,
        f'add: git {g[0]} den {d[0]} {d[2][-120:]!r}; Git status beside each index the same {after_den == after_git}; '
        f'Git fsck on den\'s index {fsck_den[0]} {fsck_den[2][-120:]!r}; den\'s trailer is zero '
        f'{(by_den / ".git" / "index").read_bytes()[-20:] == bytes(20)} (Git\'s: zero)')
    d, g = run(den, ['fsck'], skip), run(git, ['fsck'], skip)
    row('skiphash-fsck', d[0] == g[0] and d[1] == g[1],
        f'git {g[0]} den {d[0]} {d[2][-160:]!r}')

    # A sound index whose last trailer byte is flipped.
    wrong = seed('wrong-trailer', False)
    index = wrong / '.git' / 'index'
    body = bytearray(index.read_bytes())
    body[-1] ^= 1
    index.write_bytes(bytes(body))
    reads('wrong-trailer', wrong)
    d, g = run(den, ['fsck'], wrong), run(git, ['fsck'], wrong)
    row('wrong-trailer-fsck', g[0] == 128 and g[2] == GIT_FSCK_BAD and d[0] == g[0] and d[2] == g[2],
        f'git {g[0]} {g[2]!r} den {d[0]} {d[2][-160:]!r}')

    # An index whose signature is not DIRC, its trailer re-signed: structurally broken, and refused by Git the same
    # way on every run (a cut inside an entry leaves Git reading trailer bytes as an entry, which vary with the stat
    # words).
    broken = seed('broken-index', False)
    index = broken / '.git' / 'index'
    body = b'DIRX' + index.read_bytes()[4:-20]
    index.write_bytes(body + hashlib.sha1(body).digest())
    d, g = run(den, ['ls-files'], broken), run(git, ['ls-files'], broken)
    status = run(den, ['status', '--porcelain'], broken)
    row('broken-index-ls-files', g[0] == 128 and d[0] == g[0] and d[2] == status[2] and b'den: invalid' not in d[2],
        f'git {g[0]} den {d[0]} {d[2][-120:]!r}; den status says {status[2][-120:]!r}')
    for argv in (['status', '--porcelain'], ['diff', '--quiet']):
        d, g = run(den, argv, broken), run(git, argv, broken)
        row(f'broken-index-read-{label(argv)}', g[0] == 128 and d[0] == g[0] and d[2].startswith(b'fatal: '),
            f'git {g[0]} den {d[0]} {d[2][-120:]!r}')

    failures = rows.count(False)
    print(f'index-trailer: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
