"""vc23 (den#84): the local zone of a date, as the pinned Git takes it from TZ.

Every row runs one operation with both tools under tools/env, with TZ (and
TZDIR) set as the row says, and compares den's result with Git's.

  stamp   a date not given (now): `commit` in a fresh repository; the zones
          of the author, committer and reflog lines must be Git's, and each
          tool's seconds must fall inside its own run. Rules whose change is
          two hours either side of now pin both sides of a transition.
  dated   GIT_AUTHOR_DATE / GIT_COMMITTER_DATE and --date, with and without
          a zone: status, stdout, stderr, the commit and its reflog line.
  wall    zone-less readings every 30 minutes for three hours either side of
          each 2024 change, as calendar text and as `@N`: the author and
          committer lines.
  amend   an amended author whose stored zone is not four digits, re-read in
          the local zone.
  verbs   tag -a, merge, stash, revert, cherry-pick, rebase, notes, branch,
          switch and reset under a zone that is not UTC: the zone of every
          identity and reflog line each writes.
  shell   TZ exported from a shell startup file, then a plain add, commit and
          log in a new repository, end to end.

  --measure  run every row and write the table (target/zone-TIER/), failing
             nothing.
  (default)  any row whose result differs is FAIL <row>, except the named
             refusals in REFUSED, where den must refuse by that name.
  --family F (repeatable), --field (Git is not the pinned one).
"""
import argparse
import calendar
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

R = pathlib.Path(__file__).resolve().parent.parent
ORACLE_SHA = 'c4848492938c4ebfffbefe1fbbaa68b9af90c86d1f6a20e76816c5ff37fcfa60'
FAMILIES = ('stamp', 'dated', 'wall', 'amend', 'verbs', 'shell')

p = argparse.ArgumentParser()
p.add_argument('--tier', default='native')
p.add_argument('--measure', action='store_true')
p.add_argument('--field', action='store_true')
p.add_argument('--family', action='append', choices=FAMILIES)
A = p.parse_args()
SELECTED = A.family or list(FAMILIES)
GIT = pathlib.Path(os.environ.get('DEN_GIT') or next((R / 'target/oracle').glob('*/root/opt/git/bin/git')))
if not A.field:
    assert hashlib.sha256(GIT.read_bytes()).hexdigest() == ORACLE_SHA, 'pinned oracle digest'
DEN = R / 'target' / A.tier / 'den'
assert DEN.is_file(), DEN
ROOT = R / 'target' / ('zone-' + A.tier + ('-field' if A.field else ''))
if ROOT.exists():
    shutil.rmtree(ROOT)
ROOT.mkdir(parents=True)
TOOLS = {'git': str(GIT), 'den': str(DEN)}
ZONES = R / 'tests' / 'zones'
EMPTY = ROOT / 'empty-zones'
EMPTY.mkdir()
POSIXRULES = ROOT / 'posixrules-zones'
shutil.copytree(ZONES, POSIXRULES)
shutil.copyfile(ZONES / 'America' / 'New_York', POSIXRULES / 'posixrules')
NO_DATES = {'GIT_AUTHOR_DATE': None, 'GIT_COMMITTER_DATE': None}
rows = []
failures = []

# den refuses these by name, as ruled in notes/vc23-local-time-zones.md: the
# C library reads them in ways den does not reproduce. row -> stderr text.
REFUSED = {
    'stamp/posixrules-rule-less': 'commit local timezone XXX3YYY: daylight saving with no change rules',
    'stamp/malformed-month-13': 'commit local timezone EST5EDT,M13.1.0,M11.1.0: a malformed daylight-saving rule',
    'stamp/malformed-junk-after-rule': 'commit local timezone EST5EDT,M3.2.0,M11.1.0x: a malformed daylight-saving rule',
    'stamp/held-daylight-offset': 'commit local timezone EST5EDT4:60: an out-of-range daylight-saving offset',
}


def utc(*fields):
    return calendar.timegm(fields + (0,) * (6 - len(fields)))


def run(argv, cwd, env=None, data=None):
    e = dict(os.environ)
    for key, value in (env or {}).items():
        if value is None:
            e.pop(key, None)
        else:
            e[key] = value
    return subprocess.run([str(x) for x in argv], cwd=cwd, input=data, capture_output=True, env=e, timeout=300)


