#!/usr/bin/env python3
"""status's memory, counted in minor page faults: one warm `status --porcelain`
on the speed rows' fixture (tools/status-fixture.py: 454 files), den against
its bound and beside the pinned Git.

Each tool runs 9 times from the restored warm index with optional locks off
(GIT_OPTIONAL_LOCKS=0), straight from this process. A run's faults are the
RUSAGE_CHILDREN difference across that one child: a child's faults count from
its exec, so this process's own size does not enter them (a peak would; peaks
are read through tools/minimal-parent.c and are not bound here). The row keeps
the least of the 9.

den runs from a copy of its binary in memory (memfd_create(2), executed as
/proc/self/fd/N), not from the file the build wrote. A fault maps the binary's
pages as the host's page cache holds them: a kernel that caches a file in large
folios maps more pages per fault, so the same binary read 11 to 14 fewer faults
from a fresh build directory than from a memory copy, and its count moved by 11
between two build directories. A memory copy maps one page per fault on every
host, so the row counts den's work and not the cache's layout. Git runs from its
pinned path: its count is printed beside den's and bound to nothing.

A minor fault is a page the process touches for the first time. den's ambient
region never frees (wolf-lang#191), so its faults past start-up follow the
bytes a status allocates: 22 chunks of 64 KiB on this fixture before the walk
kept its scratch in a region per directory. The bounds, warm status:

  status-faults-warm-native    at most 441 faults (571 before)
  status-faults-warm-release   at most 415 faults (544 before)

They are the change's predicted ceiling, from a measure that ran the base and
the head interleaved in one hold, through the minimal parent for peaks: every
comparison of den's memory is taken that way, never across two holds, whose
spread alone moves a peak by 0.5 MiB.

Linux only: a macOS page is 16 KiB and the fixture needs the pinned Linux Git,
so elsewhere each row SKIPs by name.
"""
import argparse
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys

R = Path(__file__).resolve().parent.parent
BOUND = {'native': 441, 'release': 415}
RUNS = 9


def least_faults(argv, repo, index, warm, env, keep=()):
    """The least minor faults of RUNS runs of argv in repo, each from the warm
    index, with the descriptors keep left open in the child; the first run's
    process output, which every run must repeat."""
    counts, first = [], None
    for _ in range(RUNS):
        index.write_bytes(warm)
        c0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        q = subprocess.run(argv, cwd=repo, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=120,
                           pass_fds=keep)
        c1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        out = (q.returncode, q.stdout, q.stderr)
        if first is None:
            first = out
        elif out != first:
            raise SystemExit('FAIL status-faults-harness: %s did not repeat its output' % argv[0])
        counts.append(c1.ru_minflt - c0.ru_minflt)
    return min(counts), first


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tier', choices=('native', 'release'), default='native')
    a = p.parse_args()
    name = 'status-faults-warm-' + a.tier
    if not sys.platform.startswith('linux'):
        print('SKIP %s reason=Linux only (a macOS page is 16 KiB; the fixture needs the pinned Linux Git)' % name,
              flush=True)
        return
    den = R / 'target' / a.tier / 'den'
    if not den.is_file():
        raise SystemExit('FAIL status-faults-input: build target/%s/den first' % a.tier)
    git = str(Path(os.environ['DEN_GIT']).resolve())
    root = R / 'target' / ('status-faults-' + a.tier)
    if root.exists():
        shutil.rmtree(root)
    q = subprocess.run([sys.executable, '-I', '-B', str(R / 'tools/status-fixture.py'), '--root', str(root)],
                       capture_output=True, timeout=600)
    if q.returncode:
        raise SystemExit('FAIL status-faults-fixture: ' + q.stderr.decode('utf-8', 'replace')[-300:])
    repo = root / 'case'
    index = repo / '.git/index'
    warm = (root / 'warm.index').read_bytes()
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    image = os.memfd_create('den-' + a.tier)
    with open(den, 'rb') as source, os.fdopen(os.dup(image), 'wb') as copy:
        shutil.copyfileobj(source, copy)
    in_memory = '/proc/self/fd/%d' % image
    mine, ours = least_faults([in_memory, 'status', '--porcelain'], repo, index, warm, env, (image,))
    os.close(image)
    theirs_faults, theirs = least_faults([git, 'status', '--porcelain'], repo, index, warm, env)
    problems = []
    if ours != theirs:
        problems.append('den status exit %d differs from Git\'s %d, or its output does' % (ours[0], theirs[0]))
    if mine > BOUND[a.tier]:
        problems.append('%d faults over the bound %d' % (mine, BOUND[a.tier]))
    print('FAULTS %s den=%d git=%d bound=%d runs=%d' % (name, mine, theirs_faults, BOUND[a.tier], RUNS), flush=True)
    print(('PASS ' if not problems else 'FAIL ') + name + ('' if not problems else ' ' + '; '.join(problems)),
          flush=True)
    shutil.rmtree(root)
    if problems:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
