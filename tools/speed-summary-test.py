"""The status-speed leaf's summary: a row counts only when its line and its script's report agree.

tools/check-status-speed runs status-measure.py and speed-measure.py for each tier with `|| true`, so
one take names every red row; their exit statuses cannot tell a red row from a crash (an uncaught
exception also exits 1). A measure script that crashed after printing its verdicts once left no report
while its sixteen PASS lines still counted. tools/speed-summary.py reads the log and the four reports
and counts a row only when both agree; a missing report fails by name. This test feeds it made logs
and reports: it needs no den and no Git and runs on every host before any row is timed.
"""
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
shared = runpy.run_path(str(ROOT / 'tools/speed-measure.py'))
NAMES = ['%s-ratio-%s-%s' % (row, state, tier)
         for tier in shared['TIERS'] for row in shared['ROWS'] for state in shared['STATES']]
failures = 0


def say(name, check):
    global failures
    try:
        ok, detail = check()
    except Exception as e:
        ok, detail = False, '%s: %s' % (type(e).__name__, e)
    failures += not ok
    print(('PASS ' if ok else 'FAIL ') + name + (': ' + detail if detail else ''), flush=True)


def ratio(name):
    return 1.0 + NAMES.index(name) / 7.0


def write_case(d, fail=(), drop=(), stale=(), extra=()):
    """A log of the sixteen verdict lines and the four reports, in d."""
    lines = []
    for n in NAMES:
        r = ratio(n)
        lines.append('%s %s ratio=%.6f guardband=1.10 ceiling=9 den_cpu=0.1 git_cpu=0.1 process_same=True'
                     % ('FAIL' if n in fail else 'PASS', n, r))
    lines.extend(extra)
    (d / 'status-speed.log').write_text('\n'.join(lines) + '\n')
    for tier in shared['TIERS']:
        status = [dict(sample=0, state='cold', tool='git', mean_cpu=0.1)]
        speed = []
        for n in NAMES:
            row, rest = n.split('-ratio-')
            state, t = rest.split('-')
            if t != tier:
                continue
            r = ratio(n) * (1.25 if n in stale else 1.0)
            if row == 'status':
                status.append(dict(verdict=state, tier=tier, equal=n not in fail, ratio=r))
            else:
                speed.append(dict(row=row, state=state, ok=n not in fail, ratio=r))
        for kind, body in (('status-ratio', dict(samples=status)), ('speed-rows', dict(tier=tier, verdicts=speed))):
            if '%s-%s' % (kind, tier) not in drop:
                (d / ('%s-%s.json' % (kind, tier))).write_text(json.dumps(body))


def summary(**case):
    with tempfile.TemporaryDirectory(prefix='speed-summary-') as tmp:
        d = Path(tmp)
        write_case(d, **case)
        q = subprocess.run([sys.executable, '-I', str(ROOT / 'tools/speed-summary.py'), str(d / 'status-speed.log'), str(d)],
                           capture_output=True, text=True, timeout=60)
    last = [x for x in q.stdout.splitlines() if x.startswith('status-speed: MEASURED ')]
    return q.returncode, q.stdout, last[-1] if last else ''


GREEN = 'status-speed: MEASURED rows=16 pass=16 fail=0 '


def whole():
    rc, _out, last = summary()
    return rc == 0 and last.startswith(GREEN), 'exit %d: %s' % (rc, last or 'no summary line')


CRASH = ['Traceback (most recent call last):',
         '  File "/work/den/tools/speed-measure.py", line 397, in <module>',
         '    raise SystemExit(main())',
         "AttributeError: 'list' object has no attribute 'read_bytes'"]


def crash():
    rc, out, last = summary(drop=('speed-rows-native', 'speed-rows-release'), extra=CRASH)
    named = all(('FAIL status-speed-report-speed-rows-%s' % t) in out for t in shared['TIERS'])
    return rc == 1 and named and last and not last.startswith(GREEN), \
        'exit %d, report rows named %s: %s' % (rc, named, last or 'no summary line')


def stale():
    n = 'diff-quiet-ratio-warm-native'
    rc, out, last = summary(stale=(n,))
    return rc == 1 and ('FAIL %s' % n) in out and 'pass=15 fail=1 ' in last, 'exit %d: %s' % (rc, last or 'no summary line')


def red():
    rc, _out, last = summary(fail=('pull-ratio-warm-release',))
    return rc == 1 and 'pass=15 fail=1 ' in last, 'exit %d: %s' % (rc, last or 'no summary line')


def witness():
    rc, _out, last = summary(extra=['FAIL diff-quiet-dirty-witness-native git=1 den=0'])
    return rc == 1 and 'pass=16 fail=1 ' in last, 'exit %d: %s' % (rc, last or 'no summary line')


def leaf():
    text = (ROOT / 'tools/check-status-speed').read_text()
    ok = ('tools/speed-summary.py' in text and 'grep -c' not in text
          and all(('target/runs/%s-*.json' % k) in text for k in ('status-ratio', 'speed-rows')))
    return ok, 'the leaf removes old reports, then judges through speed-summary.py, never by counting lines'


say('speed-summary-whole', whole)
say('speed-summary-swallowed-crash', crash)
say('speed-summary-stale-report', stale)
say('speed-summary-red-row', red)
say('speed-summary-witness', witness)
say('speed-summary-leaf', leaf)
print('speed-summary-test: %d failures' % failures, flush=True)
raise SystemExit(int(failures > 0))
