"""The speed rows' band: the ratchet rule, and the sub-millisecond rows' sampling and headroom.

Fed recorded takes (tools/speed-band-takes.json), it needs no den and no Git, and tools/check-status-speed
runs it on every host before any row is timed. The rule (README "Speed rows"): a row's ceiling is the
lowest half step at or above its headroom times the guardband times the record host's ratio, never under
the table's target. A row whose Git side takes about a millisecond of CPU or less moves between takes by
more than the fifth the other rows keep, so it sums each sample to a longer CPU floor, takes more samples,
and keeps a wider headroom, its band: the spread between takes measured with that sampling, rounded up to
a twentieth, never under a fifth. The other rows keep their sampling and a fifth.
"""
import json
import math
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parent.parent
failures = 0


def say(name, check):
    global failures
    try:
        ok, detail = check()
    except Exception as e:  # a missing function or key fails its row by name, never the whole file
        ok, detail = False, '%s: %s' % (type(e).__name__, e)
    failures += not ok
    print(('PASS ' if ok else 'FAIL ') + name + (': ' + detail if detail else ''), flush=True)


shared = runpy.run_path(str(ROOT / 'tools/speed-measure.py'))
bounds = shared['load_bounds']()
data = json.loads((ROOT / 'tools/speed-band-takes.json').read_text())
GUARD = bounds['guardband']
TARGET = bounds['target']
FIFTH = 1.20


def split(name):
    """'diff-cached-quiet-ratio-warm-native' -> ('diff-cached-quiet', 'warm', 'native')."""
    row, rest = name.split('-ratio-')
    state, tier = rest.split('-')
    return row, state, tier


def rule():
    ceiling_for = shared['ceiling_for']
    bad = []
    for r in data['ratchets']:
        got = ceiling_for(r['ratio'], FIFTH, GUARD, TARGET)
        if got != r['ceiling']:
            bad.append('%s %.2f gives %s, not %s' % (r['row'], r['ratio'], got, r['ceiling']))
    o = data['overran']
    first = ceiling_for(o['set_from'], FIFTH, GUARD, TARGET)
    if first != o['ceiling'] or shared['verdict'](o['later'], first, GUARD):
        bad.append('%s: a fifth from %.2f gave %s, which %.2f should fail' % (o['row'], o['set_from'], first, o['later']))
    if bounds['headroom'] != FIFTH:
        bad.append('the table headroom is %s, not a fifth' % bounds['headroom'])
    return not bad, '; '.join(bad) or '%d recorded ratchets reproduce with a fifth; %.2f then %.2f overran %s' % (
        len(data['ratchets']), o['set_from'], o['later'], first)


def named():
    gits = {}
    for take in data['takes']:
        for name, (_ratio, _den, git) in take['rows'].items():
            row, state, _tier = split(name)
            gits.setdefault('%s/%s' % (row, state), []).append(git)
    want = sorted(k for k, v in gits.items() if max(v) < 0.0012)
    mixed = sorted(k for k, v in gits.items() if min(v) < 0.0012 <= max(v))
    have = sorted(bounds['fine']['rows'])
    return have == want and not mixed, 'sub-millisecond: %s%s' % (
        ', '.join(have), '' if have == want else '; recorded under 1.2 ms of Git CPU: ' + ', '.join(want))


def sampling():
    plan = shared['sampling']
    is_fine = shared['is_fine']
    fine = bounds['fine']
    bad = []
    for row in shared['ROWS']:
        for state in shared['STATES']:
            n, floor = plan(bounds, row, state, 5, 0.2)
            if is_fine(bounds, row, state):
                if n < 9 or floor < 1.0:
                    bad.append('%s/%s takes %d samples of %.1f s' % (row, state, n, floor))
            elif (n, floor) != (5, 0.2):
                bad.append('%s/%s moved to %d samples of %.1f s' % (row, state, n, floor))
    fastest = min(git for take in data['takes'] for name, (_r, _d, git) in take['rows'].items()
                  if is_fine(bounds, *split(name)[:2]))
    if shared['RUN_CAP'] * fastest < fine['cpu_floor']:
        bad.append('%d runs of %.6f s never reach %.1f s' % (shared['RUN_CAP'], fastest, fine['cpu_floor']))
    status = (ROOT / 'tools/status-measure.py').read_text()
    if "shared['RUN_CAP']" not in status or "shared['sampling']" not in status:
        bad.append('status-measure.py does not take the shared sampling and run cap')
    return not bad, '; '.join(bad) or 'sub-millisecond rows %d samples of %.1f s (cap %d runs); others 5 of 0.2 s' % (
        fine['samples'], fine['cpu_floor'], shared['RUN_CAP'])