def g(cwd, *args, env=None, data=None):
    q = run([GIT, *args], cwd, env=env, data=data)
    assert q.returncode == 0, (args, q.stderr)
    return q.stdout.decode()


def text(data):
    return data.decode('utf-8', 'backslashreplace')


def result(q):
    return {'status': q.returncode, 'stdout': text(q.stdout), 'stderr': text(q.stderr)}


def record(name, git_res, den_res, extra=None, same=None):
    if same is None:
        same = git_res == den_res
    if extra is not None:
        same = same and extra.get('git') == extra.get('den')
    row = dict(name=name, git=git_res, den=den_res, extra=extra, same=same)
    want = REFUSED.get(name)
    row['refusal'] = want
    rows.append(row)
    if want is not None:
        ok = den_res['status'] != 0 and want in den_res['stderr']
        row['passed'] = ok
        if ok:
            print('PASS', name, 'refused by name (git: status %d)' % git_res['status'], flush=True)
            return
    else:
        row['passed'] = same
        if same:
            print('PASS', name, flush=True)
            return
    failures.append(name)
    print(('DIFF ' if A.measure else 'FAIL ') + name, 'git=' + json.dumps(git_res), 'den=' + json.dumps(den_res),
          ('extra=' + json.dumps(extra)) if extra is not None else '', flush=True)


def fresh(path):
    """A repository with one commit at a fixed date, the same for both tools."""
    path.mkdir(parents=True)
    g(path, 'init', '-q', '-b', 'main')
    (path / 'f').write_bytes(b'one\n')
    g(path, 'add', 'f')
    g(path, 'commit', '-q', '-m', 'base')
    return path


IDENT = re.compile(r'^(author|committer|tagger) .* (\d+) ([+-]\d{4})$')


def object_dates(cwd, kind, oid):
    """(field, seconds, zone) of each identity line of an object."""
    out = []
    for line in g(cwd, 'cat-file', kind, oid).splitlines():
        if line == '':
            break
        m = IDENT.match(line)
        if m:
            out.append((m.group(1), int(m.group(2)), m.group(3)))
    return out


def reflog_dates(cwd, skip):
    """(ref, seconds, zone) of every reflog line after the first `skip` of each log."""
    out = []
    logs = cwd / '.git' / 'logs'
    for log in sorted(logs.rglob('*')):
        if not log.is_file():
            continue
        lines = log.read_text(errors='replace').splitlines()
        for line in lines[skip.get(str(log), 0):]:
            head = line.split('\t', 1)[0]
            parts = head.rsplit(' ', 2)
            out.append((str(log.relative_to(logs)), int(parts[1]), parts[2]))
    return out


def reflog_messages(cwd, skip):
    """Every new reflog line's message, object ids masked."""
    out = []
    logs = cwd / '.git' / 'logs'
    for log in sorted(logs.rglob('*')):
        if log.is_file():
            for line in log.read_text(errors='replace').splitlines()[skip.get(str(log), 0):]:
                out.append((str(log.relative_to(logs)), HEX.sub('X', line.split('\t', 1)[-1])))
    return out


def reflog_counts(cwd):
    logs = cwd / '.git' / 'logs'
    return {str(log): len(log.read_text(errors='replace').splitlines()) for log in logs.rglob('*') if log.is_file()}


