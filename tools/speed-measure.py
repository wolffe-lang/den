"""Speed rows beside the pinned Git: diff --quiet, diff --cached --quiet, pull.

The rows have the status row's shape (status-measure.py): the 454-file
fixture, a cold index (copied stat words) and a warm one (refreshed), samples
interleaved between the tools, child user+system CPU summed to a floor, the
minimum over the samples, and a row passes when ratio x guardband <= ceiling
with every run's process bytes and end state equal to Git's. Ceilings and the
guardband are tools/speed-bounds.json's, one line per row to ratchet.

  diff-quiet         `diff --quiet` on the clean work tree;
  diff-cached-quiet  `diff --cached --quiet`;
  pull               `pull --ff-only origin main` of one commit over file://
                     that changes twelve files, adds three and removes two.

Nothing but the tool is timed: the index (and, for pull, the repository
directory, the changed files and the refresh of the warm index) is restored
before each child. A dirty-index witness holds the two diff forms to Git's
exit 1 before any sample, so equal bytes are not only equal silence. Peak
resident sets are read once more through tools/minimal-parent.c (a child's
peak starts at its parent's) and stated for status too; they are not gated.

Intended for an exclusive performance block, not a light slot or mixed cores.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parent.parent
STATES = ('cold', 'warm')
ROWS = ('status', 'diff-quiet', 'diff-cached-quiet', 'pull')
MTIME = 1_700_000_000_123456789
GIT_SHA256 = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'


def load_bounds(path=ROOT / 'tools/speed-bounds.json'):
    """The ratchet table: {'guardband': g, 'rows': {row: {state: ceiling}}}."""
    table = json.loads(Path(path).read_text())
    assert set(table) == {'guardband', 'rows'}, sorted(table)
    assert set(table['rows']) == set(ROWS), sorted(table['rows'])
    for row, states in table['rows'].items():
        assert set(states) == set(STATES), (row, sorted(states))
    return table


def verdict(ratio, ceiling, guardband):
    """A multiplicative uncertainty of the guardband must still fit the ceiling."""
    return ratio * guardband <= ceiling


def pseudorandom(seed, size):
    # Hash-counter bytes, as status-fixture.py's: stable across machines.
    data = bytearray()
    counter = 0
    while len(data) < size:
        data.extend(hashlib.sha256(seed + counter.to_bytes(8, 'big')).digest())
        counter += 1
    return bytes(data[:size])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--fixture', type=Path, required=True)
    p.add_argument('--den', type=Path, required=True)
    p.add_argument('--tier', required=True)
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--samples', type=int, default=5)
    p.add_argument('--cpu-floor', type=float, default=0.2)
    p.add_argument('--rows', default='diff-quiet,diff-cached-quiet,pull')
    p.add_argument('--bounds', type=Path, default=ROOT / 'tools/speed-bounds.json')
    a = p.parse_args()
    G = Path(os.environ['DEN_GIT'])
    assert hashlib.sha256(G.read_bytes()).hexdigest() == GIT_SHA256
    assert a.samples >= 3 and a.cpu_floor >= 0.1
    bounds = load_bounds(a.bounds)
    guard = bounds['guardband']
    chosen = [r for r in a.rows.split(',') if r]
    assert chosen and all(r in ROWS[1:] for r in chosen), chosen
    den = a.den.resolve()
    parent = a.parent.resolve()
    fixture = a.fixture.resolve()
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    tools = [('git', G), ('den', den)]

    def git(*args, cwd):
        q = subprocess.run([str(G), *args], cwd=cwd, capture_output=True, env=env)
        assert q.returncode == 0, (args, q.stdout[-300:], q.stderr[-300:])
        return q.stdout

    def digest(data):
        return hashlib.sha256(data).hexdigest()

    # The status fixture's own case: status and the two diff forms.
    case = fixture / 'case'
    index = case / '.git/index'
    inputs = {s: (fixture / (s + '.index')).read_bytes() for s in STATES}

    def restore_index(state):
        index.write_bytes(inputs[state])

    def observe_index():
        return dict(index=digest(index.read_bytes()))

    # The pull fixture: the same shape again, with a remote one commit ahead.
    pull = fixture / 'pull'
    pcase = pull / 'case'
    pindex = pcase / '.git/index'
    before = pull / 'git-before'
    if not (pull / 'pull.json').exists():
        shutil.rmtree(pull, ignore_errors=True)
        pull.mkdir()
        upstream = pull / 'upstream'
        git('clone', '-q', '--no-local', str(fixture / 'source'), str(upstream), cwd=pull)
        names = ['src/d%02d/f%03d.bin' % (n // 30, n) for n in range(453)]
        modified = [names[n] for n in range(7, 453, 41)][:12]
        removed = [names[19], names[230]]
        added = ['src/d00/added-0.txt', 'src/d07/added-1.txt', 'src/d14/added-2.bin']
        for n, name in enumerate(modified):
            f = upstream / name
            f.write_bytes(pseudorandom(('pulled-%d' % n).encode(), f.stat().st_size))
        for name in removed:
            (upstream / name).unlink()
        for n, name in enumerate(added):
            body = (pseudorandom(b'added-%d' % n, 4096) if name.endswith('.bin')
                    else b''.join(b'added line %d of file %d\n' % (k, n) for k in range(200)))
            (upstream / name).write_bytes(body)
        git('add', '-A', '.', cwd=upstream)
        git('commit', '-qm', 'the pulled change', cwd=upstream)
        tip = git('rev-parse', 'HEAD', cwd=upstream).decode().strip()
        origin = pull / 'origin.git'
        git('clone', '-q', '--bare', '--no-local', str(upstream), str(origin), cwd=pull)
        subprocess.run(['cp', '-a', str(case), str(pcase)], check=True)
        git('remote', 'add', 'origin', origin.as_uri(), cwd=pcase)
        git('config', 'branch.main.remote', 'origin', cwd=pcase)
        git('config', 'branch.main.merge', 'refs/heads/main', cwd=pcase)
        # cp -a kept the mtimes and changed inode and ctime: this index is cold.
        (pull / 'cold.index').write_bytes(inputs['cold'])
        pindex.write_bytes(inputs['cold'])
        git('update-index', '--refresh', cwd=pcase)
        (pull / 'warm.index').write_bytes(pindex.read_bytes())
        shutil.copytree(pcase / '.git', before)
        (before / 'index').unlink()
        (pull / 'pull.json').write_text(json.dumps(dict(
            tip=tip, base=git('rev-parse', 'HEAD', cwd=pcase).decode().strip(),
            modified=modified, removed=removed, added=added), indent=2) + '\n')
    shape = json.loads((pull / 'pull.json').read_text())
    pinputs = {s: (pull / (s + '.index')).read_bytes() for s in STATES}
    originals = {name: (fixture / 'source' / name).read_bytes()
                 for name in shape['modified'] + shape['removed']}

    def restore_pull(state):
        for name in shape['added']:
            (pcase / name).unlink(missing_ok=True)
        for name, body in originals.items():
            f = pcase / name
            if not f.is_file() or f.read_bytes() != body:
                f.write_bytes(body)
                os.utime(f, ns=(MTIME, MTIME))
        shutil.rmtree(pcase / '.git')
        shutil.copytree(before, pcase / '.git')
        pindex.write_bytes(pinputs[state])
        if state == 'warm':
            # The rewritten files have new inode and ctime words: refresh them,
            # untimed, so a warm pull starts from an index that matches lstat.
            git('update-index', '--refresh', cwd=pcase)

    def observe_pull():
        refs = subprocess.run([str(G), 'rev-parse', 'HEAD', 'refs/remotes/origin/main'],
                              cwd=pcase, capture_output=True, env=env)
        tree = hashlib.sha256()
        for name in shape['modified'] + shape['removed'] + shape['added']:
            f = pcase / name
            tree.update(name.encode() + b'\0' + (digest(f.read_bytes()) if f.is_file() else 'absent').encode() + b'\n')
        return dict(refs=refs.stdout.decode(), refs_status=refs.returncode,
                    entries=digest(git('ls-files', '-s', cwd=pcase)), files=tree.hexdigest())

    rows = {
        'status': dict(argv=['status', '--porcelain'], cwd=case, restore=restore_index, observe=observe_index, expect=0),
        'diff-quiet': dict(argv=['diff', '--quiet'], cwd=case, restore=restore_index, observe=observe_index, expect=0),
        'diff-cached-quiet': dict(argv=['diff', '--cached', '--quiet'], cwd=case, restore=restore_index,
                                  observe=observe_index, expect=0),
        'pull': dict(argv=['pull', '--ff-only', 'origin', 'main'], cwd=pcase, restore=restore_pull,
                     observe=observe_pull, expect=0),
    }

    def child(exe, row):
        c0 = resource.getrusage(resource.RUSAGE_CHILDREN)
        t0 = time.perf_counter_ns()
        q = subprocess.run([str(exe), *row['argv']], cwd=row['cwd'], env=env, capture_output=True, timeout=600)
        wall = (time.perf_counter_ns() - t0) / 1e9
        c1 = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu = (c1.ru_utime - c0.ru_utime) + (c1.ru_stime - c0.ru_stime)
        return dict(status=q.returncode, stdout=q.stdout.hex(), stderr=q.stderr.hex(), cpu=cpu, wall=wall)

    def key(q):
        return json.dumps([q['status'], q['stdout'], q['stderr'], q['after']], sort_keys=True)

    report = a.output.parent / (a.output.name + '.usage')

    def peak(exe, row):
        report.unlink(missing_ok=True)
        q = subprocess.run([str(parent), str(report), str(exe), *row['argv']], cwd=row['cwd'], env=env,
                           capture_output=True, timeout=600)
        assert q.returncode == 0, ('minimal parent', q.returncode)
        status, maxrss, _user, _system, _wall = report.read_text().split()
        assert int(status) == row['expect'], (row['argv'], status)
        return int(maxrss)

    out = dict(tier=a.tier, guardband=guard, witness=[], samples=[], memory=[], verdicts=[])
    failed = False
    try:
        # The dirty witness: one index entry names another file's blob, so the
        # work tree and HEAD both differ from the index. Both forms must exit 1.
        if 'diff-quiet' in chosen or 'diff-cached-quiet' in chosen:
            other = git('rev-parse', ':src/d00/f001.bin', cwd=case).decode().strip()
            for form in ('diff-quiet', 'diff-cached-quiet'):
                seen = {}
                for name, exe in tools:
                    restore_index('warm')
                    git('update-index', '--cacheinfo', '100644,' + other + ',src/d00/f000.bin', cwd=case)
                    q = child(exe, rows[form])
                    seen[name] = (q['status'], q['stdout'], q['stderr'])
                same = seen['git'] == seen['den'] and seen['git'][0] == 1
                failed = failed or not same
                out['witness'].append(dict(row=form, same=same, git=seen['git'], den=seen['den']))
                print(('PASS' if same else 'FAIL'), '%s-dirty-witness-%s' % (form, a.tier),
                      'git=%d den=%d' % (seen['git'][0], seen['den'][0]), flush=True)
            restore_index('warm')
        cap = 4096
        for sample in range(a.samples):
            order = list(tools)
            if sample % 2:
                order.reverse()
            for name_row in chosen:
                row = rows[name_row]
                for state in STATES:
                    for name, exe in order:
                        results, elapsed = [], 0.0
                        while elapsed < a.cpu_floor and len(results) < cap:
                            row['restore'](state)
                            q = child(exe, row)
                            q['after'] = row['observe']()
                            results.append(q)
                            elapsed += q['cpu']
                            if q['status'] != row['expect']:
                                break
                        keys = sorted({key(q) for q in results})
                        out['samples'].append(dict(
                            row=name_row, sample=sample, state=state, tool=name, runs=len(results),
                            mean_cpu=elapsed / len(results),
                            mean_wall=sum(q['wall'] for q in results) / len(results),
                            cpu_floor_reached=elapsed >= a.cpu_floor,
                            statuses=sorted({q['status'] for q in results}),
                            outcomes=keys, first=results[0]))
                        print('SAMPLE', sample, name_row, state, name, 'runs=' + str(len(results)),
                              'cpu=%.6f' % (elapsed / len(results)), flush=True)
        # Peaks, untimed: every row and status, each tool three times, the least.
        floor_kib = min(peak('/bin/true', dict(argv=[], cwd=fixture, expect=0)) for _ in range(3))
        memory = {}
        for name_row in ['status'] + chosen:
            row = rows[name_row]
            for state in STATES:
                for name, exe in tools:
                    kib = []
                    for _ in range(3):
                        row['restore'](state)
                        kib.append(peak(exe, row))
                    memory[name_row, state, name] = min(kib)
                out['memory'].append(dict(row=name_row, state=state, git_kib=memory[name_row, state, 'git'],
                                          den_kib=memory[name_row, state, 'den'], floor_kib=floor_kib))
                print('MEMORY %s-peak-%s-%s' % (name_row, state, a.tier),
                      'den_kib=%d git_kib=%d floor_kib=%d' % (memory[name_row, state, 'den'],
                                                              memory[name_row, state, 'git'], floor_kib), flush=True)
        for name_row in chosen:
            for state in STATES:
                both = [s for s in out['samples'] if s['row'] == name_row and s['state'] == state]
                left = [s for s in both if s['tool'] == 'git']
                right = [s for s in both if s['tool'] == 'den']
                valid = all(s['cpu_floor_reached'] and s['statuses'] == [rows[name_row]['expect']] for s in both)
                expected = {k for s in left for k in s['outcomes']}
                actual = {k for s in right for k in s['outcomes']}
                same = expected == actual and len(expected) == 1
                den_cpu = min(s['mean_cpu'] for s in right)
                git_cpu = min(s['mean_cpu'] for s in left)
                ratio = den_cpu / git_cpu
                ceiling = bounds['rows'][name_row][state]
                ok = valid and same and verdict(ratio, ceiling, guard)
                failed = failed or not ok
                print(('PASS' if ok else 'FAIL'), '%s-ratio-%s-%s' % (name_row, state, a.tier),
                      'ratio=%.6f guardband=%.2f ceiling=%g' % (ratio, guard, ceiling),
                      'den_cpu=%.6f git_cpu=%.6f' % (den_cpu, git_cpu),
                      'den_kib=%d git_kib=%d' % (memory[name_row, state, 'den'], memory[name_row, state, 'git']),
                      'process_same=' + str(same) + ('' if valid else ' valid=False'), flush=True)
                out['verdicts'].append(dict(row=name_row, state=state, ok=ok, valid=valid, same=same, ratio=ratio,
                                            den_cpu=den_cpu, git_cpu=git_cpu, ceiling=ceiling))
    finally:
        restore_index('warm')
        report.unlink(missing_ok=True)
        a.output.parent.mkdir(parents=True, exist_ok=True)
        out.update(fixture_sha256=digest((fixture / 'fixture.json').read_bytes()),
                   den_sha256=digest(den.read_bytes()), pull=shape, environment=env)
        a.output.write_text(json.dumps(out, indent=2) + '\n')
    return int(failed or len(out['verdicts']) != len(chosen) * len(STATES))


if __name__ == '__main__':
    raise SystemExit(main())