def unchanged():
    headroom = shared['headroom']
    is_fine = shared['is_fine']
    ceiling_for = shared['ceiling_for']
    bad = []
    for row in shared['ROWS']:
        for state in shared['STATES']:
            if not is_fine(bounds, row, state) and headroom(bounds, row, state) != FIFTH:
                bad.append('%s/%s headroom %s' % (row, state, headroom(bounds, row, state)))
    seen = 0
    for take in data['takes']:
        for name, (ratio, _den, _git) in take['rows'].items():
            row, state, tier = split(name)
            if is_fine(bounds, row, state):
                continue
            seen += 1
            if ceiling_for(ratio, headroom(bounds, row, state), GUARD, TARGET) != ceiling_for(ratio, FIFTH, GUARD, TARGET):
                bad.append('%s %.3f sets another ceiling' % (name, ratio))
    return not bad and seen > 0, '; '.join(bad) or '%d recorded takes of rows over a millisecond set what a fifth sets' % seen


def matching(take):
    fine = bounds['fine']
    return (take['samples'] == fine['samples'] and take['cpu_floor'] == fine['cpu_floor']
            and take['statistic'] == bounds['statistic'])


def holds():
    is_fine = shared['is_fine']
    ceiling_for = shared['ceiling_for']
    band = bounds['fine']['headroom']
    chosen = [t for t in data['takes'] if matching(t)]
    if len(chosen) < 3:
        return False, '%d recorded takes with the band\'s sampling (%d samples of %.1f s, %s); three or more set it' % (
            len(chosen), bounds['fine']['samples'], bounds['fine']['cpu_floor'], bounds['statistic'])
    ratios = {}
    for take in chosen:
        for name, (ratio, _den, _git) in take['rows'].items():
            if is_fine(bounds, *split(name)[:2]):
                ratios.setdefault(name, []).append(ratio)
    spread = max(max(v) / min(v) for v in ratios.values())
    want = max(FIFTH, math.ceil(spread * 20 - 1e-9) / 20)
    bad = []
    if abs(band - want) > 1e-9:
        bad.append('band %s where the spread %.3f sets %s' % (band, spread, want))
    for name, v in sorted(ratios.items()):
        c = ceiling_for(min(v), band, GUARD, TARGET)
        if not shared['verdict'](max(v), c, GUARD):
            bad.append('%s: %.3f fails %s set from %.3f' % (name, max(v), c, min(v)))
    return not bad, '; '.join(bad) or 'band %s from a spread of %.3f over %d takes; each row\'s slowest take passes the ceiling its fastest sets' % (
        band, spread, len(chosen))


def outliers():
    is_fine = shared['is_fine']
    ceiling_for = shared['ceiling_for']
    band = bounds['fine']['headroom']
    bad = []
    for o in data['outliers']:
        row, state, tier = split(o['row'])
        if shared['verdict'](o['ratio'], bounds['rows'][row][state][tier], GUARD):
            bad.append('%s %.2f passes' % (o['row'], o['ratio']))
    lowest = {}
    for take in data['takes']:
        for name, (ratio, _den, _git) in take['rows'].items():
            if is_fine(bounds, *split(name)[:2]):
                lowest[name] = min(ratio, lowest.get(name, ratio))
    for name, r in sorted(lowest.items()):
        if shared['verdict'](1.5 * r, ceiling_for(r, band, GUARD, TARGET), GUARD):
            bad.append('%s: half again over %.3f passes the band' % (name, r))
    return not bad and lowest, '; '.join(bad) or 'the recorded plant fails, and half again over each sub-millisecond row\'s fastest take fails its band'


def paired():
    pm = shared['paired_median']
    least = shared['least']
    cases = [(pm([3, 5, 4], [1, 1, 2]), 3.0), (pm([1, 2, 3, 4], [1, 1, 1, 1]), 2.5),
             (least([3, 5, 4], [1, 1, 2]), 3.0), (pm([2.0, 2.6, 2.2], [1.0, 1.3, 1.1]), 2.0)]
    ok = all(abs(got - want) < 1e-12 for got, want in cases) and bounds['statistic'] in shared['STATISTICS']
    return ok, 'median of per-sample den/Git ratios and least over least; the table uses %s' % bounds['statistic']


say('speed-band-rule', rule)
say('speed-band-rows-named', named)
say('speed-band-sampling-sub-ms', sampling)
say('speed-band-over-1ms-unchanged', unchanged)
say('speed-band-holds-spread', holds)
say('speed-band-outlier-fails', outliers)
say('speed-band-paired-median', paired)
print('speed-band-test: %d failures' % failures, flush=True)
raise SystemExit(int(failures > 0))