def rule_at(std_hours, kind, instant):
    """A J-rule (zone AAA, daylight BBB) whose `kind` change is at `instant`."""
    east = -std_hours * 3600
    local = instant + east + (3600 if kind == 'end' else 0)
    tm = time.gmtime(local)
    day = tm.tm_yday
    if calendar.isleap(tm.tm_year) and day > 59:
        day -= 1
    seconds = tm.tm_hour * 3600 + tm.tm_min * 60 + tm.tm_sec
    spec = 'J%d/%d:%02d:%02d' % (day, seconds // 3600, seconds // 60 % 60, seconds % 60)
    body = 'AAA%dBBB' % std_hours
    if kind == 'start':
        return body + ',' + spec + ',J365/0'
    return body + ',J1/0,' + spec


# ---- stamp: a date not given -------------------------------------------------

def stamp_cases():
    now = int(time.time())
    cases = [
        ('unset', None, None),
        ('empty', '', None),
        ('utc', 'UTC', None),
        ('posix-rule', 'EST5EDT,M3.2.0,M11.1.0', None),
        ('posix-rule-no-database', 'EST5EDT,M3.2.0,M11.1.0', EMPTY),
        ('posix-rule-east', 'CET-1CEST,M3.5.0,M10.5.0/3', None),
        ('posix-rule-south', 'AEST-10AEDT,M10.1.0,M4.1.0/3', None),
        ('posix-rule-half-hour', '<+1030>-10:30<+11>-11,M10.1.0,M4.1.0', None),
        ('fixed-east', 'JST-9', None),
        ('fixed-quoted', '<+0530>-5:30', None),
        ('fixed-west-quoted', '<-03>3', None),
        ('fixed-signed', 'UTC-3', None),
        ('fixed-seconds', 'LMT0:44:30', None),
        ('fixed-seconds-east', 'LMT-0:44:30', None),
        ('fixed-under-a-minute', 'ABC0:00:30', None),
        ('fixed-largest', 'ABC-24:59:59', None),
        ('name-database', 'America/New_York', ZONES),
        ('name-database-colon', ':America/New_York', ZONES),
        ('name-database-path', str(ZONES / 'Europe' / 'Berlin'), ZONES),
        ('name-database-half-hour', 'Australia/Lord_Howe', ZONES),
        ('name-database-fixed', 'Asia/Kolkata', ZONES),
        ('name-database-rule-less', 'EST5EDT', ZONES),
        ('name-no-database', 'America/New_York', EMPTY),
        ('name-no-database-colon', ':America/New_York', EMPTY),
        ('rule-less-no-database', 'EST5EDT', EMPTY),
        ('rule-less-made-up', 'XXX3YYY', EMPTY),
        ('rule-less-east', 'CET-1CEST', EMPTY),
        ('rule-less-offset', 'EST5EDT4:30', EMPTY),
        ('posixrules-rule-less', 'XXX3YYY', POSIXRULES),
        ('malformed-word', 'garbage', None),
        ('malformed-short-name', 'E5', None),
        ('malformed-no-offset', 'EST', EMPTY),
        ('malformed-daylight-name', 'EST5x', None),
        ('malformed-space', 'EST5 ', None),
        ('malformed-colon-only', ':', None),
        ('malformed-colon-missing', ':nonexistent', None),
        ('malformed-path-missing', '/nonexistent/zone', None),
        ('held-hours', 'EST25', None),
        ('held-minutes', 'EST5:60', None),
        ('held-seconds', 'EST5:59:60', None),
        ('held-hours-minutes', 'EST25:30', None),
        ('held-daylight-offset', 'EST5EDT4:60', EMPTY),
        ('malformed-rule-word', 'EST5EDT,garbage', None),
        ('malformed-rule-empty', 'EST5EDT,,M11.1.0', None),
        ('malformed-rule-separator', 'EST5EDT;M3.2.0,M11.1.0', None),
        ('malformed-rule-day', 'EST5EDT,366,300', None),
        ('malformed-after-offset', 'EST5EDT4x', None),
        ('malformed-no-end', 'EST5EDT,M3.2.0', None),
        ('malformed-no-end-comma', 'EST5EDT,M3.2.0,', None),
        ('malformed-end-word', 'EST5EDT,M3.2.0,garbage', None),
        ('malformed-trailing-comma', 'EST5EDT,M3.2.0,M11.1.0,', None),
        ('malformed-rules-comma', 'EST5EDT,', EMPTY),
        ('malformed-month-13', 'EST5EDT,M13.1.0,M11.1.0', None),
        ('malformed-junk-after-rule', 'EST5EDT,M3.2.0,M11.1.0x', None),
    ]
    # Both sides of a change: a rule whose change is two hours from now.
    for std, place in [(5, 'west'), (-5, 'east')]:
        for kind in ('start', 'end'):
            for delta, side in [(7200, 'ahead'), (-7200, 'behind')]:
                cases.append(('change-%s-%s-%s' % (place, kind, side), rule_at(std, kind, now + delta), None))
    return cases


def stamp_family():
    for label, zone, tzdir in stamp_cases():
        name = 'stamp/' + label
        env = dict(NO_DATES)
        env['TZ'] = zone
        env['TZDIR'] = str(tzdir) if tzdir is not None else None
        res, seen = {}, {}
        for tool in ('git', 'den'):
            work = fresh(ROOT / 'stamp' / tool / label)
            counts = reflog_counts(work)
            before = int(time.time())
            q = run([TOOLS[tool], 'commit', '-q', '--allow-empty', '-m', 'now'], work, env=env)
            after = int(time.time())
            res[tool] = result(q)
            if q.returncode != 0:
                seen[tool] = None
                continue
            head = g(work, 'rev-parse', 'HEAD').strip()
            dates = object_dates(work, 'commit', head) + reflog_dates(work, counts)
            inside = all(before <= secs <= after + 1 for _, secs, _ in dates)
            seen[tool] = {'zones': [(field, zone_text) for field, _, zone_text in dates], 'inside': inside,
                          'seconds': [secs for _, secs, _ in dates]}
        extra = {t: (None if seen[t] is None else (seen[t]['zones'], seen[t]['inside'])) for t in seen}
        row_extra = {'git': extra['git'], 'den': extra['den'], 'zone': zone, 'tzdir': str(tzdir) if tzdir else None,
                     'seconds': {t: (seen[t] or {}).get('seconds') for t in seen}}
        # Each tool's seconds must lie inside its own run; the zones must agree.
        inside = all(seen[t] is None or seen[t]['inside'] for t in seen)
        record(name, res['git'], res['den'], extra=row_extra, same=res['git'] == res['den'] and inside)


# ---- dated: dates given, with and without a zone ----------------------------

DATED_ZONES = [
    ('posix-rule', 'EST5EDT,M3.2.0,M11.1.0', None),
    ('posix-rule-east', 'CET-1CEST,M3.5.0,M10.5.0/3', None),
    ('fixed-east', 'JST-9', None),
    ('fixed-seconds', 'LMT0:44:30', None),
    ('utc', 'UTC', None),
    ('name-database', 'America/New_York', ZONES),
    ('rule-less-no-database', 'EST5EDT', EMPTY),
]

DATED_FORMS = [
    ('explicit-raw', '@1710053999 -0500'),
    ('explicit-digits', '1710053999 +0100'),
    ('explicit-iso', '2024-03-10 02:30:00 +0000'),
    ('explicit-rfc', 'Sun, 10 Mar 2024 02:30:00 +0100'),
    ('explicit-name', '2024-03-10 02:30:00 EDT'),
    ('explicit-z', '2024-03-10T02:30:00Z'),
    ('epoch-before-change', '@1710053999'),
    ('epoch-at-change', '@1710054000'),
    ('epoch-before-fall', '@1730613599'),
    ('epoch-at-fall', '@1730613600'),
    ('epoch-digits', '1710053999'),
    ('epoch-small', '@99999999'),
    ('epoch-smallest', '@100000000'),
    ('epoch-leading-zero', '@0100000000'),
    ('epoch-zero', '@0'),
    ('wall-iso', '2024-03-10 02:30:00'),
    ('wall-t', '2024-03-10T02:30:00'),
    ('wall-rfc', 'Sun, 10 Mar 2024 02:30:00'),
    ('wall-slash', '03/10/2024 02:30:00'),
    ('wall-dots', '2024.03.10 02:30:00'),
    ('wall-epoch-day', '1970-01-01 00:00:00'),
    ('wall-summer', '2024-07-01 12:00:00'),
    ('wall-winter', '2024-01-15 12:00:00'),
]


def dated_family():
    for zlabel, zone, tzdir in DATED_ZONES:
        for flabel, form in DATED_FORMS:
            for how in ('environment', 'option'):
                if how == 'option' and not flabel.startswith(('wall-iso', 'epoch-before-change', 'explicit-raw')):
                    continue
                name = 'dated/%s/%s/%s' % (zlabel, flabel, how)
                env = {'TZ': zone, 'TZDIR': str(tzdir) if tzdir else None}
                argv = ['commit', '--allow-empty', '-m', 'dated']
                if how == 'environment':
                    env.update(GIT_AUTHOR_DATE=form, GIT_COMMITTER_DATE=form)
                else:
                    argv += ['--date', form]
                res, made = {}, {}
                for tool in ('git', 'den'):
                    work = fresh(ROOT / 'dated' / tool / zlabel / flabel / how)
                    q = run([TOOLS[tool], *argv], work, env=env)
                    res[tool] = result(q)
                    head = g(work, 'rev-parse', 'HEAD').strip()
                    made[tool] = None if q.returncode else [g(work, 'cat-file', 'commit', head),
                                                            (work / '.git/logs/HEAD').read_text().splitlines()[-1]]
                record(name, res['git'], res['den'], extra=made)


# ---- wall: readings about each 2024 change ------------------------------------

WALL_ZONES = [
    ('posix-rule', 'EST5EDT,M3.2.0,M11.1.0', None, [(2024, 3, 10, 2), (2024, 11, 3, 1)]),
    ('posix-rule-east', 'CET-1CEST,M3.5.0,M10.5.0/3', None, [(2024, 3, 31, 2), (2024, 10, 27, 2)]),
    ('posix-rule-south', 'AEST-10AEDT,M10.1.0,M4.1.0/3', None, [(2024, 4, 7, 2), (2024, 10, 6, 2)]),
    ('posix-rule-half-hour', '<+1030>-10:30<+11>-11,M10.1.0,M4.1.0', None, [(2024, 4, 7, 1), (2024, 10, 6, 2)]),
    ('name-database', 'America/New_York', ZONES, [(2024, 3, 10, 2), (2024, 11, 3, 1)]),
    ('name-database-east', 'Europe/Berlin', ZONES, [(2024, 3, 31, 2), (2024, 10, 27, 2)]),
    ('name-database-half-hour', 'Australia/Lord_Howe', ZONES, [(2024, 4, 7, 1), (2024, 10, 6, 2)]),
    ('rule-less-no-database', 'EST5EDT', EMPTY, [(2024, 3, 10, 2), (2024, 11, 3, 1)]),
    ('fixed-seconds', 'LMT0:44:30', None, [(2024, 3, 10, 2)]),
]


def wall_family():
    for zlabel, zone, tzdir, centers in WALL_ZONES:
        base = {'TZ': zone, 'TZDIR': str(tzdir) if tzdir else None}
        works = {tool: fresh(ROOT / 'wall' / tool / zlabel) for tool in TOOLS}
        for year, month, day, hour in centers:
            center = utc(year, month, day, hour)
            for step in range(-6, 7):
                wall = center + step * 1800
                stamp = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(wall))
                for form, value in [('calendar', stamp), ('epoch', '@%d' % wall)]:
                    name = 'wall/%s/%s/%s' % (zlabel, form, stamp.replace(' ', 'T'))
                    env = dict(base, GIT_AUTHOR_DATE=value, GIT_COMMITTER_DATE=value)
                    res, made = {}, {}
                    for tool, work in works.items():
                        q = run([TOOLS[tool], 'commit', '-q', '--allow-empty', '-m', 'wall'], work, env=env)
                        res[tool] = result(q)
                        made[tool] = None if q.returncode else object_dates(work, 'commit', g(work, 'rev-parse', 'HEAD').strip())
                    record(name, res['git'], res['den'], extra=made)


