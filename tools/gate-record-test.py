#!/usr/bin/env python3
"""A failing leaf owns its nonzero END; child output is retained, not trusted."""
import os
import json
import tempfile
from pathlib import Path
import re
import shlex
import subprocess

root = Path(__file__).resolve().parent.parent
env = dict(os.environ)
env.pop('DEN_GATE_LEAF_RUNNER', None)
for code in (0, 7):
    child = 'alpha\nEND inner exit=0\nbeta\n'
    script = "printf 'alpha\\nEND inner exit=0\\nbeta\\n'; exit " + str(code)
    p = subprocess.run([str(root / 'tools/gate-record'), '--leaf', 'witness', 'sh', '-c', script],
                       cwd=root, env=env, capture_output=True, timeout=30)
    assert p.returncode == code, (p.returncode, p.stdout, p.stderr)
    prefix = ('START witness\n' + ''.join('  ' + line for line in child.splitlines(keepends=True)) + '\n').encode()
    assert p.stdout.startswith(prefix), p.stdout
    assert re.fullmatch(rb'END witness exit=' + str(code).encode() + rb' secs=\d+\n', p.stdout[len(prefix):]), p.stdout
    assert p.stderr == b'', p.stderr
p = subprocess.run([str(root / 'tools/gate-record'), '--leaf', 'unterminated', 'sh', '-c', "printf last; exit 9"],
                   cwd=root, env=env, capture_output=True, timeout=30)
assert p.returncode == 9 and re.fullmatch(rb'START unterminated\n  last\nEND unterminated exit=9 secs=\d+\n', p.stdout), p.stdout
print('gate-record: failing leaves retain exits 7/9 in column-zero END; complete child output stays indented')
# Every literal tools/gate command remains its own leaf, in inherited order.
listed = subprocess.run([str(root / 'tools/gate-record'), '--list'], cwd=root,
                        env=env, capture_output=True, text=True, timeout=30)
assert listed.returncode == 0, listed.stderr
commands = [shlex.split(line.split('\t', 1)[1]) for line in listed.stdout.splitlines()]
position = 0
for line in (root / 'tools/gate').read_text().splitlines():
    if not line.startswith('tools/'):
        continue
    command = shlex.split(line)
    try:
        position = commands.index(command, position) + 1
    except ValueError:
        raise AssertionError('missing or reordered inherited leaf: ' + line)
assert ['python3', '-I', 'ci/local-gate-test.py'] in commands
print('gate-record: all inherited literal commands and local CI routing proof are leaves')

# This is the exact reviewed -> strict consumer boundary that exposed the bug.
plan_run = subprocess.run([str(root / 'tools/gate-record'), '--plan'], cwd=root,
                          env=env, capture_output=True, text=True, check=True)
plan = [json.loads(line) for line in plan_run.stdout.splitlines()]
position = next(i for i, row in enumerate(plan) if row['name'] == 'binary-reviewed')
remaining = plan[position+1:]
assert any('target/native/diffbinary-client' in row['inputs'] for row in remaining)
with tempfile.TemporaryDirectory(prefix='prune-runner-', dir=root/'target') as folder:
    fixture = Path(folder); repo = fixture/'repo'; target = repo/'target'
    (repo/'src').mkdir(parents=True); (repo/'src/den.lu').write_text('// synthetic workspace sentinel\n')
    (target/'native').mkdir(parents=True)
    (target/'native/den').write_bytes(b'synthetic den, never executed\n')
    client = target/'native/diffbinary-client'; client.write_bytes(b'required later, never executed\n')
    (target/'native/diffbinary-test').write_bytes(b'finished unit, never executed\n')
    (fixture/'packed-read.finished').write_text('passed\n')
    planned = fixture/'remaining.json'; planned.write_text(json.dumps(dict(after='binary-reviewed',remaining=remaining)))
    bindir = fixture/'bin'; bindir.mkdir(); probe = bindir/'lsof'
    probe.write_text('#!/bin/sh\nexit 0\n'); probe.chmod(0o755)
    # Unit-only no-open-files stub; real pruning still uses the host lsof.
    child_env = dict(env, PATH=str(bindir)+os.pathsep+env.get('PATH',''))
    result = subprocess.run(['python3','-I',str(root/'tools/gate-prune.py'),str(target),
                             'tools/check-diffbinary',str(planned)], cwd=root,env=child_env,capture_output=True)
    assert result.returncode == 0, ('prune harness failed', result.stdout, result.stderr)
    if not client.exists():
        print('FAIL runner-prune-future-input: binary-reviewed removed the later strict-report input',flush=True)
        raise SystemExit(1)
    assert client.read_bytes()==b'required later, never executed\n'
    assert not (target/'native/diffbinary-test').exists()
print('PASS runner-prune-future-input: remaining-plan consumer retains diffbinary-client')
