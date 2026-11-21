"""Measure cold/warm status and optional index refresh; same-host CPU ratios.

Restores the captured index before each timed child, never times restoration or
fixture hashing. Samples are interleaved, use child user+system CPU, and retain
raw process bytes plus exact before/after indexes. Intended for an exclusive
performance block, not a light slot or mixed-core block. The ceilings, the
guardband, the statistic and each index state's sampling are
tools/speed-bounds.json's "status" lines, read through speed-measure.py, whose
rows share this one's shape and whose judge() this one uses; --tier names the
build in each row.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import runpy
import subprocess
import time

p = argparse.ArgumentParser()
p.add_argument('--fixture', type=Path, required=True)
p.add_argument('--den', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--samples', type=int, default=3)
p.add_argument('--tier', default='native', choices=['native', 'release'])
p.add_argument('--cpu-floor', type=float, default=0.2)
p.add_argument('--profile-only', action='store_true')
a = p.parse_args()
G = Path(os.environ['DEN_GIT'])
assert hashlib.sha256(G.read_bytes()).hexdigest() == 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
assert a.samples >= 3 and a.cpu_floor >= 0.1
shared = runpy.run_path(str(Path(__file__).resolve().parent / 'speed-measure.py'))
bounds = shared['load_bounds']()
guard = bounds['guardband']
fixture = a.fixture.resolve()
repo = fixture / 'case'
index = repo / '.git/index'
inputs = {label: (fixture / (label + '.index')).read_bytes() for label in ['cold', 'warm']}
rows, refresh = [], []
env = dict(os.environ)


def child(exe, optional, keep=True):
    """One status run. keep: the index's bytes before and after in hex (the
    refresh witnesses); a timed run keeps their digests, since a 1 s floor
    takes a thousand runs of Git's status."""
    e = dict(env, GIT_OPTIONAL_LOCKS=str(optional))
    before = index.read_bytes()
    c0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.perf_counter_ns()
    q = subprocess.run([str(exe), 'status', '--porcelain'], cwd=repo, env=e,
                       capture_output=True, timeout=600)
    wall = (time.perf_counter_ns() - t0) / 1e9
    c1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (c1.ru_utime - c0.ru_utime) + (c1.ru_stime - c0.ru_stime)
    after = index.read_bytes()
    shown = (lambda b: b.hex()) if keep else (lambda b: hashlib.sha256(b).hexdigest())
    return dict(status=q.returncode, stdout=q.stdout.hex(), stderr=q.stderr.hex(),
                cpu=cpu, wall=wall, index_before=shown(before), index_after=shown(after),
                index_changed=before != after)


try:
    # Two consecutive commands witness opportunistic refresh separately from
    # the restored-input perf samples. No assumptions from exit=0 alone.
    for label in ['cold', 'warm']:
        for optional in [0, 1]:
            for name, exe in [('git', G), ('den', a.den.resolve())]:
                index.write_bytes(inputs[label])
                for invocation in [1, 2]:
                    q = child(exe, optional)
                    refresh.append(dict(state=label, optional_locks=optional, tool=name,
                                        invocation=invocation, result=q))
                    print('REFRESH', label, optional, name, invocation,
                          'cpu=%.6f' % q['cpu'], 'wall=%.6f' % q['wall'],
                          'index_changed=' + str(q['index_changed']), flush=True)
    if not a.profile_only:
        plan = {label: shared['sampling'](bounds, 'status', label, a.samples, a.cpu_floor) for label in ['cold', 'warm']}
        for sample in range(max(n for n, _ in plan.values())):
            order = [('git', G), ('den', a.den.resolve())]
            if sample % 2:
                order.reverse()
            for label in ['cold', 'warm']:
                count, floor = plan[label]
                if sample >= count:
                    continue
                for name, exe in order:
                    results, elapsed = [], 0.0
                    while elapsed < floor and len(results) < shared['RUN_CAP']:
                        index.write_bytes(inputs[label])
                        q = child(exe, 0, keep=False)
                        results.append(q)
                        elapsed += q['cpu']
                        if q['status']:
                            break
                    rows.append(dict(sample=sample, state=label, tool=name, runs=len(results),
                                     outcomes=sorted({(q['status'], q['stdout'], q['stderr']) for q in results}),
                                     statuses=sorted({q['status'] for q in results}),
                                     index_changed=any(q['index_changed'] for q in results),
                                     first=results[0], mean_cpu=elapsed / len(results),
                                     mean_wall=sum(x['wall'] for x in results) / len(results),
                                     cpu_floor=floor, cpu_floor_reached=elapsed >= floor))
                    print('SAMPLE', sample, label, name, 'runs=' + str(len(results)),
                          'cpu=%.6f' % (elapsed / len(results)), flush=True)
        for label in ['cold', 'warm']:
            left = [x for x in rows if x.get('state') == label and x['tool'] == 'git']
            right = [x for x in rows if x.get('state') == label and x['tool'] == 'den']
            valid = all(x['cpu_floor_reached'] and x['statuses'] == [0] for x in left + right)
            expected = {tuple(o) for x in left for o in x['outcomes']}
            actual = {tuple(o) for x in right for o in x['outcomes']}
            same = expected == actual and len(expected) == 1
            # Sample order pairs each den batch with the Git batch beside it.
            den = [x['mean_cpu'] for x in sorted(right, key=lambda x: x['sample'])]
            git = [x['mean_cpu'] for x in sorted(left, key=lambda x: x['sample'])]
            ok, words, judged = shared['judge'](bounds, 'status', label, a.tier, den, git, valid, same)
            print(('PASS' if ok else 'FAIL'), 'status-ratio-%s-%s' % (label, a.tier), words,
                  'process_same=' + str(same) + ('' if valid else ' valid=False'), flush=True)
            rows.append(dict(verdict=label, tier=a.tier, equal=ok, margin=guard, **judged))
finally:
    index.write_bytes(inputs['warm'])
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(dict(refresh=refresh, samples=rows,
        fixture_sha256=hashlib.sha256((fixture / 'fixture.json').read_bytes()).hexdigest(),
        den_sha256=hashlib.sha256(a.den.read_bytes()).hexdigest(), environment=env), indent=2) + '\n')
raise SystemExit(0 if a.profile_only or all(x['equal'] for x in rows if 'verdict' in x) else 1)
