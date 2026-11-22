#!/usr/bin/env python3
"""submodule-live-unreachable: live-wolf-web when the host goes away mid-row.

A local plain-HTTP server (tools/http-live-stall-test.py's, through the
pinned git-http-backend) serves a superproject, and another serves its one
submodule, `sub`. tools/submodule-live-test.py's live-wolf-web row runs
against the superproject (--web-url) with its unreachable pause at PAUSE
seconds (DEN_LIVE_UNREACHABLE_PAUSE). Right after the superproject's server
sends its first fetch response (the pinned Git's clone, which runs first) it
stops listening, so each later connection to it is refused, as in a network
outage:

  submodule-live-unreachable-once   the server listens again 2 s after it
                         stopped, within the pause: one `RETRY live-wolf-web
                         unreachable=ls-remote-after` line (den's clone,
                         refused too, is never a reason to rerun), then PASS
                         live-wolf-web.
  submodule-live-unreachable-twice  the server never listens again: the same
                         RETRY line, then FAIL live-wolf-web naming the
                         second attempt's failed reads, and no third.

Loopback only, besides the live row's own check that github.com answers.
Run through tools/env with the pinned Git.
"""
import argparse
import hashlib
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys

R = Path(__file__).resolve().parent.parent
GIT_SHA256 = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
BOUND = 600
PAUSE = 4
WANT = {
    'once': (['RETRY live-wolf-web unreachable=ls-remote-after'], ['PASS live-wolf-web'], 0),
    'twice': (['RETRY live-wolf-web unreachable=ls-remote-after'],
              ['FAIL live-wolf-web pinned Git could not reach wolf-web twice: ls-remote-before,git'], 1),
}


def scenario(outage, tier, git, Server, StallServer):
    name = 'submodule-live-unreachable-' + outage
    srv = R / 'target/live' / ('%s-%s' % (name, tier))
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
    super_server = None
    try:
        work = srv / 'sub-work'
        g('init', '-q', '-b', 'main', str(work))
        (work / 'a.txt').write_text('sub one\n')
        g('add', 'a.txt', cwd=work)
        g('commit', '-q', '-m', 'sub one', cwd=work)
        g('clone', '-q', '--bare', str(work), str(srv / 'sub/remote.git'))
        main = g('--git-dir', str(srv / 'sub/remote.git'), 'rev-parse', 'refs/heads/main')
        work = srv / 'super-work'
        g('init', '-q', '-b', 'main', str(work))
        (work / '.gitmodules').write_text('[submodule "sub"]\n\tpath = sub\n\turl = %s\n' % sub_server.url)
        (work / 'README').write_text('superproject\n')
        g('add', '.gitmodules', 'README', cwd=work)
        g('update-index', '--add', '--cacheinfo', '160000,%s,sub' % main, cwd=work)
        g('commit', '-q', '-m', 'superproject', cwd=work)
        g('clone', '-q', '--bare', str(work), str(srv / 'super/remote.git'))
        super_server = StallServer(srv / 'super', git, env, 0, None, outage)
        argv = [sys.executable, '-I', '-B', str(R / 'tools/submodule-live-test.py'), '--tier', tier,
                '--only', '^live-wolf-web$', '--web-url', super_server.url]
        q = subprocess.run(argv, env=dict(os.environ, SHELL='/bin/sh', DEN_LIVE_UNREACHABLE_PAUSE=str(PAUSE)),
                           capture_output=True, timeout=BOUND)
    finally:
        sub_server.close()
        if super_server is not None:
            super_server.close()
    lines = q.stdout.decode('utf-8', 'replace').splitlines() + q.stderr.decode('utf-8', 'replace').splitlines()
    for line in lines:
        print('live| ' + line, flush=True)
    skipped = [line for line in lines if line.startswith('SKIP live-wolf-web ')]
    if skipped and q.returncode == 0:
        print('SKIP %s reason=the live row skipped: %s' % (name, skipped[0].split(' reason=', 1)[-1]), flush=True)
        shutil.rmtree(srv, ignore_errors=True)
        return True
    want_retries, want_verdicts, want_exit = WANT[outage]
    retries = [line for line in lines if line.startswith('RETRY ')]
    verdicts = [line for line in lines if line.startswith(('PASS live-wolf-web', 'FAIL live-wolf-web'))]
    problems = []
    if retries != want_retries:
        problems.append('RETRY lines %r, not %r' % (retries, want_retries))
    if verdicts != want_verdicts:
        problems.append('verdict %r, not %r' % (verdicts, want_verdicts))
    if (q.returncode != 0) != bool(want_exit):
        problems.append('the live row exited %d' % q.returncode)
    if super_server.went_down is None:
        problems.append('the server never stopped listening')
    print(('PASS ' if not problems else 'FAIL ') + name + ('' if not problems else ' ' + '; '.join(problems)),
          flush=True)
    shutil.rmtree(srv, ignore_errors=True)
    return not problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tier', choices=('native', 'release'), default='native')
    args = parser.parse_args()
    git = str(Path(os.environ['DEN_GIT']).resolve())
    assert hashlib.sha256(Path(git).read_bytes()).hexdigest() == GIT_SHA256, 'pinned Git digest'
    if not (R / 'target' / args.tier / 'den').is_file():
        raise SystemExit('FAIL submodule-live-unreachable-input: build target/' + args.tier + '/den first')
    Server = runpy.run_path(str(R / 'tools/http-git-test.py'), run_name='http_git')['Server']
    StallServer = runpy.run_path(str(R / 'tools/http-live-stall-test.py'), run_name='http_live_stall')['StallServer']
    failed = [outage for outage in ('once', 'twice') if not scenario(outage, args.tier, git, Server, StallServer)]
    if failed:
        raise SystemExit('FAIL submodule-live-unreachable: ' + ', '.join(failed))
    print('submodule-live-unreachable: %s once,twice' % args.tier, flush=True)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (AssertionError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        raise SystemExit('FAIL submodule-live-unreachable-harness: ' + str(exc))