# ---- amend: a stored zone that is not four digits ----------------------------

def amend_family():
    for zlabel, zone in [('posix-rule', 'EST5EDT,M3.2.0,M11.1.0'), ('posix-rule-east', 'CET-1CEST,M3.5.0,M10.5.0/3'),
                         ('utc', 'UTC')]:
        for slabel, stamp in [('long-zone', b'1710053999 +00000'), ('short-zone', b'1710053999 +000'),
                              ('long-zone-fall', b'1730613599 +00000'), ('long-zone-east', b'1711846799 +00000'),
                              ('long-zone-small', b'50000000 +00000')]:
            name = 'amend/%s/%s' % (zlabel, slabel)
            res, made = {}, {}
            for tool in ('git', 'den'):
                work = fresh(ROOT / 'amend' / tool / zlabel / slabel)
                tree = g(work, 'rev-parse', 'HEAD^{tree}').strip()
                body = (b'tree ' + tree.encode() + b'\nauthor A U Thor <a@example.invalid> ' + stamp +
                        b'\ncommitter C O Mitter <c@example.invalid> 1700000000 +0000\n\nodd zone\n')
                oid = g(work, 'hash-object', '-w', '-t', 'commit', '--literally', '--stdin', data=body).strip()
                g(work, 'update-ref', 'HEAD', oid)
                q = run([TOOLS[tool], 'commit', '-q', '--amend', '--allow-empty', '-m', 'amended'], work,
                        env={'TZ': zone, 'GIT_AUTHOR_DATE': None})
                res[tool] = result(q)
                made[tool] = None if q.returncode else g(work, 'cat-file', 'commit', 'HEAD')
            record(name, res['git'], res['den'], extra=made)


