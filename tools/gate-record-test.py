#!/usr/bin/env python3
"""A failing leaf owns its nonzero END; child output is retained, not trusted."""
import os
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
