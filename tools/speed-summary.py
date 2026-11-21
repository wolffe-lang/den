"""The status-speed leaf's verdict, from its log and the measure scripts' reports.

  python3 -I tools/speed-summary.py LOG RUNS

status-measure.py and speed-measure.py each print one PASS or FAIL line per row and write a JSON report
(RUNS/status-ratio-TIER.json, RUNS/speed-rows-TIER.json). A row counts only when it has exactly one line
in LOG and a verdict in its script's report, and the two agree: the same verdict and the same ratio to
the six places the line prints. A report that is missing or unreadable (a script that crashed after its
lines, or never ran) fails by name, as does a row whose line and report disagree (a report left by an
earlier take). Any other FAIL line in LOG (a dirty-index witness) counts as a failure. Prints the leaf's
summary line; exits 0 only for sixteen rows passed and nothing failed.
"""
import json
from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parent.parent
shared = runpy.run_path(str(ROOT / 'tools/speed-measure.py'))
NAMES = ['%s-ratio-%s-%s' % (row, state, tier)
         for tier in shared['TIERS'] for row in shared['ROWS'] for state in shared['STATES']]
ROW = re.compile(r'^(PASS|FAIL) ([a-z-]+-ratio-(?:cold|warm)-(?:native|release)) ratio=([0-9.]+) ')


def main():
    assert len(sys.argv) == 3, 'usage: speed-summary.py LOG RUNS'
    log, runs = Path(sys.argv[1]), Path(sys.argv[2])
    lines, other_fails = {}, 0
    for line in log.read_text(errors='replace').splitlines():
        m = ROW.match(line)
        if m:
            lines.setdefault(m.group(2), []).append((m.group(1) == 'PASS', float(m.group(3))))
        elif line.startswith('FAIL '):
            other_fails += 1
    reports, missing = {}, 0
    for tier in shared['TIERS']:
        for kind in ('status-ratio', 'speed-rows'):
            path = runs / ('%s-%s.json' % (kind, tier))
            try:
                data = json.loads(path.read_text())
                if kind == 'status-ratio':
                    for v in data['samples']:
                        if 'verdict' in v:
                            reports['status-ratio-%s-%s' % (v['verdict'], tier)] = (v['equal'], v['ratio'])
                else:
                    for v in data['verdicts']:
                        reports['%s-ratio-%s-%s' % (v['row'], v['state'], tier)] = (v['ok'], v['ratio'])
            except (OSError, ValueError, KeyError, TypeError) as e:
                missing += 1
                print('FAIL status-speed-report-%s-%s: %s not written or unreadable (%s)'
                      % (kind, tier, path.name, type(e).__name__), flush=True)
    passed = failed = 0
    for name in NAMES:
        seen = lines.get(name, [])
        if len(seen) != 1:
            failed += 1
            print('FAIL %s: %d verdict lines in the log' % (name, len(seen)), flush=True)
            continue
        ok, ratio = seen[0]
        if name not in reports:
            failed += 1
            print('FAIL %s: no verdict in its report' % name, flush=True)
            continue
        rok, rratio = reports[name]
        if rok != ok or '%.6f' % rratio != '%.6f' % ratio:
            failed += 1
            print('FAIL %s: the line says %s ratio=%.6f, the report %s ratio=%.6f'
                  % (name, 'PASS' if ok else 'FAIL', ratio, 'PASS' if rok else 'FAIL', rratio), flush=True)
            continue
        passed += ok
        failed += not ok
    failed += other_fails + missing
    print('status-speed: MEASURED rows=16 pass=%d fail=%d (ceilings in tools/speed-bounds.json, guardband 1.10, '
          'process bytes identical, every row in its report)' % (passed, failed), flush=True)
    return int(not (passed == 16 and failed == 0))


if __name__ == '__main__':
    raise SystemExit(main())