# ---- verbs: every writer of an identity or reflog line ------------------------

HEX = re.compile(r'\b[0-9a-f]{7,40}\b')


def masked(res):
    return {k: (HEX.sub('X', v) if isinstance(v, str) else v) for k, v in res.items()}


def verb_setup(work):
    """main with two commits; branch side with one; a change for stash."""
    (work / 'g').write_bytes(b'side\n')
    g(work, 'checkout', '-q', '-b', 'side')
    g(work, 'add', 'g')
    g(work, 'commit', '-q', '-m', 'side')
    g(work, 'checkout', '-q', 'main')
    (work / 'f').write_bytes(b'one\ntwo\n')
    g(work, 'commit', '-q', '-am', 'two')


VERBS = [
    ('tag-annotated', [['tag', '-a', 'v1', '-m', 'tag']], 'refs/tags/v1', 'tag'),
    ('tag-reflog', [['tag', 'v2']], None, None),
    ('merge', [['merge', '--no-ff', '-q', '-m', 'merge', 'side']], 'HEAD', 'commit'),
    ('stash', [['stash', 'push', '-q', '-m', 'saved']], 'refs/stash', 'commit'),
    ('revert', [['revert', '--no-edit', 'HEAD']], 'HEAD', 'commit'),
    ('cherry-pick', [['cherry-pick', 'side']], 'HEAD', 'commit'),
    ('rebase', [['switch', '-q', 'side'], ['rebase', 'main']], 'HEAD', 'commit'),
    ('notes', [['notes', 'add', '-m', 'note']], 'refs/notes/commits', 'commit'),
    ('branch', [['branch', 'new']], None, None),
    ('switch', [['switch', '-q', '-c', 'other']], None, None),
    ('reset', [['reset', '-q', '--hard', 'HEAD~1']], None, None),
    ('amend', [['commit', '-q', '--amend', '-m', 'amended']], 'HEAD', 'commit'),
]


