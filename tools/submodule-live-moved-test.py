#!/usr/bin/env python3
"""submodule-live-moved: live-wolf-web when a submodule's remote moves mid-row.

Two local plain-HTTP servers (tools/http-git-test.py's gateway, the pinned
git-http-backend) serve a superproject and its one submodule, `sub`, whose
remote has branches main and side. tools/submodule-live-test.py's
live-wolf-web row runs against the superproject (--web-url). Between the
pinned Git's clone and the row's first listing of the submodule's remote
(--between-clones), the submodule's remote moves: side gains a commit and a
new branch, fresh, appears. Git's clone holds the old refs and den's clone,
made after, the new ones, while the row's own listings never see the move.

The row must leave the two moved refs out of its comparison, name them on a
`NARROWED live-wolf-web excluded=sub:refs/heads/fresh,sub:refs/heads/side`
line, and pass. Loopback only. Run through tools/env with the pinned Git.
"""
import argparse
import hashlib
import os
from pathlib import Path
import runpy
import shlex
import shutil
import subprocess
import sys

R = Path(__file__).resolve().parent.parent
GIT_SHA256 = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
BOUND = 600
WANT_NARROWED = 'NARROWED live-wolf-web excluded=sub:refs/heads/fresh,sub:refs/heads/side'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    args = parser.parse_args()
    git = str(Path(os.environ['DEN_GIT']).resolve())
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == GIT_SHA256, 'pinned Git digest'
    if not (R / 'target' / args.tier / 'den').is_file():
        raise SystemExit('FAIL submodule-live-moved-input: build target/' + args.tier + '/den first')
    http_git = runpy.run_path(str(R / 'tools/http-git-test.py'), run_name='http_git')
    Server = http_git['Server']
    srv = R / 'target/live' / ('submodule-live-moved-' + args.tier)
    if srv.exists():
        shutil.rmtree(srv)
    (srv / 'super').mkdir(parents=True)
    (srv / 'sub').mkdir()
    env = dict(os.environ, GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
               GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid')

    def g(*argv, cwd=srv):
        q = subprocess.run([git, *argv], cwd=cwd, env=env, capture_output=True, timeout=120)
        assert q.returncode == 0, (argv, q.stderr.decode(errors='replace')[-300:])
        return q.stdout.decode().strip()

    sub_server = Server(srv / 'sub', git, env, 'plain', None, '', lambda data: None)
    super_server = Server(srv / 'super', git, env, 'plain', None, '', lambda data: None)
    try:
        work = srv / 'sub-work'
        g('init', '-q', '-b', 'main', str(work))
        (work / 'a.txt').write_text('sub one\n')
        g('add', 'a.txt', cwd=work)
        g('commit', '-q', '-m', 'sub one', cwd=work)
        g('branch', 'side', cwd=work)
        g('clone', '-q', '--bare', str(work), str(srv / 'sub/remote.git'))
        sub_git = srv / 'sub/remote.git'
        main = g('--git-dir', str(sub_git), 'rev-parse', 'refs/heads/main')
        # A commit no ref names yet: --between-clones points side and fresh at it.
        moved = g('--git-dir', str(sub_git), 'commit-tree', main + '^{tree}', '-p', main, '-m', 'moved mid-row')
        work = srv / 'super-work'
        g('init', '-q', '-b', 'main', str(work))
        (work / '.gitmodules').write_text('[submodule "sub"]\n\tpath = sub\n\turl = %s\n' % sub_server.url)
        (work / 'README').write_text('superproject\n')
        g('add', '.gitmodules', 'README', cwd=work)
        g('update-index', '--add', '--cacheinfo', '160000,%s,sub' % main, cwd=work)
        g('commit', '-q', '-m', 'superproject', cwd=work)
        g('clone', '-q', '--bare', str(work), str(srv / 'super/remote.git'))
        move = ' && '.join(shlex.join([git, '--git-dir', str(sub_git), 'update-ref', ref, moved])
                           for ref in ('refs/heads/side', 'refs/heads/fresh'))
        argv = [sys.executable, '-I', '-B', str(R / 'tools/submodule-live-test.py'), '--tier', args.tier,
                '--only', '^live-wolf-web$', '--web-url', super_server.url, '--between-clones', move]
        q = subprocess.run(argv, env=dict(os.environ, SHELL='/bin/sh'), capture_output=True, timeout=BOUND)
    finally:
        sub_server.close()
        super_server.close()
    lines = q.stdout.decode('utf-8', 'replace').splitlines() + q.stderr.decode('utf-8', 'replace').splitlines()
    for line in lines:
        print('live| ' + line, flush=True)
    skipped = [line for line in lines if line.startswith('SKIP live-wolf-web ')]
    if skipped and q.returncode == 0:
        # The live row has no network or no root bundle: it measured nothing.
        print('SKIP submodule-live-moved reason=the live row skipped: ' + skipped[0].split(' reason=', 1)[-1],
              flush=True)
        shutil.rmtree(srv, ignore_errors=True)
        return 0
    problems = []
    verdicts = [line for line in lines if line.startswith(('PASS live-wolf-web', 'FAIL live-wolf-web'))]
    if verdicts != ['PASS live-wolf-web']:
        problems.append('verdict %r, not PASS live-wolf-web' % verdicts)
    narrowed = [line for line in lines if line.startswith('NARROWED ')]
    if narrowed != [WANT_NARROWED]:
        problems.append('NARROWED lines %r, not %r' % (narrowed, [WANT_NARROWED]))
    if q.returncode:
        problems.append('the live row exited %d' % q.returncode)
    print(('PASS ' if not problems else 'FAIL ') + 'submodule-live-moved' +
          ('' if not problems else ' ' + '; '.join(problems)), flush=True)
    shutil.rmtree(srv, ignore_errors=True)
    return int(bool(problems))


if __name__ == '__main__':
    raise SystemExit(main())
