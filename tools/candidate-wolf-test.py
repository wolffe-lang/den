"""The candidate compiler leaf must run every build and reject missing inputs."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / 'tools/check-candidate-wolf'
failures = 0


def say(ok, name):
    global failures
    print(('PASS ' if ok else 'FAIL ') + name, flush=True)
    failures += not ok


say(CHECK.is_file(), 'candidate-wolf-runner-present')
if not CHECK.is_file():
    sys.exit(1)
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
sys.exit(int(os.environ.get('MOCK_EXIT', '0')))
''')
    wolf.chmod(0o755)
    home = work / 'home'
    home.mkdir()
    env = dict(os.environ, SHELL='/bin/sh', HOME=str(home), DEN_CANDIDATE_WOLF=str(wolf),
               DEN_CANDIDATE_STD=str(std), DEN_CANDIDATE_OUTPUT=str(work / 'out'), MOCK_CALLS=str(calls))

    def run(**updates):
        calls.write_text('')
        q = subprocess.run([str(CHECK)], cwd=ROOT, env=dict(env, **updates), capture_output=True, text=True)
        return q, calls.read_text().splitlines()

    q, seen = run()
    say(q.returncode == 0 and len(seen) == 12 and q.stdout.count('PASS candidate-wolf-build-') == 12,
        'candidate-wolf-twelve-builds')
    say(sum('--release' in call for call in seen) == 6 and all('--deny-warnings' in call for call in seen),
        'candidate-wolf-tiers-and-warnings')
    q, seen = run(MOCK_EXIT='2')
    say(q.returncode != 0 and len(seen) == 12 and q.stdout.count('FAIL candidate-wolf-build-') == 12
        and 'exit 2' in q.stdout and '  compiler diagnostic' in q.stdout,
        'candidate-wolf-compile-error-is-red')
    q, seen = run(DEN_CANDIDATE_WOLF=str(work / 'absent'))
    say(q.returncode != 0 and 'FAIL candidate-wolf-inputs' in q.stdout, 'candidate-wolf-missing-is-red')
    q, seen = run(MOCK_VERSION='wolf wrong')
    say(q.returncode != 0 and not seen and 'FAIL candidate-wolf-version' in q.stdout,
        'candidate-wolf-wrong-version-is-red')
    (std / 'STD-REV').write_text('wrong\n')
    q, seen = run()
    say(q.returncode != 0 and not seen and 'FAIL candidate-wolf-std' in q.stdout,
        'candidate-wolf-wrong-std-is-red')
sys.exit(bool(failures))
