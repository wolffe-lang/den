#!/usr/bin/env python3
"""What a warm `diff --quiet`'s tracked stat pass spends on paths, counted.

The fixture is made with Git alone: 130 files, 10 in the root and 10 in each of 12 directories two levels deep (3
top directories of 4 each), their times set in the past and the index refreshed, so every entry is stat-clean.
probes/status-phases ROOT path-work runs the stat pass `diff --quiet` makes (diff's endpoints: each stage-0 entry,
one verified-ancestor list, in index order) through worktree.tracked_stat_counted and prints its path work:

  checks   each time the pass checks a path's components again. The index read has already checked every path
           once (index.parse refuses a path with an empty, `.`, `..` or `.git` component, or a NUL byte), so the
           pass needs none.
  bytes    the path bytes the pass builds or copies. An owned path or a prefix costs its length; an absolute path
           costs the path twice (its validated text, then the joined string) and the root and a slash. The bound:
           for each clean file its absolute path and one owned copy; for each directory, the first time the
           sorted walk meets it, its prefix and its absolute path. A file's ancestors already verified cost
           nothing more, and a file's path is not copied before it is known to be needed.

The rows hold both exactly: checks 0, and bytes equal to that sum, which the fixture's paths and the root's length
give (the root's length is the probe's own). The counts depend neither on time nor on the order a directory is
listed in, so they are exact on every host and tier.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tier', default='native')
    p.add_argument('--wolf', required=True)
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    out = root / 'target' / ('path-work-' + a.tier)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    git = os.environ['DEN_GIT']
    env = dict(os.environ, HOME=str(out), GIT_CONFIG_NOSYSTEM='1', LC_ALL='C', TZ='UTC',
               GIT_AUTHOR_NAME='Den Tester', GIT_AUTHOR_EMAIL='den@example.invalid',
               GIT_COMMITTER_NAME='Den Tester', GIT_COMMITTER_EMAIL='den@example.invalid',
               GIT_AUTHOR_DATE='1700000000 +0000', GIT_COMMITTER_DATE='1700000000 +0000')
    work = out / 'work'
    subprocess.run([git, 'init', '-q', '-b', 'main', str(work)], check=True, env=env)
    paths, dirs = [], []
    for n in range(10):
        paths.append(f'root-{n:02d}.txt')
    for top in ('alpha', 'beta', 'gamma'):
        dirs.append(top)
        for sub in range(4):
            d = f'{top}/sub-{sub}'
            dirs.append(d)
            for n in range(10):
                paths.append(f'{d}/file-{n:02d}.txt')
    for path in paths:
        f = work / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f'{path}\n')
        os.utime(f, (1700000000, 1700000000))
    subprocess.run([git, 'add', '-A'], cwd=work, check=True, env=env)
    subprocess.run([git, 'commit', '-q', '-m', 'files'], cwd=work, check=True, env=env)
    subprocess.run([git, 'update-index', '--refresh'], cwd=work, check=True, env=env, capture_output=True)
    probe = root / 'target' / a.tier / 'status-phases'
    probe.parent.mkdir(parents=True, exist_ok=True)
    flags = ['--release'] if a.tier == 'release' else []
    subprocess.run([a.wolf, 'build', *flags, '--deny-warnings', str(root / 'probes/status-phases/main.lu'), '-o',
                    str(probe)], cwd=root, check=True)
    r = subprocess.run([str(probe), str(work), 'path-work'], capture_output=True, env=env)
    line = r.stdout.decode(errors='replace').strip()
    fields = dict(f.split('=', 1) for f in line.split() if '=' in f)
    n = {k: int(v) for k, v in fields.items() if v.isdigit()}
    rows = []

    def row(name, ok, detail):
        rows.append(ok)
        print(('PASS ' if ok else 'FAIL ') + name + ': ' + detail, flush=True)

    ok = r.returncode == 0 and n.get('files') == len(paths) and n.get('clean') == len(paths)
    row('path-work-files', ok, f'{line or r.stderr.decode(errors="replace").strip()}; {len(paths)} tracked, all stat-clean')
    base = n.get('root', 0) + 1
    want = sum(base + 3 * len(p.encode()) for p in paths) + sum(base + 3 * len(d.encode()) for d in dirs)
    row('path-work-checks-none', ok and n.get('checks') == 0,
        f'checks={n.get("checks")} for {len(paths)} files; want 0 (the index read has checked each path once)')
    row('path-work-bytes', ok and n.get('bytes') == want,
        f'bytes={n.get("bytes")}, {n.get("bytes", 0) / max(len(paths), 1):.1f} a file; want {want} (each file its '
        f'absolute path and one owned copy, each of {len(dirs)} directories its prefix and absolute path once)')
    failures = rows.count(False)
    print(f'path-work: {len(rows)} rows, {failures} failures; zero skips', flush=True)
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