def verbs_family():
    for zlabel, zone in [('posix-rule', 'EST5EDT,M3.2.0,M11.1.0'), ('fixed-east', 'JST-9')]:
        for vlabel, commands, ref, kind in VERBS:
            name = 'verbs/%s/%s' % (zlabel, vlabel)
            env = dict(NO_DATES, TZ=zone)
            if vlabel == 'tag-reflog':
                env.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='core.logAllRefUpdates', GIT_CONFIG_VALUE_0='always')
            res, seen = {}, {}
            for tool in ('git', 'den'):
                work = fresh(ROOT / 'verbs' / tool / zlabel / vlabel)
                verb_setup(work)
                if vlabel == 'stash':
                    (work / 'f').write_bytes(b'changed\n')
                counts = reflog_counts(work)
                before = int(time.time())
                outs = []
                for command in commands:
                    q = run([TOOLS[tool], *command], work, env=env)
                    outs.append(masked(result(q)))
                after = int(time.time())
                res[tool] = outs
                dates = reflog_dates(work, counts)
                if ref is not None and all(o['status'] == 0 for o in outs):
                    dates += object_dates(work, kind, g(work, 'rev-parse', ref).strip())
                    if vlabel == 'stash':
                        dates += object_dates(work, 'commit', g(work, 'rev-parse', 'refs/stash^2').strip())
                fresh_dates = [(f, z) for f, s, z in dates if s >= before - 1]
                inside = all(s <= after + 1 for _, s, _ in dates if s >= before - 1)
                seen[tool] = (fresh_dates + reflog_messages(work, counts), inside)
            git_res = {'status': max(o['status'] for o in res['git']), 'stdout': json.dumps(res['git']), 'stderr': ''}
            den_res = {'status': max(o['status'] for o in res['den']), 'stdout': json.dumps(res['den']), 'stderr': ''}
            inside = seen['git'][1] and seen['den'][1]
            record(name, git_res, den_res, extra={t: seen[t][0] for t in seen},
                   same=git_res == den_res and inside and bool(seen['git'][0]))


