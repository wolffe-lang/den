#!/usr/bin/env python3
"""Pruning must not depend on lsof on Linux or remove an open workspace file."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
(root / 'target').mkdir(exist_ok=True)
if not sys.platform.startswith('linux'):
    print('SKIP runner-prune-no-lsof reason=Linux-procfs-row')
    raise SystemExit(0)
failed = []
with tempfile.TemporaryDirectory(dir=root/'target', prefix='prune-proc-') as temp:
    fixture = Path(temp)
    repo = fixture/'repo'
    target = repo/'target'
    (repo/'src').mkdir(parents=True)
    (repo/'src/den.lu').write_text('// fixture, not executable\n')
    (target/'native').mkdir(parents=True)
    victim = target/'native/finished-test'
    victim.write_bytes(b'keep while open')
    plan = fixture/'remaining.json'
    plan.write_text(json.dumps({'remaining': []}))
    env = dict(os.environ, PATH=str(fixture/'absent-bin'))
    argv = [sys.executable, '-I', str(root/'tools/gate-prune.py'), str(target), 'tools/check-pack', str(plan)]
    with victim.open('rb'):
        observed = subprocess.run(argv, env=env, capture_output=True)
        ok = observed.returncode != 0 and victim.exists() and b'open workspace file' in observed.stderr
        print(('PASS ' if ok else 'FAIL ') + 'runner-prune-open-file', flush=True)
        if not ok: failed.append('runner-prune-open-file')
    observed = subprocess.run(argv, env=env, capture_output=True)
    ok = observed.returncode == 0 and not victim.exists()
    print(('PASS ' if ok else 'FAIL ') + 'runner-prune-no-lsof', flush=True)
    if not ok: failed.append('runner-prune-no-lsof')
    checked = subprocess.run([sys.executable, '-I', str(root/'tools/gate-prune.py'), '--preflight'], env=env, capture_output=True)
    ok = checked.returncode == 0 and b'PASS prune-open-files-preflight' in checked.stdout
    print(('PASS ' if ok else 'FAIL ') + 'runner-prune-preflight', flush=True)
    if not ok: failed.append('runner-prune-preflight')
if failed:
    raise SystemExit(', '.join(failed))
