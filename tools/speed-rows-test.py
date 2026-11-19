"""The speed rows' own checks, run by tools/check-status-speed on every host.

They need no den and no Git: the ratchet table's shape, the verdict at the
line, the row names, and the switch. DEN_PERF_ROWS=1 is declared only by a
record taken on an exclusive performance block; hosted CI and the container
wrapper must never declare it, because a shared runner's clocks would make
the rows report the runner. --names prints every row, one per line.
"""
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parent.parent
shared = runpy.run_path(str(ROOT / 'tools/speed-measure.py'))
TIERS = ('native', 'release')
names = ['%s-ratio-%s-%s' % (row, state, tier)
         for tier in TIERS for row in shared['ROWS'] for state in shared['STATES']]
if sys.argv[1:] == ['--names']:
    print('\n'.join(names))
    raise SystemExit(0)
assert not sys.argv[1:], sys.argv
failures = 0


def say(ok, text):
    global failures
    failures += not ok
    print(('PASS ' if ok else 'FAIL ') + text, flush=True)


bounds = shared['load_bounds']()
say(bounds['guardband'] == 1.10, 'speed-rows-guardband is 1.10')
ceilings = [c for states in bounds['rows'].values() for c in states.values()]
say(all(type(c) in (int, float) and 1 < c for c in ceilings), 'speed-rows-ceilings are numbers above 1')
say(len(names) == 16 and len(set(names)) == 16, 'speed-rows-names 16 rows: four commands, cold and warm, two tiers')
verdict = shared['verdict']
say(verdict(4.5454, 5, 1.10) and not verdict(4.5455, 5, 1.10) and not verdict(5, 5, 1.10),
    'speed-rows-verdict passes 4.5454 and fails 4.5455 at a ceiling of 5')
declared = []
for pattern in ('.github/**/*', 'ci/*', 'tools/in-container', 'tools/gate', 'tools/gate-record', 'tools/environment.py'):
    for f in sorted(ROOT.glob(pattern)):
        if f.is_file() and b'DEN_PERF_ROWS' in f.read_bytes():
            declared.append(str(f.relative_to(ROOT)))
say(not declared, 'speed-rows-switch no workflow, CI file or container wrapper declares DEN_PERF_ROWS'
    + ('' if not declared else ': ' + ', '.join(declared)))
leaf = (ROOT / 'tools/check-status-speed').read_text()
say('"${DEN_PERF_ROWS:-0}" != 1' in leaf and 'NOT MEASURED' in leaf,
    'speed-rows-default the leaf measures only when DEN_PERF_ROWS is 1 and says NOT MEASURED otherwise')
print('speed-rows-test: %d failures' % failures, flush=True)
raise SystemExit(int(failures > 0))