# ---- shell: TZ from a startup file, a plain commit end to end ----------------

def shell_family():
    zone = 'EST5EDT,M3.2.0,M11.1.0'
    res, seen, logs = {}, {}, {}
    for tool in ('git', 'den'):
        home = ROOT / 'shell' / tool / 'home'
        home.mkdir(parents=True)
        # The way a login shell's startup file sets it (den#84's machine).
        (home / '.profile').write_text('TZ=%s\nexport TZ\n' % zone)
        repo = ROOT / 'shell' / tool / 'repo'
        g(repo.parent, 'init', '-q', '-b', 'main', str(repo))
        g(repo, 'config', 'user.name', 'Shell User')
        g(repo, 'config', 'user.email', 'shell@example.invalid')
        (repo / 'file').write_text('hello\n')
        script = ('cd "$REPO" && "$TOOL" add file && "$TOOL" commit -q -m first && '
                  '"$TOOL" log -1 --format="%ad|%cd|%an <%ae>" --date=raw')
        env = {k: v for k, v in os.environ.items()
               if k in ('PATH', 'LC_ALL', 'GIT_CONFIG_NOSYSTEM', 'GIT_EXEC_PATH', 'GIT_EDITOR', 'PAGER')}
        env.update(HOME=str(home), REPO=str(repo), TOOL=TOOLS[tool], GIT_CONFIG_GLOBAL='/dev/null')
        before = int(time.time())
        q = subprocess.run(['bash', '-l', '-c', script], env=env, capture_output=True, timeout=120)
        after = int(time.time())
        res[tool] = {'status': q.returncode, 'stdout': re.sub(r'\b\d{10}\b', 'S', text(q.stdout)), 'stderr': text(q.stderr)}
        head = run([GIT, 'rev-parse', '-q', '--verify', 'HEAD'], repo).stdout.decode().strip()
        dates = object_dates(repo, 'commit', head) if head else []
        seen[tool] = ([(f, z) for f, _, z in dates], bool(dates) and all(before <= s <= after + 1 for _, s, _ in dates))
        # Each tool reads the other's commit as its own.
        logs[tool] = {reader: text(run([TOOLS[reader], 'log', '-1', '--format=%H %ad %cd', '--date=raw'], repo).stdout)
                      for reader in ('git', 'den')}
    record('shell/startup-file', res['git'], res['den'], extra={t: seen[t][0] for t in seen},
           same=res['git'] == res['den'] and seen['git'][1] and seen['den'][1])
    record('shell/den-commit-read-by-git', {'status': 0, 'stdout': logs['den']['git'], 'stderr': ''},
           {'status': 0, 'stdout': logs['den']['den'], 'stderr': ''})


def table():
    lines = []
    for row in rows:
        mark = '=' if row['same'] else ('R' if row.get('passed') else '!')
        lines.append('%s %s' % (mark, row['name']))
    return '\n'.join(lines) + '\n'


try:
    for family in SELECTED:
        globals()[family + '_family']()
finally:
    (ROOT / 'rows.json').write_text(json.dumps(rows, indent=1))
    (ROOT / 'table.txt').write_text(table())
print('ZONE rows=%d passed=%d failed=%d' % (len(rows), len(rows) - len(failures), len(failures)))
if failures and not A.measure:
    sys.exit(1)
