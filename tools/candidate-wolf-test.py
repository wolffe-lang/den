"""The candidate compiler leaf must run every build and reject missing inputs."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / 'tools/check-candidate-wolf'
FIXED = ['den', 'index_checked_flags', 'index_checked_format', 'index_checked_malformed',
         'index_checked_stat', 'index_checked_trees']
# Every test program under src/, by its path there without `.lu` (zlib/huffman_test).
TESTS = sorted(p.relative_to(ROOT / 'src').with_suffix('').as_posix() for p in (ROOT / 'src').rglob('*_test.lu')
               if not any(part.startswith('.') for part in p.relative_to(ROOT / 'src').parts))
NESTED = [t for t in TESTS if '/' in t]
failures = 0


def say(ok, name):
    global failures
    print(('PASS ' if ok else 'FAIL ') + name, flush=True)
    failures += not ok


def cells(seen):
    """(program, tier) for every compiler call, from its source argument and flags."""
    out = []
    for call in seen:
        words = call.split()
        source = next((w for w in words if w.startswith('src/') and w.endswith('.lu')), '')
        out.append((source[len('src/'):-len('.lu')], 'release' if '--release' in words else 'native'))
    return out


say(CHECK.is_file(), 'candidate-wolf-runner-present')
if not CHECK.is_file():
    sys.exit(1)
say(len(TESTS) > 0 and len(NESTED) > 0, 'candidate-wolf-test-programs-present')
(ROOT / 'target').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='candidate-leaf-', dir=ROOT / 'target') as scratch:
    work = Path(scratch)
    std = work / 'std'
    std.mkdir()
    (std / 'STD-REV').write_text('be1d10fa2798cc6bc2a1fd0b2e559e283469c9bf\n')
    wolf = work / 'wolf'
    calls = work / 'calls'
    wolf.write_text('#!' + sys.executable + '\n' + '''import os, sys
from pathlib import Path
if '--version' in sys.argv:
    print(os.environ.get('MOCK_VERSION', 'wolf 0.2.40+dev.1add9bb (wolfgang, pin 1add9bb)'))
    sys.exit(0)
with open(os.environ['MOCK_CALLS'], 'a') as log:
    log.write(' '.join(sys.argv[1:]) + '\\n')
print('compiler diagnostic')
tier = 'RELEASE' if '--release' in sys.argv else 'NATIVE'
for _ in range(int(os.environ.get('MOCK_E1010_' + tier, '0'))):
    print('error[E1010]: planted')
sys.exit(int(os.environ.get('MOCK_EXIT', '0')))
''')
    wolf.chmod(0o755)
    home = work / 'home'
    home.mkdir()
    env = dict(os.environ, SHELL='/bin/sh', HOME=str(home), DEN_CANDIDATE_WOLF=str(wolf),
               DEN_CANDIDATE_STD=str(std), DEN_CANDIDATE_OUTPUT=str(work / 'out'), MOCK_CALLS=str(calls))

    def run(*args, check=CHECK, cwd=ROOT, **updates):
        calls.write_text('')
        q = subprocess.run([str(check), *args], cwd=cwd, env=dict(env, **updates), capture_output=True, text=True)
        return q, calls.read_text().splitlines()

    q, seen = run()
    got = cells(seen)
    want = [(p, t) for t in ('native', 'release') for p in FIXED] + [(p, 'native') for p in TESTS]
    say(q.returncode == 0 and sorted(c for c in got if c[0] in FIXED) == sorted(want[:12]),
        'candidate-wolf-fixed-twelve-cells')
    # den's test programs are built too: the leaf covers what den tests, not only what it ships
    say(q.returncode == 0 and sorted(got) == sorted(want) and len(got) == len(want)
        and q.stdout.count('PASS candidate-wolf-build-') == len(want),
        'candidate-wolf-programs-include-tests')
    say(all(got.count((p, 'native')) == 1 and (p, 'release') not in got for p in TESTS),
        'candidate-wolf-test-tier-native')
    say(sum('--release' in call for call in seen) == 6 and all('--deny-warnings' in call for call in seen),
        'candidate-wolf-tiers-and-warnings')
    say(all('--error-limit=0' in call for call in seen),
        'candidate-wolf-complete-diagnostics')
    q, seen = run('--program', 'den', '--tier', 'native')
    say(q.returncode == 0 and len(seen) == 1 and 'PASS candidate-wolf-build-den-native' in q.stdout,
        'candidate-wolf-one-row-dry')
    q, seen = run('--program', TESTS[0], '--tier', 'native')
    say(q.returncode == 0 and cells(seen) == [(TESTS[0], 'native')]
        and f'PASS candidate-wolf-build-{TESTS[0]}-native' in q.stdout,
        'candidate-wolf-test-program-row')
    q, seen = run('--program', NESTED[0], '--tier', 'native')
    say(q.returncode == 0 and cells(seen) == [(NESTED[0], 'native')]
        and f'PASS candidate-wolf-build-{NESTED[0]}-native' in q.stdout,
        'candidate-wolf-nested-test-program-row')
    q, seen = run('--program', TESTS[0], '--tier', 'release')
    say(q.returncode != 0 and not seen and 'FAIL candidate-wolf-arguments' in q.stdout,
        'candidate-wolf-test-release-refused')
    q, seen = run('--tier', 'release')
    say(q.returncode == 0 and sorted(cells(seen)) == sorted((p, 'release') for p in FIXED),
        'candidate-wolf-release-tier-skips-tests')
    q, seen = run('--program', '')
    say(q.returncode != 0 and not seen and 'FAIL candidate-wolf-arguments' in q.stdout,
        'candidate-wolf-empty-selection-is-red')
    q, seen = run('--program', 'absent')
    say(q.returncode != 0 and not seen and 'FAIL candidate-wolf-arguments' in q.stdout,
        'candidate-wolf-invalid-selection-is-red')
    q, seen = run(MOCK_EXIT='2')
    say(q.returncode != 0 and len(seen) == len(want) and q.stdout.count('FAIL candidate-wolf-build-') == len(want)
        and 'exit 2' in q.stdout and '  compiler diagnostic' in q.stdout,
        'candidate-wolf-compile-error-is-red')
    q, seen = run(DEN_CANDIDATE_WOLF=str(work / 'absent'))
    say(q.returncode != 0 and 'FAIL candidate-wolf-inputs' in q.stdout, 'candidate-wolf-missing-is-red')
    q, seen = run(MOCK_VERSION='wolf wrong')
    say(q.returncode != 0 and not seen and 'FAIL candidate-wolf-version' in q.stdout,
        'candidate-wolf-wrong-version-is-red')

    # The test programs build on native only because the checker's diagnostics do not depend on the
    # tier. The leaf holds that claim on the programs it builds on both: their E1010 counts agree.
    q, seen = run()
    say(q.returncode == 0 and 'PASS candidate-wolf-tier-independent' in q.stdout,
        'candidate-wolf-tier-equal-passes')
    q, seen = run(MOCK_EXIT='2', MOCK_E1010_NATIVE='1', MOCK_E1010_RELEASE='0')
    say(q.returncode != 0 and 'FAIL candidate-wolf-tier-independent: den E1010 native 1, release 0' in q.stdout
        and 'PASS candidate-wolf-tier-independent' not in q.stdout,
        'candidate-wolf-tier-split-is-red')
    q, seen = run('--tier', 'native')
    say(q.returncode == 0 and 'candidate-wolf-tier-independent' not in q.stdout,
        'candidate-wolf-tier-row-needs-both')

    # A test program added later is built without an edit to the leaf, in src/ or below it.
    tree = work / 'tree'
    (tree / 'tools').mkdir(parents=True)
    (tree / 'src' / 'zlib').mkdir(parents=True)
    for name in ('check-candidate-wolf', 'lib-candidate.sh'):
        shutil.copy2(ROOT / 'tools' / name, tree / 'tools' / name)
    shutil.copy2(ROOT / 'candidate-wolf.toml', tree / 'candidate-wolf.toml')
    for name in FIXED + ['alpha_test', 'zz_added_test']:
        (tree / 'src' / f'{name}.lu').write_text('fn main() -> int { 0 }\n')
    (tree / 'src' / 'zlib' / 'nested_test.lu').write_text('fn main() -> int { 0 }\n')
    (tree / 'src' / '.lu-cache').mkdir()
    (tree / 'src' / '.lu-cache' / 'stale_test.lu').write_text('cached\n')
    q, seen = run(check=tree / 'tools' / 'check-candidate-wolf', cwd=tree)
    got = cells(seen)
    say(q.returncode == 0 and ('zz_added_test', 'native') in got and ('alpha_test', 'native') in got
        and ('zlib/nested_test', 'native') in got and ('zlib/nested_test', 'release') not in got
        and len(got) == 15 and 'PASS candidate-wolf-build-zlib/nested_test-native' in q.stdout,
        'candidate-wolf-new-test-covered')

    (std / 'STD-REV').write_text('wrong\n')
    q, seen = run()
    say(q.returncode != 0 and not seen and 'FAIL candidate-wolf-std' in q.stdout,
        'candidate-wolf-wrong-std-is-red')
sys.exit(bool(failures))
